import asyncio
import math
from typing import Dict, List, Optional, Sequence, Tuple
from uuid import UUID

from logfolio_ai.chunking import DocumentChunk
from logfolio_ai.vector_store.models import VectorSearchResult


class MemoryVectorStore:
    """Process-local Vector Store for development and end-to-end contract tests."""

    def __init__(self) -> None:
        self._sources: Dict[
            Tuple[UUID, UUID], List[Tuple[DocumentChunk, List[float]]]
        ] = {}
        self._lock = asyncio.Lock()

    async def replace_source_chunks(
        self,
        project_id: UUID,
        source_id: UUID,
        chunks: Sequence[DocumentChunk],
        embeddings: Sequence[Sequence[float]],
        *,
        embedding_model: str,
    ) -> None:
        del embedding_model
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings must have the same length")
        if any(chunk.source_id != source_id for chunk in chunks):
            raise ValueError("every chunk must belong to source_id")
        values = [
            (chunk, [float(value) for value in embedding])
            for chunk, embedding in zip(chunks, embeddings)
        ]
        async with self._lock:
            self._sources[(project_id, source_id)] = values

    @staticmethod
    def _cosine_distance(left: Sequence[float], right: Sequence[float]) -> float:
        if len(left) != len(right):
            raise ValueError("embedding dimensions must match")
        left_norm = math.sqrt(sum(value * value for value in left))
        right_norm = math.sqrt(sum(value * value for value in right))
        if left_norm == 0 or right_norm == 0:
            return 1.0
        similarity = sum(a * b for a, b in zip(left, right)) / (
            left_norm * right_norm
        )
        return max(0.0, 1.0 - similarity)

    async def search(
        self,
        project_id: UUID,
        query_embedding: Sequence[float],
        *,
        top_k: int = 5,
        source_ids: Optional[Sequence[UUID]] = None,
    ) -> List[VectorSearchResult]:
        if top_k < 1 or top_k > 20:
            raise ValueError("top_k must be between 1 and 20")
        async with self._lock:
            allowed_source_ids = set(source_ids) if source_ids else None
            project_rows = [
                item
                for (stored_project_id, stored_source_id), items in self._sources.items()
                if stored_project_id == project_id
                and (
                    allowed_source_ids is None
                    or stored_source_id in allowed_source_ids
                )
                for item in items
            ]
        ranked = sorted(
            (
                (self._cosine_distance(embedding, query_embedding), chunk)
                for chunk, embedding in project_rows
            ),
            key=lambda item: (item[0], str(item[1].chunk_id)),
        )[:top_k]
        return [
            VectorSearchResult(
                chunk_id=chunk.chunk_id,
                source_id=chunk.source_id,
                source_type=chunk.source_type,
                source_name=chunk.source_name,
                sequence=chunk.sequence,
                page_number=chunk.page_number,
                section_title=chunk.section_title,
                char_start=chunk.char_start,
                char_end=chunk.char_end,
                text=chunk.text,
                distance=distance,
            )
            for distance, chunk in ranked
        ]

    async def delete_source(self, project_id: UUID, source_id: UUID) -> None:
        async with self._lock:
            self._sources.pop((project_id, source_id), None)

    async def get_chunks(
        self,
        project_id: UUID,
        chunk_ids: Sequence[UUID],
    ) -> List[DocumentChunk]:
        requested = set(chunk_ids)
        if not requested:
            return []
        async with self._lock:
            chunks = [
                chunk
                for (stored_project_id, _), items in self._sources.items()
                if stored_project_id == project_id
                for chunk, _ in items
                if chunk.chunk_id in requested
            ]
        chunks.sort(key=lambda chunk: str(chunk.chunk_id))
        return chunks

    async def get_source_chunks(
        self,
        project_id: UUID,
        source_ids: Sequence[UUID],
        *,
        limit: int,
    ) -> List[DocumentChunk]:
        requested = set(source_ids)
        if not requested or limit < 1:
            return []
        async with self._lock:
            chunks = [
                chunk
                for (stored_project_id, stored_source_id), items in self._sources.items()
                if stored_project_id == project_id and stored_source_id in requested
                for chunk, _ in items
            ]
        chunks.sort(key=lambda chunk: (str(chunk.source_id), chunk.sequence))
        return chunks[:limit]

    async def delete_project(self, project_id: UUID) -> None:
        async with self._lock:
            keys = [key for key in self._sources if key[0] == project_id]
            for key in keys:
                del self._sources[key]
