from logfolio_ai.llm.models import GroundedAnalysisInput
from logfolio_ai.models import AnalysisResponse


class FakeLLMProvider:
    """Deterministic provider for local development and contract tests."""

    async def analyze_grounded(
        self, request: GroundedAnalysisInput
    ) -> AnalysisResponse:
        return AnalysisResponse(
            analysis_run_id=request.analysis_run_id,
            project_id=request.project_id,
            summary="Fake LLM 근거 기반 분석 결과입니다.",
            candidates=[],
            questions=[],
        )
