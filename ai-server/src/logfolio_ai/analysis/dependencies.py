from functools import lru_cache
from typing import AsyncIterator

from logfolio_ai.analysis.orchestrator import AnalysisOrchestrator
from logfolio_ai.core.config import get_settings
from logfolio_ai.embedding import get_embedding_provider
from logfolio_ai.llm import get_llm_provider
from logfolio_ai.rag import RagService
from logfolio_ai.vector_store import MemoryVectorStore, PgVectorStore, VectorStore


@lru_cache
def _memory_vector_store() -> MemoryVectorStore:
    return MemoryVectorStore()


async def get_rag_service() -> AsyncIterator[RagService]:
    settings = get_settings()
    vector_store: VectorStore
    pg_store = None

    database_url = (
        settings.database_url.get_secret_value().strip()
        if settings.database_url is not None
        else ""
    )
    if not database_url:
        vector_store = _memory_vector_store()
    else:
        pg_store = await PgVectorStore.connect(
            database_url,
            vector_dimension=settings.vector_dimension,
        )
        vector_store = pg_store

    service = RagService(
        get_embedding_provider(),
        vector_store,
        embedding_model=settings.embedding_model,
        chunk_size_tokens=settings.chunk_size_tokens,
        chunk_overlap_tokens=settings.chunk_overlap_tokens,
        top_k=settings.retrieval_top_k,
        existing_experience_match_distance=settings.existing_experience_match_distance,
        max_related_experiences=settings.max_related_experiences,
    )
    try:
        yield service
    finally:
        if pg_store is not None:
            await pg_store.close()


async def get_analysis_orchestrator() -> AsyncIterator[AnalysisOrchestrator]:
    settings = get_settings()
    async for rag_service in get_rag_service():
        yield AnalysisOrchestrator(
            rag_service,
            get_llm_provider(),
            max_grounded_chunks=settings.max_grounded_chunks,
        )
