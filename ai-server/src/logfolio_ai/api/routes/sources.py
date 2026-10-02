from fastapi import APIRouter, Depends

from logfolio_ai.analysis.dependencies import get_rag_service
from logfolio_ai.api.dependencies import require_internal_api_key
from logfolio_ai.models import SourceIndexRequest, SourceIndexResponse
from logfolio_ai.rag import RagService


router = APIRouter(prefix="/sources", tags=["sources"])


@router.post("/index", response_model=SourceIndexResponse)
async def index_sources(
    request: SourceIndexRequest,
    rag_service: RagService = Depends(get_rag_service),
    _: None = Depends(require_internal_api_key),
) -> SourceIndexResponse:
    """Index Project Files and Quick Logs independently from analysis."""

    return await rag_service.index_sources(request.project_id, request.sources)
