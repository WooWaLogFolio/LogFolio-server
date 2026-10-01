from uuid import uuid4

import pytest

from logfolio_ai.chunking import DocumentChunk
from logfolio_ai.vector_store import MemoryVectorStore


def chunk(text: str) -> DocumentChunk:
    return DocumentChunk(
        chunk_id=uuid4(),
        project_file_id=uuid4(),
        original_name="project.pdf",
        sequence=0,
        page_number=1,
        char_start=0,
        char_end=len(text),
        token_count=1,
        text=text,
    )


@pytest.mark.asyncio
async def test_memory_search_isolated_by_project() -> None:
    store = MemoryVectorStore()
    first_project = uuid4()
    second_project = uuid4()
    first = chunk("첫 번째 프로젝트")
    second = chunk("두 번째 프로젝트")

    await store.replace_source_chunks(
        first_project,
        first.project_file_id,
        [first],
        [[1.0, 0.0]],
        embedding_model="fake",
    )
    await store.replace_source_chunks(
        second_project,
        second.project_file_id,
        [second],
        [[1.0, 0.0]],
        embedding_model="fake",
    )

    results = await store.search(first_project, [1.0, 0.0])

    assert [result.chunk_id for result in results] == [first.chunk_id]


@pytest.mark.asyncio
async def test_memory_store_ranks_by_cosine_distance() -> None:
    store = MemoryVectorStore()
    project_id = uuid4()
    close = chunk("가까운 문서")
    far = chunk("먼 문서")

    await store.replace_source_chunks(
        project_id,
        close.project_file_id,
        [close],
        [[1.0, 0.0]],
        embedding_model="fake",
    )
    await store.replace_source_chunks(
        project_id,
        far.project_file_id,
        [far],
        [[0.0, 1.0]],
        embedding_model="fake",
    )

    results = await store.search(project_id, [1.0, 0.0], top_k=1)

    assert [result.chunk_id for result in results] == [close.chunk_id]
    assert results[0].distance == pytest.approx(0.0)
