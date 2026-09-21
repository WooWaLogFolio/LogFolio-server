from fastapi import APIRouter, Depends

from logfolio_ai.llm import LLMProvider, get_llm_provider
from logfolio_ai.models import AnalysisRequest, AnalysisResponse

router = APIRouter(prefix="/analyses", tags=["analyses"])


@router.post("", response_model=AnalysisResponse)
async def create_analysis(
    request: AnalysisRequest,
    provider: LLMProvider = Depends(get_llm_provider),
) -> AnalysisResponse:
    """Analyze extracted project text through the configured LLM provider."""

    return await provider.analyze(request)
