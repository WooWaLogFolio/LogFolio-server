from contextlib import asynccontextmanager
from typing import Any, List
from uuid import uuid4

import pytest

from logfolio_ai.chunking.models import DocumentChunk
from logfolio_ai.core.errors import AppError
from logfolio_ai.vector_store.pgvector_store import PgVectorStore


class FakeConnection:
    def __init__(self) -> None:
        self.executemany_calls: List[Any] = []

    @asynccontextmanager
    async def transaction(self):
        yield

    async def executemany(self, sql: str, rows: List[Any]) -> None:
        self.executemany_calls.append((sql, rows))


class FakePool:
    def __init__(self) -> None:
        self.connection = FakeConnection()
        self.fetch_calls: List[Any] = []
        self.execute_calls: List[Any] = []
        self.search_rows: List[dict] = []

    @asynccontextmanager
    async def acquire(self):
        yield self.connection

    async def fetch(self, sql: str, *args: Any) -> List[dict]:
        self.fetch_calls.append((sql, args))
        return self.search_rows

    async def execute(self, sql: str, *args: Any) -> None:
        self.execute_calls.append((sql, args))

    async def close(self) -> None:
        return None


def chunk() -> DocumentChunk:
    return DocumentChunk(
        chunk_id=uuid4(),
        source_id=uuid4(),
        file_name="project.pdf",
        sequence=0,
        page_number=1,
        section_title="인증 기능",
        char_start=0,
        char_end=10,
        token_count=3,
        text="JWT 인증 구현",
    )


@pytest.mark.asyncio
async def test_upsert_keeps_project_scope_and_chunk_metadata() -> None:
    pool = FakePool()
    store = PgVectorStore(pool, vector_dimension=3)
    project_id = uuid4()
    source_chunk = chunk()

    await store.upsert_chunks(
        project_id,
        [source_chunk],
        [[1.0, 0.0, 0.0]],
        embedding_model="test-model",
    )

    sql, rows = pool.connection.executemany_calls[0]
    assert "ON CONFLICT (chunk_id)" in sql
    assert rows[0][0] == source_chunk.chunk_id
    assert rows[0][1] == project_id
    assert rows[0][2] == source_chunk.source_id
    assert rows[0][11] == [1.0, 0.0, 0.0]


@pytest.mark.asyncio
async def test_search_always_filters_by_project_before_top_k() -> None:
    pool = FakePool()
    store = PgVectorStore(pool, vector_dimension=3)
    project_id = uuid4()
    result_chunk = chunk()
    pool.search_rows = [
        {
            "chunk_id": result_chunk.chunk_id,
            "source_id": result_chunk.source_id,
            "file_name": result_chunk.file_name,
            "sequence": 0,
            "page_number": 1,
            "section_title": "인증 기능",
            "char_start": 0,
            "char_end": 10,
            "content": "JWT 인증 구현",
            "distance": 0.12,
        }
    ]

    results = await store.search(project_id, [1.0, 0.0, 0.0], top_k=5)

    sql, args = pool.fetch_calls[0]
    assert "WHERE project_id = $1" in sql
    assert "ORDER BY embedding <=> $2" in sql
    assert args == (project_id, [1.0, 0.0, 0.0], 5)
    assert results[0].chunk_id == result_chunk.chunk_id
    assert results[0].distance == pytest.approx(0.12)


@pytest.mark.asyncio
async def test_dimension_mismatch_is_rejected_before_database_call() -> None:
    pool = FakePool()
    store = PgVectorStore(pool, vector_dimension=3)

    with pytest.raises(AppError) as error:
        await store.search(uuid4(), [1.0, 0.0], top_k=5)

    assert error.value.code == "EMBEDDING_DIMENSION_MISMATCH"
    assert pool.fetch_calls == []


@pytest.mark.asyncio
async def test_delete_is_scoped_to_one_project() -> None:
    pool = FakePool()
    store = PgVectorStore(pool, vector_dimension=3)
    project_id = uuid4()

    await store.delete_project(project_id)

    sql, args = pool.execute_calls[0]
    assert "WHERE project_id = $1" in sql
    assert args == (project_id,)


@pytest.mark.asyncio
async def test_source_delete_requires_both_project_and_source_scope() -> None:
    pool = FakePool()
    store = PgVectorStore(pool, vector_dimension=3)
    project_id = uuid4()
    source_id = uuid4()

    await store.delete_source(project_id, source_id)

    sql, args = pool.execute_calls[0]
    assert "WHERE project_id = $1 AND source_id = $2" in sql
    assert args == (project_id, source_id)


@pytest.mark.asyncio
async def test_non_finite_embedding_is_rejected() -> None:
    pool = FakePool()
    store = PgVectorStore(pool, vector_dimension=3)

    with pytest.raises(AppError) as error:
        await store.search(uuid4(), [1.0, float("nan"), 0.0])

    assert error.value.code == "INVALID_EMBEDDING_VALUE"
    assert pool.fetch_calls == []


@pytest.mark.asyncio
async def test_upsert_rejects_mismatched_chunk_and_embedding_counts() -> None:
    store = PgVectorStore(FakePool(), vector_dimension=3)

    with pytest.raises(ValueError):
        await store.upsert_chunks(
            uuid4(),
            [chunk()],
            [],
            embedding_model="test-model",
        )
