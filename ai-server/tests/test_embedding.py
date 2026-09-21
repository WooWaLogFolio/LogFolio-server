import math
from typing import List

import pytest

from logfolio_ai.core.config import Settings
from logfolio_ai.embedding.e5 import E5EmbeddingProvider
from logfolio_ai.embedding.factory import build_embedding_provider
from logfolio_ai.embedding.fake import FakeEmbeddingProvider


class RecordingModel:
    def __init__(self) -> None:
        self.calls: List[dict] = []

    def get_sentence_embedding_dimension(self) -> int:
        return 3

    def encode(self, texts: List[str], **kwargs: object) -> List[List[float]]:
        self.calls.append({"texts": texts, **kwargs})
        return [[1.0, 0.0, 0.0] for _ in texts]


@pytest.mark.asyncio
async def test_fake_embedding_is_deterministic_and_normalized() -> None:
    provider = FakeEmbeddingProvider(dimension=8)

    first = await provider.embed_query("사용자의 기여")
    second = await provider.embed_query("사용자의 기여")

    assert first == second
    assert len(first) == 8
    assert math.sqrt(sum(value * value for value in first)) == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_e5_uses_passage_and_query_prefixes() -> None:
    model = RecordingModel()
    provider = E5EmbeddingProvider("test-model", batch_size=4, model=model)

    document_vectors = await provider.embed_documents(["JWT 인증을 구현했다."])
    query_vector = await provider.embed_query("사용자의 기여")

    assert model.calls[0]["texts"] == ["passage: JWT 인증을 구현했다."]
    assert model.calls[1]["texts"] == ["query: 사용자의 기여"]
    assert model.calls[0]["normalize_embeddings"] is True
    assert model.calls[0]["batch_size"] == 4
    assert document_vectors == [[1.0, 0.0, 0.0]]
    assert query_vector == [1.0, 0.0, 0.0]
    assert provider.dimension == 3


@pytest.mark.asyncio
async def test_empty_document_batch_does_not_call_model() -> None:
    model = RecordingModel()
    provider = E5EmbeddingProvider("test-model", model=model)

    assert await provider.embed_documents([]) == []
    assert model.calls == []


def test_factory_defaults_to_fake_embedding() -> None:
    provider = build_embedding_provider(Settings())

    assert isinstance(provider, FakeEmbeddingProvider)
