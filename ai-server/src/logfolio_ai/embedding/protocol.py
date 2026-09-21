from typing import List, Protocol, Sequence


class EmbeddingProvider(Protocol):
    @property
    def dimension(self) -> int:
        """Return the vector dimension produced by this provider."""

    async def embed_documents(self, texts: Sequence[str]) -> List[List[float]]:
        """Embed source passages for storage."""

    async def embed_query(self, text: str) -> List[float]:
        """Embed a retrieval query using the provider's query convention."""

