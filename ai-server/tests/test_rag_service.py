from typing import List, Sequence
from uuid import UUID, uuid4

import pytest

from logfolio_ai.chunking import DocumentChunk
from logfolio_ai.models import DocumentPage, DocumentSource
from logfolio_ai.rag import AnalysisPurpose, RagService
from logfolio_ai.vector_store import VectorSearchResult


class RecordingEmbeddingProvider:
    dimension = 3

    def __init__(self) -> None:
        self.document_calls: List[List[str]] = []
        self.query_calls: List[str] = []
        self.query_batch_calls: List[List[str]] = []

    async def embed_documents(self, texts: Sequence[str]) -> List[List[float]]:
        self.document_calls.append(list(texts))
        return [[1.0, 0.0, 0.0] for _ in texts]

    async def embed_query(self, text: str) -> List[float]:
        self.query_calls.append(text)
        return [0.0, 1.0, 0.0]

    async def embed_queries(self, texts: Sequence[str]) -> List[List[float]]:
        self.query_batch_calls.append(list(texts))
        return [[0.0, 1.0, 0.0] for _ in texts]


class RecordingVectorStore:
    def __init__(self) -> None:
        self.replace_calls: List[dict] = []
        self.search_calls: List[dict] = []
        self.results: List[VectorSearchResult] = []

    async def replace_source_chunks(
        self,
        project_id: UUID,
        project_file_id: UUID,
        chunks: Sequence[DocumentChunk],
        embeddings: Sequence[Sequence[float]],
        *,
        embedding_model: str,
    ) -> None:
        self.replace_calls.append(
            {
                "project_id": project_id,
                "project_file_id": project_file_id,
                "chunks": list(chunks),
                "embeddings": list(embeddings),
                "embedding_model": embedding_model,
            }
        )

    async def search(
        self,
        project_id: UUID,
        query_embedding: Sequence[float],
        *,
        top_k: int = 5,
    ) -> List[VectorSearchResult]:
        self.search_calls.append(
            {
                "project_id": project_id,
                "query_embedding": list(query_embedding),
                "top_k": top_k,
            }
        )
        return self.results


def source(text: str = "JWT 인증 API를 구현했다.") -> DocumentSource:
    return DocumentSource(
        project_file_id=uuid4(),
        original_name="project.pdf",
        pages=[DocumentPage(page_number=1, text=text)],
    )


def rag_service(
    embedding: RecordingEmbeddingProvider,
    store: RecordingVectorStore,
) -> RagService:
    return RagService(
        embedding,
        store,
        embedding_model="test-e5",
        chunk_size_tokens=10,
        chunk_overlap_tokens=2,
        top_k=5,
    )


@pytest.mark.asyncio
async def test_index_connects_chunking_embedding_and_atomic_source_replace() -> None:
    embedding = RecordingEmbeddingProvider()
    store = RecordingVectorStore()
    service = rag_service(embedding, store)
    project_id = uuid4()
    document = source()

    result = await service.index_documents(project_id, [document])

    assert result.document_count == 1
    assert result.chunk_count == 1
    assert embedding.document_calls == [["JWT 인증 API를 구현했다."]]
    assert store.replace_calls[0]["project_id"] == project_id
    assert store.replace_calls[0]["project_file_id"] == document.project_file_id
    assert store.replace_calls[0]["embedding_model"] == "test-e5"


@pytest.mark.asyncio
async def test_retrieve_embeds_query_and_keeps_project_scope() -> None:
    embedding = RecordingEmbeddingProvider()
    store = RecordingVectorStore()
    service = rag_service(embedding, store)
    project_id = uuid4()

    await service.retrieve(project_id, "  사용자의 기여  ", top_k=3)

    assert embedding.query_calls == ["사용자의 기여"]
    assert store.search_calls == [
        {
            "project_id": project_id,
            "query_embedding": [0.0, 1.0, 0.0],
            "top_k": 3,
        }
    ]


@pytest.mark.asyncio
async def test_analysis_context_uses_five_distinct_purposes() -> None:
    embedding = RecordingEmbeddingProvider()
    store = RecordingVectorStore()
    service = rag_service(embedding, store)

    contexts = await service.retrieve_analysis_context(uuid4())

    assert [context.purpose for context in contexts] == list(AnalysisPurpose)
    assert len(embedding.query_batch_calls) == 1
    assert len(set(embedding.query_batch_calls[0])) == 5
    assert len(store.search_calls) == 5


@pytest.mark.asyncio
async def test_blank_query_is_rejected_before_embedding() -> None:
    embedding = RecordingEmbeddingProvider()
    store = RecordingVectorStore()
    service = rag_service(embedding, store)

    with pytest.raises(ValueError):
        await service.retrieve(uuid4(), "   ")

    assert embedding.query_calls == []
    assert store.search_calls == []
