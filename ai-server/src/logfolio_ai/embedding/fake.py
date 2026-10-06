import hashlib
import math
from typing import List, Sequence


class FakeEmbeddingProvider:
    """Small deterministic vectors for tests; not suitable for semantic search."""

    def __init__(self, dimension: int = 8) -> None:
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    def _embed(self, text: str) -> List[float]:
        values = bytearray()
        counter = 0
        while len(values) < self._dimension:
            values.extend(
                hashlib.sha256(f"{counter}:{text}".encode("utf-8")).digest()
            )
            counter += 1
        raw = [value / 127.5 - 1.0 for value in values[: self._dimension]]
        norm = math.sqrt(sum(value * value for value in raw)) or 1.0
        return [value / norm for value in raw]

    async def embed_documents(self, texts: Sequence[str]) -> List[List[float]]:
        return [self._embed(f"passage: {text}") for text in texts]

    async def embed_query(self, text: str) -> List[float]:
        return self._embed(f"query: {text}")

    async def embed_queries(self, texts: Sequence[str]) -> List[List[float]]:
        return [self._embed(f"query: {text}") for text in texts]
