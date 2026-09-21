import asyncio
from typing import Any, List, Optional, Sequence

from logfolio_ai.core.errors import AppError


class E5EmbeddingProvider:
    """Local multilingual E5 embeddings with the required passage/query prefixes."""

    def __init__(
        self,
        model_name: str,
        batch_size: int = 16,
        model: Optional[Any] = None,
    ) -> None:
        if model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise AppError(
                    code="EMBEDDING_DEPENDENCY_MISSING",
                    message="로컬 Embedding 실행 패키지가 설치되지 않았습니다.",
                    status_code=500,
                ) from exc
            model = SentenceTransformer(model_name)

        self._model = model
        self._batch_size = batch_size

    @property
    def dimension(self) -> int:
        return int(self._model.get_sentence_embedding_dimension())

    def _encode(self, texts: Sequence[str]) -> List[List[float]]:
        vectors = self._model.encode(
            list(texts),
            batch_size=self._batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return [[float(value) for value in vector] for vector in vectors]

    async def embed_documents(self, texts: Sequence[str]) -> List[List[float]]:
        if not texts:
            return []
        prefixed = [f"passage: {text}" for text in texts]
        try:
            return await asyncio.to_thread(self._encode, prefixed)
        except Exception as exc:
            raise AppError(
                code="EMBEDDING_ERROR",
                message="문서 Embedding 생성에 실패했습니다.",
                status_code=500,
            ) from exc

    async def embed_query(self, text: str) -> List[float]:
        try:
            vectors = await asyncio.to_thread(self._encode, [f"query: {text}"])
            return vectors[0]
        except Exception as exc:
            raise AppError(
                code="EMBEDDING_ERROR",
                message="검색 Query Embedding 생성에 실패했습니다.",
                status_code=500,
            ) from exc
