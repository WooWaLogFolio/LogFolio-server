from fastapi import APIRouter, Depends

from logfolio_ai.analysis import AnalysisOrchestrator
from logfolio_ai.analysis.dependencies import get_analysis_orchestrator
from logfolio_ai.models import AnalysisRequest, AnalysisResponse

router = APIRouter(prefix="/analyses", tags=["analyses"])


@router.post("", response_model=AnalysisResponse)
async def create_analysis(
    request: AnalysisRequest,
    orchestrator: AnalysisOrchestrator = Depends(get_analysis_orchestrator),
) -> AnalysisResponse:
    """Index, retrieve, and analyze project evidence through the RAG pipeline."""

    return await orchestrator.analyze(request)
