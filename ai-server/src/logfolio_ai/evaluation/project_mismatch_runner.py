import argparse
import asyncio
import json
from pathlib import Path
from typing import List, Optional, Sequence
from uuid import uuid4

from pydantic import Field

from logfolio_ai.analysis import AnalysisOrchestrator
from logfolio_ai.llm import GroundedAnalysisInput, LLMCallMetrics
from logfolio_ai.models import (
    AnalysisRequest,
    AnalysisResponse,
    AnalysisResultType,
    DocumentPage,
    DocumentSource,
    ProjectContext,
)
from logfolio_ai.models.base import ContractModel
from logfolio_ai.rag import RagService
from logfolio_ai.vector_store import MemoryVectorStore


EVALS_ROOT = Path(__file__).resolve().parents[3] / "evals"
DEFAULT_DATASET = EVALS_ROOT / "datasets" / "project_mismatch_v1.json"


class ProjectMismatchEvalCase(ContractModel):
    case_id: str = Field(min_length=1)
    scenario: str = Field(min_length=1)
    expected_outcome: str = Field(min_length=1)


class ProjectMismatchCaseResult(ContractModel):
    case_id: str
    passed: bool
    expected_outcome: str
    actual_outcome: str
    llm_called: bool
    source_preserved: bool
    failures: List[str] = Field(default_factory=list)


class ProjectMismatchEvalReport(ContractModel):
    dataset: str
    total: int = Field(ge=0)
    passed: int = Field(ge=0)
    failed: int = Field(ge=0)
    pass_rate: float = Field(ge=0, le=1)
    results: List[ProjectMismatchCaseResult]


class _SemanticFixtureEmbedding:
    dimension = 3

    async def embed_documents(self, texts: Sequence[str]) -> List[List[float]]:
        return [self._embedding(text) for text in texts]

    async def embed_query(self, text: str) -> List[float]:
        return self._embedding(text)

    async def embed_queries(self, texts: Sequence[str]) -> List[List[float]]:
        return [self._embedding(text) for text in texts]

    @staticmethod
    def _embedding(text: str) -> List[float]:
        normalized = text.lower()
        if "logfolio" in normalized or "경험 정리" in normalized:
            return [1.0, 0.0, 0.0]
        if "쇼핑몰" in normalized or "결제" in normalized:
            return [0.0, 1.0, 0.0]
        return [0.0, 0.0, 1.0]


class _RecordingProvider:
    def __init__(self) -> None:
        self.called = False
        self.last_call_metrics: Optional[LLMCallMetrics] = None

    async def analyze_grounded(
        self, request: GroundedAnalysisInput
    ) -> AnalysisResponse:
        self.called = True
        self.last_call_metrics = LLMCallMetrics(
            provider="project-mismatch-fixture",
            model="scripted",
            latency_ms=0,
            retry_count=0,
        )
        return AnalysisResponse(
            analysis_run_id=request.analysis_run_id,
            project_id=request.project_id,
            summary="확인된 Source를 근거로 분석했습니다.",
            candidates=[],
            questions=[],
        )


def load_project_mismatch_cases(
    path: Path = DEFAULT_DATASET,
) -> tuple[str, List[ProjectMismatchEvalCase]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload["name"], [
        ProjectMismatchEvalCase.model_validate(item) for item in payload["cases"]
    ]


def _source(text: str, name: str) -> DocumentSource:
    return DocumentSource(
        source_id=uuid4(),
        source_name=name,
        pages=[DocumentPage(page_number=1, text=text)],
    )


async def _run_scenario(
    scenario: str,
) -> tuple[str, bool, bool]:
    store = MemoryVectorStore()
    rag = RagService(
        _SemanticFixtureEmbedding(),
        store,
        embedding_model="project-mismatch-fixture",
        chunk_size_tokens=50,
        chunk_overlap_tokens=5,
        project_source_match_distance=0.65,
    )
    provider = _RecordingProvider()
    project_id = uuid4()
    project_context = ProjectContext(
        name="LogFolio",
        description="프로젝트 경험 정리 서비스",
    )
    if scenario in {"SUSPECTED_SOURCE", "CONFIRMED_SOURCE"}:
        source = _source("쇼핑몰 결제 기능을 구현했다.", "other-project.txt")
    elif scenario == "RELATED_SOURCE":
        source = _source("LogFolio 경험 정리 기능을 구현했다.", "logfolio.txt")
    else:
        raise ValueError(f"Unsupported project mismatch scenario: {scenario}")

    await rag.index_sources(project_id, [source])
    confirmed_source_ids = (
        [source.source_id] if scenario == "CONFIRMED_SOURCE" else []
    )
    response = await AnalysisOrchestrator(rag, provider).analyze(
        AnalysisRequest(
            analysis_run_id=uuid4(),
            project_id=project_id,
            source_ids=[source.source_id],
            project_context=project_context,
            confirmed_source_ids=confirmed_source_ids,
        )
    )
    stored_chunks = await store.get_source_chunks(
        project_id, [source.source_id], limit=20
    )
    source_preserved = bool(stored_chunks)

    if scenario == "SUSPECTED_SOURCE":
        if (
            response.result_types == [AnalysisResultType.NEEDS_CONTEXT]
            and len(response.source_warnings) == 1
            and response.source_warnings[0].source_id == source.source_id
            and not provider.called
            and source_preserved
        ):
            return "WAITING_FOR_CONFIRMATION", provider.called, source_preserved
    elif scenario == "CONFIRMED_SOURCE":
        if not response.source_warnings and provider.called and source_preserved:
            return "ANALYZED_AFTER_CONFIRMATION", provider.called, source_preserved
    elif not response.source_warnings and provider.called and source_preserved:
        return "ANALYZED_WITHOUT_WARNING", provider.called, source_preserved
    return "UNEXPECTED_RESULT", provider.called, source_preserved


async def evaluate_project_mismatch_case(
    case: ProjectMismatchEvalCase,
) -> ProjectMismatchCaseResult:
    actual_outcome, llm_called, source_preserved = await _run_scenario(case.scenario)
    failures: List[str] = []
    if actual_outcome != case.expected_outcome:
        failures.append(
            f"outcome expected={case.expected_outcome} actual={actual_outcome}"
        )
    if not source_preserved:
        failures.append("source was deleted or excluded from its project index")
    return ProjectMismatchCaseResult(
        case_id=case.case_id,
        passed=not failures,
        expected_outcome=case.expected_outcome,
        actual_outcome=actual_outcome,
        llm_called=llm_called,
        source_preserved=source_preserved,
        failures=failures,
    )


async def run_project_mismatch_eval(
    cases: List[ProjectMismatchEvalCase], dataset_name: str
) -> ProjectMismatchEvalReport:
    results = [await evaluate_project_mismatch_case(case) for case in cases]
    passed = sum(result.passed for result in results)
    return ProjectMismatchEvalReport(
        dataset=dataset_name,
        total=len(results),
        passed=passed,
        failed=len(results) - passed,
        pass_rate=passed / len(results) if results else 0,
        results=results,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run LogFolio project mismatch confirmation evaluation"
    )
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output-json", type=Path)
    args = parser.parse_args()
    dataset_name, cases = load_project_mismatch_cases(args.dataset)
    report = asyncio.run(run_project_mismatch_eval(cases, dataset_name))
    rendered = report.model_dump_json(indent=2, by_alias=True)
    print(rendered)
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(rendered + "\n", encoding="utf-8")
    raise SystemExit(0 if report.failed == 0 else 1)


if __name__ == "__main__":
    main()
