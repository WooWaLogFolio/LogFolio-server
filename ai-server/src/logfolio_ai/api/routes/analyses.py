import asyncio

from fastapi import APIRouter, Depends

from logfolio_ai.analysis import AnalysisOrchestrator
from logfolio_ai.analysis.dependencies import get_analysis_orchestrator
from logfolio_ai.api.dependencies import require_internal_api_key
from logfolio_ai.core.config import Settings, get_settings
from logfolio_ai.core.errors import AppError
from logfolio_ai.models import AnalysisRequest, AnalysisResponse

router = APIRouter(prefix="/analyses", tags=["analyses"])


@router.post("", response_model=AnalysisResponse)
async def create_analysis(
    request: AnalysisRequest,
    orchestrator: AnalysisOrchestrator = Depends(get_analysis_orchestrator),
    settings: Settings = Depends(get_settings),
    _: None = Depends(require_internal_api_key),
) -> AnalysisResponse:
    """Index, retrieve, and analyze project evidence through the RAG pipeline."""

    try:
        return await asyncio.wait_for(
            orchestrator.analyze(request),
            timeout=settings.analysis_timeout_seconds,
        )
    except asyncio.TimeoutError as exc:
        raise AppError(
            code="ANALYSIS_TIMEOUT",
            message="AI 분석 제한 시간을 초과했습니다.",
            status_code=504,
        ) from exc
