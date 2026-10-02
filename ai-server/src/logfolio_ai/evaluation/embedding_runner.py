import argparse
import asyncio
import json
import math
import os
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from pydantic import Field

from logfolio_ai.embedding.e5 import E5EmbeddingProvider
from logfolio_ai.models.base import ContractModel


EVALS_ROOT = Path(__file__).resolve().parents[3] / "evals"
DEFAULT_DATASET = EVALS_ROOT / "datasets" / "retrieval_core_v1.json"


class RetrievalCandidate(ContractModel):
    chunk_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    text: str = Field(min_length=1)


class RetrievalEvalCase(ContractModel):
    case_id: str = Field(min_length=1)
    category: str = Field(min_length=1)
    query: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    expected_chunk_ids: List[str] = Field(min_length=1)
    candidates: List[RetrievalCandidate] = Field(min_length=1)


class RetrievalCaseResult(ContractModel):
    case_id: str
    category: str
    retrieved_chunk_ids: List[str]
    recall_at_k: float = Field(ge=0, le=1)
    irrelevant_chunk_ratio: float = Field(ge=0, le=1)
    cross_project_count: int = Field(ge=0)
    passed: bool


class RetrievalEvalReport(ContractModel):
    dataset: str
    model: str
    top_k: int = Field(ge=1)
    dimension: int = Field(ge=1)
    expected_dimension: int = Field(ge=1)
    dimensions_match: bool
    vectors_normalized: bool
    mean_recall_at_k: float = Field(ge=0, le=1)
    mean_irrelevant_chunk_ratio: float = Field(ge=0, le=1)
    cross_project_count: int = Field(ge=0)
    success: bool
    cases: List[RetrievalCaseResult]


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return numerator / (left_norm * right_norm)


def load_retrieval_cases(
    path: Path = DEFAULT_DATASET,
) -> Tuple[str, int, List[RetrievalEvalCase]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases = [RetrievalEvalCase.model_validate(item) for item in payload["cases"]]
    return payload["name"], int(payload.get("topK", 5)), cases


def evaluate_retrieved_chunks(
    case: RetrievalEvalCase,
    retrieved_chunk_ids: List[str],
) -> RetrievalCaseResult:
    expected = set(case.expected_chunk_ids)
    candidates = {candidate.chunk_id: candidate for candidate in case.candidates}
    retrieved = [chunk_id for chunk_id in retrieved_chunk_ids if chunk_id in candidates]
    relevant_count = sum(chunk_id in expected for chunk_id in retrieved)
    cross_project_count = sum(
        candidates[chunk_id].project_id != case.project_id for chunk_id in retrieved
    )
    recall = relevant_count / len(expected)
    irrelevant_ratio = (
        (len(retrieved) - relevant_count) / len(retrieved) if retrieved else 0.0
    )
    return RetrievalCaseResult(
        case_id=case.case_id,
        category=case.category,
        retrieved_chunk_ids=retrieved,
        recall_at_k=recall,
        irrelevant_chunk_ratio=irrelevant_ratio,
        cross_project_count=cross_project_count,
        passed=recall == 1.0 and cross_project_count == 0,
    )


async def evaluate(
    dataset_path: Path = DEFAULT_DATASET,
    top_k_override: Optional[int] = None,
) -> RetrievalEvalReport:
    dataset_name, configured_top_k, cases = load_retrieval_cases(dataset_path)
    top_k = top_k_override or configured_top_k
    model_name = os.environ.get(
        "LOGFOLIO_AI_EMBEDDING_MODEL",
        "intfloat/multilingual-e5-base",
    )
    expected_dimension = int(os.environ.get("LOGFOLIO_AI_VECTOR_DIMENSION", "768"))
    provider = E5EmbeddingProvider(model_name=model_name, batch_size=8)

    results: List[RetrievalCaseResult] = []
    vectors_normalized = True
    vector_dimensions_match = True
    for case in cases:
        # Project scoping happens before ranking so another project's chunk cannot leak.
        eligible = [
            candidate for candidate in case.candidates
            if candidate.project_id == case.project_id
        ]
        passage_vectors = await provider.embed_documents(
            [candidate.text for candidate in eligible]
        )
        query_vector = await provider.embed_query(case.query)
        all_vectors = [query_vector, *passage_vectors]
        vectors_normalized = vectors_normalized and all(
            math.isclose(
                math.sqrt(sum(value * value for value in vector)),
                1.0,
                rel_tol=1e-5,
                abs_tol=1e-5,
            )
            for vector in all_vectors
        )
        vector_dimensions_match = vector_dimensions_match and all(
            len(vector) == expected_dimension for vector in all_vectors
        )
        scores: Dict[str, float] = {
            candidate.chunk_id: cosine_similarity(query_vector, vector)
            for candidate, vector in zip(eligible, passage_vectors)
        }
        ranked_ids = sorted(scores, key=scores.get, reverse=True)[:top_k]
        results.append(evaluate_retrieved_chunks(case, ranked_ids))

    dimensions_match = provider.dimension == expected_dimension and vector_dimensions_match
    mean_recall = sum(item.recall_at_k for item in results) / len(results) if results else 0
    mean_irrelevant = (
        sum(item.irrelevant_chunk_ratio for item in results) / len(results)
        if results else 0
    )
    cross_project_count = sum(item.cross_project_count for item in results)
    return RetrievalEvalReport(
        dataset=dataset_name,
        model=model_name,
        top_k=top_k,
        dimension=provider.dimension,
        expected_dimension=expected_dimension,
        dimensions_match=dimensions_match,
        vectors_normalized=vectors_normalized,
        mean_recall_at_k=mean_recall,
        mean_irrelevant_chunk_ratio=mean_irrelevant,
        cross_project_count=cross_project_count,
        success=(
            bool(results)
            and dimensions_match
            and vectors_normalized
            and all(item.passed for item in results)
        ),
        cases=results,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run LogFolio E5 retrieval evaluations")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--top-k", type=int)
    parser.add_argument("--output-json", type=Path)
    args = parser.parse_args()
    if args.top_k is not None and args.top_k < 1:
        parser.error("--top-k must be at least 1")
    report = asyncio.run(evaluate(args.dataset, args.top_k))
    rendered = report.model_dump_json(indent=2, by_alias=True)
    print(rendered)
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(rendered + "\n", encoding="utf-8")
    raise SystemExit(0 if report.success else 1)


if __name__ == "__main__":
    main()
