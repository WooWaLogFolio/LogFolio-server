import argparse
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from typing import List, Optional, Sequence
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

from pydantic import Field

from logfolio_ai.chunking import DocumentChunk
from logfolio_ai.core.errors import AppError
from logfolio_ai.llm import GroundedAnalysisInput, GroundedChunk
from logfolio_ai.llm.gemini import GeminiLLMProvider
from logfolio_ai.models import DocumentPage, DocumentSource
from logfolio_ai.models.base import ContractModel
from logfolio_ai.rag import AnalysisPurpose, RagService


EVALS_ROOT = Path(__file__).resolve().parents[3] / "evals"
DEFAULT_DATASET = EVALS_ROOT / "datasets" / "resilience_core_v1.json"


class ResilienceEvalCase(ContractModel):
    case_id: str = Field(min_length=1)
    scenario: str = Field(min_length=1)
    expected_outcome: str = Field(min_length=1)
    expected_attempts: int = Field(ge=1)
    expected_retry_count: int = Field(ge=0)


class ResilienceCaseResult(ContractModel):
    case_id: str
    passed: bool
    expected_outcome: str
    actual_outcome: str
    attempts: int = Field(ge=0)
    retry_count: int = Field(ge=0)
    failures: List[str] = Field(default_factory=list)


class ResilienceEvalReport(ContractModel):
    dataset: str
    total: int = Field(ge=0)
    passed: int = Field(ge=0)
    failed: int = Field(ge=0)
    pass_rate: float = Field(ge=0, le=1)
    results: List[ResilienceCaseResult]


def _request() -> GroundedAnalysisInput:
    return GroundedAnalysisInput(
        analysis_run_id=uuid4(),
        project_id=uuid4(),
        chunks=[
            GroundedChunk(
                chunk_id=uuid4(),
                source_id=uuid4(),
                source_name="resilience.txt",
                page_number=1,
                text="팀은 사용자 인터뷰 결과를 바탕으로 기능 우선순위를 바꿨다.",
                distance=0.1,
                purposes=[AnalysisPurpose.PROJECT_OVERVIEW],
            )
        ],
    )


def _valid_response() -> SimpleNamespace:
    return SimpleNamespace(
        text=json.dumps(
            {
                "analysisRunId": str(uuid4()),
                "projectId": str(uuid4()),
                "summary": "재시도 후 분석을 완료했습니다.",
                "candidates": [],
                "questions": [],
            }
        )
    )


class _ProviderHttpError(Exception):
    status_code = 400


class _RecordingEmbeddingProvider:
    dimension = 3

    def __init__(self, failing_text: str) -> None:
        self.failing_text = failing_text
        self.attempts = 0

    async def embed_documents(self, texts: Sequence[str]) -> List[List[float]]:
        self.attempts += 1
        if any(self.failing_text in text for text in texts):
            raise AppError("EMBEDDING_ERROR", "의도된 평가 실패", 502)
        return [[1.0, 0.0, 0.0] for _ in texts]

    async def embed_query(self, text: str) -> List[float]:
        del text
        return [1.0, 0.0, 0.0]


class _RecordingVectorStore:
    def __init__(self) -> None:
        self.stored_source_ids: List[UUID] = []

    async def find_source_by_content_hash(
        self, project_id: UUID, content_hash: str
    ) -> Optional[UUID]:
        del project_id, content_hash
        return None

    async def replace_source_chunks(
        self,
        project_id: UUID,
        source_id: UUID,
        chunks: Sequence[DocumentChunk],
        embeddings: Sequence[Sequence[float]],
        *,
        embedding_model: str,
        content_hash: Optional[str] = None,
    ) -> None:
        del project_id, chunks, embeddings, embedding_model, content_hash
        self.stored_source_ids.append(source_id)


