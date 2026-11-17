import asyncio

from fastapi import APIRouter, Depends

from logfolio_ai.analysis import AnalysisOrchestrator
from logfolio_ai.analysis.dependencies import get_analysis_orchestrator
from logfolio_ai.api.dependencies import require_internal_api_key
from logfolio_ai.core.config import Settings, get_settings
from logfolio_ai.core.errors import AppError, COMMON_ERROR_RESPONSES
from logfolio_ai.models import AnalysisRequest
from logfolio_ai.models.refinement import (
    ExperienceRefinementRequest,
    ExperienceRefinementResponse,
    refinement_response,
)

router = APIRouter(prefix="/experience-refinements", tags=["experience-refinements"])


@router.post(
    "",
    response_model=ExperienceRefinementResponse,
    responses=COMMON_ERROR_RESPONSES,
)
async def create_experience_refinement(
    request: ExperienceRefinementRequest,
    orchestrator: AnalysisOrchestrator = Depends(get_analysis_orchestrator),
    settings: Settings = Depends(get_settings),
    _: None = Depends(require_internal_api_key),
) -> ExperienceRefinementResponse:
    """Return review proposals for one Experience; Spring owns persistence and status."""

    analysis_request = AnalysisRequest(
        analysis_run_id=request.review_session_id,
        project_id=request.project_id,
        source_ids=request.source_ids,
        project_context=request.project_context,
        existing_experiences=[request.experience],
        corrections=request.corrections,
        answers=request.answers,
    )
    try:
        analysis = await asyncio.wait_for(
            orchestrator.analyze(analysis_request),
            timeout=settings.analysis_timeout_seconds,
        )
    except asyncio.TimeoutError as exc:
        raise AppError(
            code="REFINEMENT_TIMEOUT",
            message="AI 경험 다듬기 제한 시간을 초과했습니다.",
            status_code=504,
        ) from exc
    return refinement_response(request, analysis)
