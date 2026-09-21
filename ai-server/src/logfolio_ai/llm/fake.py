from logfolio_ai.models import AnalysisRequest, AnalysisResponse


class FakeLLMProvider:
    """Deterministic provider for local development and contract tests."""

    async def analyze(self, request: AnalysisRequest) -> AnalysisResponse:
        return AnalysisResponse(
            analysis_run_id=request.analysis_run_id,
            project_id=request.project_id,
            summary="Fake LLM 분석 결과입니다.",
            candidates=[],
            questions=[],
        )
