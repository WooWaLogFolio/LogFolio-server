import math
from typing import Any, List, Optional, Sequence
from uuid import UUID

from logfolio_ai.chunking import DocumentChunk
from logfolio_ai.core.errors import AppError
from logfolio_ai.vector_store.models import VectorSearchResult

_UPSERT_SQL = """
INSERT INTO ai_document_chunks (
    chunk_id, project_id, source_id, source_type, source_name, sequence, page_number,
    section_title, char_start, char_end, token_count, content, embedding,
    embedding_model, content_hash
) VALUES (
    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15
)
ON CONFLICT (chunk_id) DO UPDATE SET
    project_id = EXCLUDED.project_id,
    source_id = EXCLUDED.source_id,
    source_type = EXCLUDED.source_type,
    source_name = EXCLUDED.source_name,
    sequence = EXCLUDED.sequence,
    page_number = EXCLUDED.page_number,
    section_title = EXCLUDED.section_title,
    char_start = EXCLUDED.char_start,
    char_end = EXCLUDED.char_end,
    token_count = EXCLUDED.token_count,
    content = EXCLUDED.content,
    embedding = EXCLUDED.embedding,
    embedding_model = EXCLUDED.embedding_model,
    content_hash = EXCLUDED.content_hash,
    updated_at = CURRENT_TIMESTAMP
"""

_SEARCH_SQL = """
SELECT
    chunk_id, source_id, source_type, source_name, sequence, page_number, section_title,
    char_start, char_end, content, embedding <=> $2 AS distance
FROM ai_document_chunks
WHERE project_id = $1
  AND ($4::uuid[] IS NULL OR source_id = ANY($4::uuid[]))
ORDER BY embedding <=> $2
LIMIT $3
"""

_DELETE_PROJECT_SQL = """
DELETE FROM ai_document_chunks
WHERE project_id = $1
"""

_DELETE_SOURCE_SQL = """
DELETE FROM ai_document_chunks
WHERE project_id = $1 AND source_id = $2
"""

_GET_CHUNKS_SQL = """
SELECT
    chunk_id, source_id, source_type, source_name, sequence, page_number,
    section_title, char_start, char_end, token_count, content
FROM ai_document_chunks
WHERE project_id = $1 AND chunk_id = ANY($2::uuid[])
ORDER BY chunk_id
"""

_GET_SOURCE_CHUNKS_SQL = """
SELECT
    chunk_id, source_id, source_type, source_name, sequence, page_number,
    section_title, char_start, char_end, token_count, content
FROM ai_document_chunks
WHERE project_id = $1 AND source_id = ANY($2::uuid[])
ORDER BY source_id, sequence
LIMIT $3
"""

_FIND_SOURCE_BY_CONTENT_HASH_SQL = """
SELECT source_id
FROM ai_document_chunks
WHERE project_id = $1 AND content_hash = $2
ORDER BY sequence
LIMIT 1
"""


