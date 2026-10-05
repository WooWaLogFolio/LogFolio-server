import argparse
import asyncio
import json
from pathlib import Path
from typing import List, Optional
from uuid import UUID

from pydantic import Field

from logfolio_ai.analysis import AnalysisOrchestrator
from logfolio_ai.chunking import DocumentChunk
from logfolio_ai.llm import GroundedAnalysisInput, GroundedChunk, LLMCallMetrics
from logfolio_ai.models import (
    AnalysisRequest,
    AnalysisResponse,
    AnalysisResultType,
    InformationNeedType,
    PolicyViolationType,
    SourceWarning,
    SubjectType,
)
from logfolio_ai.models.base import ContractModel
from logfolio_ai.rag import (
    AnalysisPurpose,
    ExistingExperienceContext,
    IndexingResult,
    RetrievalContext,
)
from logfolio_ai.vector_store import VectorSearchResult


EVALS_ROOT = Path(__file__).resolve().parents[3] / "evals"
DEFAULT_DATASET = EVALS_ROOT / "datasets" / "pipeline_core_v1.json"


class PipelineExpectation(ContractModel):
    result_types: List[AnalysisResultType]
    candidate_count: int = Field(ge=0, le=3)
    llm_called: bool
    question_count: int = Field(default=0, ge=0, le=2)
    information_need: Optional[InformationNeedType] = None
    conflict_count: int = Field(default=0, ge=0)
    target_experience_id: Optional[UUID] = None
    conflict_existing_contents: List[str] = Field(default_factory=list)
    subject_type: Optional[SubjectType] = None
    policy_violations: List[PolicyViolationType] = Field(default_factory=list)


class PipelineEvalCase(ContractModel):
    case_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    request: AnalysisRequest
    retrieved_chunks: List[GroundedChunk] = Field(default_factory=list)
    provider_output: Optional[AnalysisResponse] = None
    expected: PipelineExpectation


class PipelineCaseResult(ContractModel):
    case_id: str
    passed: bool
    llm_called: bool
    actual_result_types: List[AnalysisResultType]
    candidate_count: int
    question_count: int
    information_need: Optional[InformationNeedType] = None
    conflict_count: int = Field(ge=0)
    failures: List[str] = Field(default_factory=list)


class PipelineEvalReport(ContractModel):
    dataset: str
    total: int = Field(ge=0)
    passed: int = Field(ge=0)
    failed: int = Field(ge=0)
    pass_rate: float = Field(ge=0, le=1)
    results: List[PipelineCaseResult]


class DatasetRagService:
    def __init__(self, chunks: List[GroundedChunk]) -> None:
        self._chunks = chunks

    async def find_suspected_project_mismatches(
        self, project_id, source_ids, project_context, *, confirmed_source_ids=()
    ) -> List[SourceWarning]:
        del project_id, source_ids, project_context, confirmed_source_ids
        return []

    async def index_documents(self, project_id, documents) -> IndexingResult:
        del project_id
        return IndexingResult(
            document_count=len(documents),
            chunk_count=len(self._chunks),
            embedding_model="pipeline-eval-fixture",
        )

    async def retrieve_analysis_context(
        self, project_id, *, source_ids=None
    ) -> List[RetrievalContext]:
        del project_id
        allowed = set(source_ids or [])
        chunks = [chunk for chunk in self._chunks if chunk.source_id in allowed]
        if not chunks:
            return []
        return [
            RetrievalContext(
                purpose=AnalysisPurpose.PROJECT_OVERVIEW,
                query="pipeline evaluation fixture",
                chunks=[
                    VectorSearchResult(
                        chunk_id=chunk.chunk_id,
                        source_id=chunk.source_id,
                        source_type=chunk.source_type,
                        source_name=chunk.source_name,
                        sequence=index,
                        page_number=chunk.page_number,
                        section_title=chunk.section_title,
                        char_start=0,
                        char_end=len(chunk.text),
                        text=chunk.text,
                        distance=chunk.distance,
                    )
                    for index, chunk in enumerate(chunks)
                ],
            )
        ]

    async def retrieve_related_experience_context(
        self, project_id, source_ids, existing_experiences
    ) -> List[ExistingExperienceContext]:
        del project_id, source_ids
        return [
            ExistingExperienceContext(
                experience_id=experience.experience_id,
                relevance_distance=0.2,
                chunks=[],
            )
            for experience in existing_experiences
        ]

    async def retrieve_source_chunks(
        self, project_id, source_ids, *, limit: int
    ) -> List[DocumentChunk]:
        del project_id, source_ids, limit
        return []


