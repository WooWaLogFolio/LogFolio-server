from functools import lru_cache

from logfolio_ai.core.config import Settings, get_settings
from logfolio_ai.embedding.e5 import E5EmbeddingProvider
from logfolio_ai.embedding.fake import FakeEmbeddingProvider
from logfolio_ai.embedding.protocol import EmbeddingProvider


def build_embedding_provider(settings: Settings) -> EmbeddingProvider:
    if settings.embedding_provider == "fake":
        return FakeEmbeddingProvider()
    return E5EmbeddingProvider(
        model_name=settings.embedding_model,
        batch_size=settings.embedding_batch_size,
    )


@lru_cache
def get_embedding_provider() -> EmbeddingProvider:
    return build_embedding_provider(get_settings())
