from fastapi import APIRouter

from logfolio_ai.models import AnalysisRequest, AnalysisResponse

router = APIRouter(prefix="/analyses", tags=["analyses"])


@router.post("", response_model=AnalysisResponse)
async def create_analysis(request: AnalysisRequest) -> AnalysisResponse:
    """Validate an analysis request and return a contract-compatible stub."""

    return AnalysisResponse(
        analysis_run_id=request.analysis_run_id,
        project_id=request.project_id,
        summary="AI 분석 기능 연결 전 임시 응답입니다.",
        candidates=[],
        questions=[],
    )
