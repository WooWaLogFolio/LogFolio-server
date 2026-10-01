from typing import List, Protocol, Sequence
from uuid import UUID

from logfolio_ai.chunking import DocumentChunk
from logfolio_ai.vector_store.models import VectorSearchResult


class VectorStore(Protocol):
    async def replace_source_chunks(
        self,
        project_id: UUID,
        project_file_id: UUID,
        chunks: Sequence[DocumentChunk],
        embeddings: Sequence[Sequence[float]],
        *,
        embedding_model: str,
    ) -> None:
        """Atomically replace all stored chunks for one project file."""

    async def search(
        self,
        project_id: UUID,
        query_embedding: Sequence[float],
        *,
        top_k: int = 5,
    ) -> List[VectorSearchResult]:
        """Search only within one authorized project."""