class PgVectorStore:
    def __init__(self, pool: Any, *, vector_dimension: int = 768) -> None:
        self._pool = pool
        self._vector_dimension = vector_dimension

    @classmethod
    async def connect(
        cls,
        database_url: str,
        *,
        vector_dimension: int = 768,
    ) -> "PgVectorStore":
        import asyncpg
        from pgvector.asyncpg import register_vector

        try:
            pool = await asyncpg.create_pool(
                database_url,
                init=register_vector,
            )
        except Exception as exc:
            raise AppError(
                code="VECTOR_STORE_CONNECTION_ERROR",
                message="Vector DB 연결에 실패했습니다.",
                status_code=503,
            ) from exc
        return cls(pool, vector_dimension=vector_dimension)

    async def close(self) -> None:
        await self._pool.close()

    def _validate_vector(self, vector: Sequence[float]) -> List[float]:
        if len(vector) != self._vector_dimension:
            raise AppError(
                code="EMBEDDING_DIMENSION_MISMATCH",
                message="Embedding 차원이 Vector DB 계약과 일치하지 않습니다.",
                status_code=500,
            )
        values = [float(value) for value in vector]
        if not all(math.isfinite(value) for value in values):
            raise AppError(
                code="INVALID_EMBEDDING_VALUE",
                message="Embedding에는 유한한 숫자만 포함할 수 있습니다.",
                status_code=500,
            )
        return values

    async def upsert_chunks(
        self,
        project_id: UUID,
        chunks: Sequence[DocumentChunk],
        embeddings: Sequence[Sequence[float]],
        *,
        embedding_model: str,
        content_hash: Optional[str] = None,
    ) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings must have the same length")
        if not chunks:
            return

        rows = [
            (
                chunk.chunk_id,
                project_id,
                chunk.source_id,
                chunk.source_type.value,
                chunk.source_name,
                chunk.sequence,
                chunk.page_number,
                chunk.section_title,
                chunk.char_start,
                chunk.char_end,
                chunk.token_count,
                chunk.text,
                self._validate_vector(embedding),
                embedding_model,
                content_hash,
            )
            for chunk, embedding in zip(chunks, embeddings)
        ]
        try:
            async with self._pool.acquire() as connection:
                async with connection.transaction():
                    await connection.executemany(_UPSERT_SQL, rows)
        except AppError:
            raise
        except Exception as exc:
            raise AppError(
                code="VECTOR_STORE_WRITE_ERROR",
                message="문서 Chunk 저장에 실패했습니다.",
                status_code=503,
            ) from exc

    async def replace_source_chunks(
        self,
        project_id: UUID,
        source_id: UUID,
        chunks: Sequence[DocumentChunk],
        embeddings: Sequence[Sequence[float]],
        *,
        embedding_model: str,
        content_hash: Optional[str] = None,
    ) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings must have the same length")
        if any(chunk.source_id != source_id for chunk in chunks):
            raise ValueError("every chunk must belong to source_id")

        rows = [
            (
                chunk.chunk_id,
                project_id,
                chunk.source_id,
                chunk.source_type.value,
                chunk.source_name,
                chunk.sequence,
                chunk.page_number,
                chunk.section_title,
                chunk.char_start,
                chunk.char_end,
                chunk.token_count,
                chunk.text,
                self._validate_vector(embedding),
                embedding_model,
                content_hash,
            )
            for chunk, embedding in zip(chunks, embeddings)
        ]

        try:
            async with self._pool.acquire() as connection:
                async with connection.transaction():
                    await connection.execute(_DELETE_SOURCE_SQL, project_id, source_id)
                    if rows:
                        await connection.executemany(_UPSERT_SQL, rows)
        except AppError:
            raise
        except Exception as exc:
            raise AppError(
                code="VECTOR_STORE_WRITE_ERROR",
                message="파일 Chunk 교체에 실패했습니다.",
                status_code=503,
            ) from exc

    async def find_source_by_content_hash(
        self,
        project_id: UUID,
        content_hash: str,
    ) -> Optional[UUID]:
        try:
            row = await self._pool.fetchrow(
                _FIND_SOURCE_BY_CONTENT_HASH_SQL,
                project_id,
                content_hash,
            )
        except Exception as exc:
            raise AppError(
                code="VECTOR_STORE_ERROR",
                message="중복 Source 조회에 실패했습니다.",
                status_code=503,
            ) from exc
        return row["source_id"] if row is not None else None

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
        vector = self._validate_vector(query_embedding)
        try:
            source_filter = list(source_ids) if source_ids else None
            rows = await self._pool.fetch(
                _SEARCH_SQL,
                project_id,
                vector,
                top_k,
                source_filter,
            )
        except AppError:
            raise
        except Exception as exc:
            raise AppError(
                code="VECTOR_STORE_SEARCH_ERROR",
                message="관련 문서 검색에 실패했습니다.",
                status_code=503,
            ) from exc

        return [
            VectorSearchResult(
                chunk_id=row["chunk_id"],
                source_id=row["source_id"],
                source_type=row["source_type"],
                source_name=row["source_name"],
                sequence=row["sequence"],
                page_number=row["page_number"],
                section_title=row["section_title"],
                char_start=row["char_start"],
                char_end=row["char_end"],
                text=row["content"],
                distance=float(row["distance"]),
            )
            for row in rows
        ]

    async def get_chunks(
        self,
        project_id: UUID,
        chunk_ids: Sequence[UUID],
    ) -> List[DocumentChunk]:
        if not chunk_ids:
            return []
        try:
            rows = await self._pool.fetch(_GET_CHUNKS_SQL, project_id, list(chunk_ids))
        except Exception as exc:
            raise AppError(
                code="VECTOR_STORE_ERROR",
                message="기존 경험 근거 조회에 실패했습니다.",
                status_code=503,
            ) from exc
        return [
            DocumentChunk(
                chunk_id=row["chunk_id"],
                source_id=row["source_id"],
                source_type=row["source_type"],
                source_name=row["source_name"],
                sequence=row["sequence"],
                page_number=row["page_number"],
                section_title=row["section_title"],
                char_start=row["char_start"],
                char_end=row["char_end"],
                token_count=row["token_count"],
                text=row["content"],
            )
            for row in rows
        ]

    async def get_source_chunks(
        self,
        project_id: UUID,
        source_ids: Sequence[UUID],
        *,
        limit: int,
    ) -> List[DocumentChunk]:
        if not source_ids or limit < 1:
            return []
        try:
            rows = await self._pool.fetch(
                _GET_SOURCE_CHUNKS_SQL,
                project_id,
                list(source_ids),
                limit,
            )
        except Exception as exc:
            raise AppError(
                code="VECTOR_STORE_ERROR",
                message="새 Source 원문 조회에 실패했습니다.",
                status_code=503,
            ) from exc
        return [
            DocumentChunk(
                chunk_id=row["chunk_id"],
                source_id=row["source_id"],
                source_type=row["source_type"],
                source_name=row["source_name"],
                sequence=row["sequence"],
                page_number=row["page_number"],
                section_title=row["section_title"],
                char_start=row["char_start"],
                char_end=row["char_end"],
                token_count=row["token_count"],
                text=row["content"],
            )
            for row in rows
        ]

    async def delete_project(self, project_id: UUID) -> None:
        try:
            await self._pool.execute(_DELETE_PROJECT_SQL, project_id)
        except Exception as exc:
            raise AppError(
                code="VECTOR_STORE_DELETE_ERROR",
                message="프로젝트 Chunk 삭제에 실패했습니다.",
                status_code=503,
            ) from exc

    async def delete_source(self, project_id: UUID, source_id: UUID) -> None:
        try:
            await self._pool.execute(_DELETE_SOURCE_SQL, project_id, source_id)
        except Exception as exc:
            raise AppError(
                code="VECTOR_STORE_DELETE_ERROR",
                message="파일 Chunk 삭제에 실패했습니다.",
                status_code=503,
            ) from exc
