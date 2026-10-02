from uuid import UUID

from fastapi import APIRouter, Depends, Response, status

from logfolio_ai.analysis.dependencies import get_rag_service
from logfolio_ai.api.dependencies import require_internal_api_key
from logfolio_ai.models import SourceIndexRequest, SourceIndexResponse
from logfolio_ai.rag import RagService


router = APIRouter(prefix="/sources", tags=["sources"])
index_lifecycle_router = APIRouter(tags=["sources"])


@router.post("/index", response_model=SourceIndexResponse)
async def index_sources(
    request: SourceIndexRequest,
    rag_service: RagService = Depends(get_rag_service),
    _: None = Depends(require_internal_api_key),
) -> SourceIndexResponse:
    """Index Project Files and Quick Logs independently from analysis."""

    return await rag_service.index_sources(request.project_id, request.sources)


@index_lifecycle_router.delete(
    "/projects/{project_id}/sources/{source_id}/index",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_source_index(
    project_id: UUID,
    source_id: UUID,
    rag_service: RagService = Depends(get_rag_service),
    _: None = Depends(require_internal_api_key),
) -> Response:
    """Remove only the Source's RAG chunks after Spring authorizes deletion."""

    await rag_service.delete_source_index(project_id, source_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