class DatasetLLMProvider:
    def __init__(self, output: Optional[AnalysisResponse]) -> None:
        self._output = output
        self.called = False
        self.last_call_metrics = LLMCallMetrics(
            provider="pipeline-fixture",
            model="scripted",
            input_tokens=0,
            cached_input_tokens=0,
            output_tokens=0,
            reasoning_tokens=0,
            latency_ms=0,
            retry_count=0,
        )

    async def analyze_grounded(
        self, request: GroundedAnalysisInput
    ) -> AnalysisResponse:
        self.called = True
        if self._output is None:
            raise AssertionError("LLM was called but this case has no providerOutput")
        return self._output.model_copy(
            update={
                "analysis_run_id": request.analysis_run_id,
                "project_id": request.project_id,
            }
        )


def load_pipeline_cases(
    path: Path = DEFAULT_DATASET,
) -> tuple:
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases = [PipelineEvalCase.model_validate(item) for item in payload["cases"]]
    return payload["name"], cases


async def evaluate_pipeline_case(case: PipelineEvalCase) -> PipelineCaseResult:
    provider = DatasetLLMProvider(case.provider_output)
    response = await AnalysisOrchestrator(
        DatasetRagService(case.retrieved_chunks),
        provider,
    ).analyze(case.request)
    failures: List[str] = []
    actual_result_types = list(response.result_types)
    if set(actual_result_types) != set(case.expected.result_types):
        failures.append(
            f"resultTypes expected={case.expected.result_types} actual={actual_result_types}"
        )
    if len(response.candidates) != case.expected.candidate_count:
        failures.append(
            f"candidateCount expected={case.expected.candidate_count} "
            f"actual={len(response.candidates)}"
        )
    if provider.called != case.expected.llm_called:
        failures.append(
            f"llmCalled expected={case.expected.llm_called} actual={provider.called}"
        )
    if len(response.questions) != case.expected.question_count:
        failures.append(
            f"questionCount expected={case.expected.question_count} "
            f"actual={len(response.questions)}"
        )
    if response.information_need != case.expected.information_need:
        failures.append(
            "informationNeed "
            f"expected={case.expected.information_need} "
            f"actual={response.information_need}"
        )
    conflict_candidates = [
        candidate for candidate in response.candidates if candidate.conflict
    ]
    if len(conflict_candidates) != case.expected.conflict_count:
        failures.append(
            f"conflictCount expected={case.expected.conflict_count} "
            f"actual={len(conflict_candidates)}"
        )
    if case.expected.target_experience_id is not None and not any(
        candidate.target_experience_id == case.expected.target_experience_id
        for candidate in response.candidates
    ):
        failures.append(
            f"missingTargetExperienceId={case.expected.target_experience_id}"
        )
    actual_existing_contents = {
        conflict.existing_content
        for candidate in conflict_candidates
        for conflict in candidate.conflicts
    }
    missing_existing_contents = [
        content
        for content in case.expected.conflict_existing_contents
        if content not in actual_existing_contents
    ]
    if missing_existing_contents:
        failures.append(
            f"missingConflictExistingContents={missing_existing_contents}"
        )
    claims = [claim for candidate in response.candidates for claim in candidate.claims]
    if case.expected.subject_type is not None and not any(
        claim.subject_type == case.expected.subject_type for claim in claims
    ):
        failures.append(f"missingSubjectType={case.expected.subject_type.value}")
    actual_violations = {
        violation for claim in claims for violation in claim.policy_violations
    }
    missing_violations = [
        violation.value
        for violation in case.expected.policy_violations
        if violation not in actual_violations
    ]
    if missing_violations:
        failures.append(f"missingPolicyViolations={missing_violations}")
    return PipelineCaseResult(
        case_id=case.case_id,
        passed=not failures,
        llm_called=provider.called,
        actual_result_types=actual_result_types,
        candidate_count=len(response.candidates),
        question_count=len(response.questions),
        information_need=response.information_need,
        conflict_count=len(conflict_candidates),
        failures=failures,
    )


async def run_pipeline_eval(
    cases: List[PipelineEvalCase],
    dataset_name: str,
) -> PipelineEvalReport:
    results = [await evaluate_pipeline_case(case) for case in cases]
    passed = sum(result.passed for result in results)
    return PipelineEvalReport(
        dataset=dataset_name,
        total=len(results),
        passed=passed,
        failed=len(results) - passed,
        pass_rate=passed / len(results) if results else 0,
        results=results,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run LogFolio full pipeline eval")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output-json", type=Path)
    args = parser.parse_args()
    dataset_name, cases = load_pipeline_cases(args.dataset)
    report = asyncio.run(run_pipeline_eval(cases, dataset_name))
    rendered = report.model_dump_json(indent=2, by_alias=True)
    print(rendered)
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(rendered + "\n", encoding="utf-8")
    raise SystemExit(0 if report.failed == 0 else 1)


if __name__ == "__main__":
    main()
