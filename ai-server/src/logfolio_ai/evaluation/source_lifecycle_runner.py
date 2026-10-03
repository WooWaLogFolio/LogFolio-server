import argparse
import asyncio
import json
from pathlib import Path
from typing import List, Sequence
from uuid import UUID, uuid4

from pydantic import Field

from logfolio_ai.models import DocumentPage, DocumentSource
from logfolio_ai.models.base import ContractModel
from logfolio_ai.rag import RagService
from logfolio_ai.vector_store import MemoryVectorStore


EVALS_ROOT = Path(__file__).resolve().parents[3] / "evals"
DEFAULT_DATASET = EVALS_ROOT / "datasets" / "source_lifecycle_v1.json"


class SourceLifecycleEvalCase(ContractModel):
    case_id: str = Field(min_length=1)
    scenario: str = Field(min_length=1)
    expected_outcome: str = Field(min_length=1)


class SourceLifecycleCaseResult(ContractModel):
    case_id: str
    passed: bool
    expected_outcome: str
    actual_outcome: str
    failures: List[str] = Field(default_factory=list)


class SourceLifecycleEvalReport(ContractModel):
    dataset: str
    total: int = Field(ge=0)
    passed: int = Field(ge=0)
    failed: int = Field(ge=0)
    pass_rate: float = Field(ge=0, le=1)
    results: List[SourceLifecycleCaseResult]


class _DeterministicEmbeddingProvider:
    dimension = 3

    def __init__(self) -> None:
        self.document_count = 0

    async def embed_documents(self, texts: Sequence[str]) -> List[List[float]]:
        self.document_count += len(texts)
        return [self._embedding(text) for text in texts]

    async def embed_query(self, text: str) -> List[float]:
        return self._embedding(text)

    async def embed_queries(self, texts: Sequence[str]) -> List[List[float]]:
        return [self._embedding(text) for text in texts]

    @staticmethod
    def _embedding(text: str) -> List[float]:
        normalized = text.lower()
        return [
            1.0 if "인터뷰" in normalized else 0.1,
            1.0 if "jwt" in normalized else 0.1,
            1.0,
        ]


def _source(text: str, name: str = "source.txt") -> DocumentSource:
    return DocumentSource(
        source_id=uuid4(),
        source_name=name,
        pages=[DocumentPage(page_number=1, text=text)],
    )


def _service() -> tuple[RagService, _DeterministicEmbeddingProvider]:
    embedding = _DeterministicEmbeddingProvider()
    return (
        RagService(
            embedding,
            MemoryVectorStore(),
            embedding_model="offline-lifecycle-eval",
            chunk_size_tokens=50,
            chunk_overlap_tokens=5,
            top_k=5,
        ),
        embedding,
    )


def load_source_lifecycle_cases(
    path: Path = DEFAULT_DATASET,
) -> tuple[str, List[SourceLifecycleEvalCase]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload["name"], [
        SourceLifecycleEvalCase.model_validate(item) for item in payload["cases"]
    ]


async def _exact_duplicate() -> str:
    service, embedding = _service()
    project_id = uuid4()
    original = _source("사용자 인터뷰를 진행했다.", "original.txt")
    duplicate = _source("사용자 인터뷰를 진행했다.", "duplicate.txt")

    first = await service.index_sources(project_id, [original])
    second = await service.index_sources(project_id, [duplicate])
    if (
        first.indexed_count == 1
        and second.duplicate_count == 1
        and second.items[0].duplicate_of_source_id == original.source_id
        and embedding.document_count == 1
    ):
        return "DUPLICATE_BLOCKED"
    return "UNEXPECTED_RESULT"


async def _project_isolation() -> str:
    service, _ = _service()
    first_project = uuid4()
    second_project = uuid4()
    text = "JWT 인증 기능을 구현했다."

    first = await service.index_sources(first_project, [_source(text, "first.txt")])
    second = await service.index_sources(second_project, [_source(text, "second.txt")])
    if first.indexed_count == 1 and second.indexed_count == 1:
        return "BOTH_INDEXED"
    return "UNEXPECTED_RESULT"


async def _delete_excludes_retrieval() -> str:
    service, _ = _service()
    project_id = uuid4()
    deleted = _source("사용자 인터뷰를 진행했다.")

    await service.index_sources(project_id, [deleted])
    before = await service.retrieve(project_id, "사용자 인터뷰")
    await service.delete_source_index(project_id, deleted.source_id)
    after = await service.retrieve(project_id, "사용자 인터뷰")
    if (
        any(item.source_id == deleted.source_id for item in before)
        and all(item.source_id != deleted.source_id for item in after)
    ):
        return "NOT_RETRIEVED"
    return "UNEXPECTED_RESULT"


async def _delete_releases_content_hash() -> str:
    service, _ = _service()
    project_id = uuid4()
    text = "동일한 자료를 삭제 후 다시 등록한다."
    original = _source(text, "original.txt")
    replacement = _source(text, "replacement.txt")

    await service.index_sources(project_id, [original])
    await service.delete_source_index(project_id, original.source_id)
    result = await service.index_sources(project_id, [replacement])
    if result.indexed_count == 1 and result.duplicate_count == 0:
        return "REUPLOAD_INDEXED"
    return "UNEXPECTED_RESULT"


async def evaluate_source_lifecycle_case(
    case: SourceLifecycleEvalCase,
) -> SourceLifecycleCaseResult:
    scenarios = {
        "EXACT_DUPLICATE": _exact_duplicate,
        "PROJECT_ISOLATION": _project_isolation,
        "DELETE_EXCLUDES_RETRIEVAL": _delete_excludes_retrieval,
        "DELETE_RELEASES_CONTENT_HASH": _delete_releases_content_hash,
    }
    evaluator = scenarios.get(case.scenario)
    if evaluator is None:
        raise ValueError(f"Unsupported Source lifecycle scenario: {case.scenario}")
    actual_outcome = await evaluator()
    failures = []
    if actual_outcome != case.expected_outcome:
        failures.append(
            f"outcome expected={case.expected_outcome} actual={actual_outcome}"
        )
    return SourceLifecycleCaseResult(
        case_id=case.case_id,
        passed=not failures,
        expected_outcome=case.expected_outcome,
        actual_outcome=actual_outcome,
        failures=failures,
    )


async def run_source_lifecycle_eval(
    cases: List[SourceLifecycleEvalCase], dataset_name: str
) -> SourceLifecycleEvalReport:
    results = [await evaluate_source_lifecycle_case(case) for case in cases]
    passed = sum(result.passed for result in results)
    return SourceLifecycleEvalReport(
        dataset=dataset_name,
        total=len(results),
        passed=passed,
        failed=len(results) - passed,
        pass_rate=passed / len(results) if results else 0,
        results=results,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run LogFolio offline Source lifecycle evaluation"
    )
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output-json", type=Path)
    args = parser.parse_args()
    dataset_name, cases = load_source_lifecycle_cases(args.dataset)
    report = asyncio.run(run_source_lifecycle_eval(cases, dataset_name))
    rendered = report.model_dump_json(indent=2, by_alias=True)
    print(rendered)
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(rendered + "\n", encoding="utf-8")
    raise SystemExit(0 if report.failed == 0 else 1)


if __name__ == "__main__":
    main()