def load_resilience_cases(
    path: Path = DEFAULT_DATASET,
) -> tuple[str, List[ResilienceEvalCase]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload["name"], [
        ResilienceEvalCase.model_validate(item) for item in payload["cases"]
    ]


async def _evaluate_llm_case(case: ResilienceEvalCase) -> tuple[str, int, int]:
    if case.scenario == "INVALID_THEN_SUCCESS":
        side_effect = [SimpleNamespace(text="not-json"), _valid_response()]
    elif case.scenario == "TIMEOUT":
        side_effect = asyncio.TimeoutError
    elif case.scenario == "NON_TRANSIENT_4XX":
        side_effect = _ProviderHttpError("invalid request")
    elif case.scenario == "INVALID_OUTPUT":
        side_effect = None
    else:
        raise ValueError(f"Unsupported LLM scenario: {case.scenario}")

    if case.scenario == "INVALID_OUTPUT":
        generate_content = AsyncMock(return_value=SimpleNamespace(text="not-json"))
    else:
        generate_content = AsyncMock(side_effect=side_effect)
    client = SimpleNamespace(
        aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
    )
    provider = GeminiLLMProvider(
        "offline-test-key",
        "offline-scripted-model",
        0.1,
        client=client,
    )
    try:
        await provider.analyze_grounded(_request())
        outcome = "SUCCESS"
    except AppError as exc:
        outcome = exc.code
    metrics = provider.last_call_metrics
    return outcome, generate_content.await_count, metrics.retry_count if metrics else 0


async def _evaluate_partial_indexing() -> tuple[str, int, int]:
    embedding = _RecordingEmbeddingProvider("FAIL_THIS_SOURCE")
    store = _RecordingVectorStore()
    service = RagService(
        embedding,
        store,
        embedding_model="offline-eval-embedding",
        chunk_size_tokens=50,
        chunk_overlap_tokens=5,
    )
    sources = [
        DocumentSource(
            source_id=uuid4(),
            source_name=f"source-{index}.txt",
            pages=[DocumentPage(page_number=1, text=text)],
        )
        for index, text in enumerate(
            ["첫 번째 정상 자료", "FAIL_THIS_SOURCE", "세 번째 정상 자료"],
            start=1,
        )
    ]
    result = await service.index_sources(uuid4(), sources)
    outcome = (
        "PARTIAL_SUCCESS"
        if result.indexed_count == 2
        and result.failed_count == 1
        and len(store.stored_source_ids) == 2
        else "UNEXPECTED_RESULT"
    )
    return outcome, embedding.attempts, 0


async def evaluate_resilience_case(
    case: ResilienceEvalCase,
) -> ResilienceCaseResult:
    if case.scenario == "PARTIAL_SOURCE_INDEXING":
        outcome, attempts, retry_count = await _evaluate_partial_indexing()
    else:
        outcome, attempts, retry_count = await _evaluate_llm_case(case)

    failures: List[str] = []
    if outcome != case.expected_outcome:
        failures.append(
            f"outcome expected={case.expected_outcome} actual={outcome}"
        )
    if attempts != case.expected_attempts:
        failures.append(
            f"attempts expected={case.expected_attempts} actual={attempts}"
        )
    if retry_count != case.expected_retry_count:
        failures.append(
            "retryCount "
            f"expected={case.expected_retry_count} actual={retry_count}"
        )
    return ResilienceCaseResult(
        case_id=case.case_id,
        passed=not failures,
        expected_outcome=case.expected_outcome,
        actual_outcome=outcome,
        attempts=attempts,
        retry_count=retry_count,
        failures=failures,
    )


async def run_resilience_eval(
    cases: List[ResilienceEvalCase], dataset_name: str
) -> ResilienceEvalReport:
    results = [await evaluate_resilience_case(case) for case in cases]
    passed = sum(result.passed for result in results)
    return ResilienceEvalReport(
        dataset=dataset_name,
        total=len(results),
        passed=passed,
        failed=len(results) - passed,
        pass_rate=passed / len(results) if results else 0,
        results=results,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run LogFolio offline failure and recovery evaluation"
    )
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output-json", type=Path)
    args = parser.parse_args()
    dataset_name, cases = load_resilience_cases(args.dataset)
    report = asyncio.run(run_resilience_eval(cases, dataset_name))
    rendered = report.model_dump_json(indent=2, by_alias=True)
    print(rendered)
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(rendered + "\n", encoding="utf-8")
    raise SystemExit(0 if report.failed == 0 else 1)


if __name__ == "__main__":
    main()
