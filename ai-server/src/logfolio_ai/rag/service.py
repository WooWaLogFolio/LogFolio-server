import asyncio
import hashlib
from typing import Dict, Iterable, List, Optional, Sequence
from uuid import UUID

from logfolio_ai.chunking import DocumentChunk, chunk_documents
from logfolio_ai.core.errors import AppError
from logfolio_ai.embedding import EmbeddingProvider
from logfolio_ai.models import (
    DocumentSource,
    ExistingExperience,
    ProjectContext,
    SourceWarning,
    SourceIndexItem,
    SourceIndexResponse,
)
from logfolio_ai.rag.models import (
    AnalysisPurpose,
    ExistingExperienceContext,
    IndexingResult,
    RetrievalContext,
)
from logfolio_ai.vector_store import VectorSearchResult, VectorStore

DEFAULT_ANALYSIS_QUERIES: Dict[AnalysisPurpose, str] = {
    AnalysisPurpose.PROJECT_OVERVIEW: "프로젝트가 해결하려던 문제, 목적, 주요 기능과 진행 기간",
    AnalysisPurpose.USER_CONTRIBUTION: "사용자가 직접 담당하거나 수행한 역할, 행동과 개인 기여",
    AnalysisPurpose.DECISION_REASON: "핵심 의사결정, 선택한 방법과 그렇게 판단한 이유",
    AnalysisPurpose.OUTCOME: "프로젝트 결과, 성과, 변화와 이를 확인할 수 있는 수치",
    AnalysisPurpose.LEARNING: "프로젝트에서 배운 점, 회고, 어려움과 개선한 내용",
}


class RagService:
    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        vector_store: VectorStore,
        *,
        embedding_model: str,
        chunk_size_tokens: int = 700,
        chunk_overlap_tokens: int = 100,
        top_k: int = 5,
        existing_experience_match_distance: float = 0.4,
        project_source_match_distance: float = 0.65,
        max_related_experiences: int = 3,
    ) -> None:
        self._embedding_provider = embedding_provider
        self._vector_store = vector_store
        self._embedding_model = embedding_model
        self._chunk_size_tokens = chunk_size_tokens
        self._chunk_overlap_tokens = chunk_overlap_tokens
        self._top_k = top_k
        self._existing_experience_match_distance = existing_experience_match_distance
        self._project_source_match_distance = project_source_match_distance
        self._max_related_experiences = max_related_experiences

    @staticmethod
    def _experience_query(experience: ExistingExperience) -> str:
        parts = [experience.title]
        if experience.summary:
            parts.append(experience.summary)
        parts.extend(claim.content for claim in experience.claims)
        return "\n".join(parts)

    @staticmethod
    def _project_query(project_context: ProjectContext) -> str:
        parts = [project_context.name]
        parts.extend(
            value
            for value in (
                project_context.description,
                project_context.activity_type,
                project_context.user_role,
            )
            if value
        )
        return "\n".join(parts)

    async def find_suspected_project_mismatches(
        self,
        project_id: UUID,
        source_ids: Sequence[UUID],
        project_context: ProjectContext,
        *,
        confirmed_source_ids: Sequence[UUID] = (),
    ) -> List[SourceWarning]:
        """Flag possible mismatches without deleting or excluding any Source."""

        confirmed = set(confirmed_source_ids)
        unchecked = [source_id for source_id in source_ids if source_id not in confirmed]
        if not unchecked:
            return []

        query_embedding = await self._embedding_provider.embed_query(
            self._project_query(project_context)
        )

        async def inspect(source_id: UUID) -> Optional[SourceWarning]:
            results = await self._vector_store.search(
                project_id,
                query_embedding,
                top_k=1,
                source_ids=[source_id],
            )
            if not results:
                return None
            closest = results[0]
            if (
                closest.source_id != source_id
                or closest.distance <= self._project_source_match_distance
            ):
                return None
            return SourceWarning(
                source_id=source_id,
                source_name=closest.source_name,
                distance=closest.distance,
                message=(
                    "현재 프로젝트와 관련성이 낮아 보이는 자료입니다. "
                    "이번 분석에서 제외할지, 그래도 포함할지 확인해주세요."
                ),
            )

        warnings = await asyncio.gather(*(inspect(source_id) for source_id in unchecked))
        return [warning for warning in warnings if warning is not None]

    async def index_documents(
        self,
        project_id: UUID,
        documents: Iterable[DocumentSource],
    ) -> IndexingResult:
        document_list = list(documents)
        chunk_count = 0

        for document in document_list:
            content_hash = self._content_hash(document)
            chunks = chunk_documents(
                [document],
                chunk_size_tokens=self._chunk_size_tokens,
                overlap_tokens=self._chunk_overlap_tokens,
            )
            embeddings = await self._embedding_provider.embed_documents(
                [chunk.text for chunk in chunks]
            )
            await self._vector_store.replace_source_chunks(
                project_id,
                document.source_id,
                chunks,
                embeddings,
                embedding_model=self._embedding_model,
                content_hash=content_hash,
            )
            chunk_count += len(chunks)

        return IndexingResult(
            document_count=len(document_list),
            chunk_count=chunk_count,
            embedding_model=self._embedding_model,
        )

    @staticmethod
    def _content_hash(source: DocumentSource) -> str:
        if source.content_hash is not None:
            return source.content_hash
        canonical_text = "\n\f\n".join(page.text for page in source.pages)
        return hashlib.sha256(canonical_text.encode("utf-8")).hexdigest()

    async def index_sources(
        self,
        project_id: UUID,
        sources: Iterable[DocumentSource],
    ) -> SourceIndexResponse:
        items: List[SourceIndexItem] = []
        for source in sources:
            try:
                content_hash = self._content_hash(source)
                duplicate_source_id = (
                    await self._vector_store.find_source_by_content_hash(
                        project_id,
                        content_hash,
                    )
                )
                if (
                    duplicate_source_id is not None
                    and duplicate_source_id != source.source_id
                ):
                    items.append(
                        SourceIndexItem(
                            source_id=source.source_id,
                            source_type=source.source_type,
                            status="DUPLICATE",
                            duplicate_of_source_id=duplicate_source_id,
                        )
                    )
                    continue
                result = await self.index_documents(project_id, [source])
                items.append(
                    SourceIndexItem(
                        source_id=source.source_id,
                        source_type=source.source_type,
                        status="INDEXED",
                        chunk_count=result.chunk_count,
                    )
                )
            except Exception as exc:
                error_code = getattr(exc, "code", "SOURCE_INDEXING_ERROR")
                items.append(
                    SourceIndexItem(
                        source_id=source.source_id,
                        source_type=source.source_type,
                        status="FAILED",
                        error_code=error_code,
                    )
                )
        return SourceIndexResponse(
            project_id=project_id,
            indexed_count=sum(item.status == "INDEXED" for item in items),
            duplicate_count=sum(item.status == "DUPLICATE" for item in items),
            failed_count=sum(item.status == "FAILED" for item in items),
            items=items,
        )

    async def delete_source_index(self, project_id: UUID, source_id: UUID) -> None:
        """Remove a deleted Spring Source from retrieval without touching domain data."""

        await self._vector_store.delete_source(project_id, source_id)

    async def retrieve(
        self,
        project_id: UUID,
        query: str,
        *,
        top_k: Optional[int] = None,
        source_ids: Optional[Sequence[UUID]] = None,
    ) -> List[VectorSearchResult]:
        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("query must not be blank")
        query_embedding = await self._embedding_provider.embed_query(normalized_query)
        return await self._vector_store.search(
            project_id,
            query_embedding,
            top_k=top_k or self._top_k,
            source_ids=source_ids,
        )

    async def retrieve_analysis_context(
        self,
        project_id: UUID,
        *,
        source_ids: Optional[Sequence[UUID]] = None,
    ) -> List[RetrievalContext]:
        purposes = list(DEFAULT_ANALYSIS_QUERIES)
        queries = [DEFAULT_ANALYSIS_QUERIES[purpose] for purpose in purposes]
        query_embeddings = await self._embedding_provider.embed_queries(queries)
        if len(query_embeddings) != len(queries):
            raise AppError(
                code="EMBEDDING_COUNT_MISMATCH",
                message="검색 Query와 Embedding 개수가 일치하지 않습니다.",
                status_code=500,
            )

        async def retrieve_purpose(
            purpose: AnalysisPurpose,
            query: str,
            query_embedding: List[float],
        ) -> RetrievalContext:
            chunks = await self._vector_store.search(
                project_id,
                query_embedding,
                top_k=self._top_k,
                source_ids=source_ids,
            )
            return RetrievalContext(purpose=purpose, query=query, chunks=chunks)

        return list(
            await asyncio.gather(
                *(
                    retrieve_purpose(purpose, query, query_embedding)
                    for purpose, query, query_embedding in zip(
                        purposes, queries, query_embeddings
                    )
                )
            )
        )

    async def retrieve_related_experience_context(
        self,
        project_id: UUID,
        source_ids: Sequence[UUID],
        existing_experiences: Sequence[ExistingExperience],
    ) -> List[ExistingExperienceContext]:
        """Match new Sources first, then load exact evidence for related Experiences."""

        eligible = [experience for experience in existing_experiences if experience.evidences]
        if not source_ids or not eligible:
            return []

        queries = [self._experience_query(experience) for experience in eligible]
        embeddings = await self._embedding_provider.embed_queries(queries)
        if len(embeddings) != len(eligible):
            raise AppError(
                code="EMBEDDING_COUNT_MISMATCH",
                message="기존 경험과 Embedding 개수가 일치하지 않습니다.",
                status_code=500,
            )

        async def match(experience: ExistingExperience, embedding: List[float]):
            results = await self._vector_store.search(
                project_id,
                embedding,
                top_k=1,
                source_ids=source_ids,
            )
            if not results:
                return None
            return experience, results[0].distance

        matches = await asyncio.gather(
            *(match(experience, embedding) for experience, embedding in zip(eligible, embeddings))
        )
        related = sorted(
            (
                item
                for item in matches
                if item is not None
                and item[1] <= self._existing_experience_match_distance
            ),
            key=lambda item: (item[1], str(item[0].experience_id)),
        )[: self._max_related_experiences]

        contexts: List[ExistingExperienceContext] = []
        for experience, distance in related:
            chunks = await self._vector_store.get_chunks(
                project_id,
                [evidence.chunk_id for evidence in experience.evidences],
            )
            allowed = {
                (evidence.source_id, evidence.chunk_id)
                for evidence in experience.evidences
            }
            verified_chunks = [
                chunk
                for chunk in chunks
                if (chunk.source_id, chunk.chunk_id) in allowed
            ]
            if verified_chunks:
                contexts.append(
                    ExistingExperienceContext(
                        experience_id=experience.experience_id,
                        relevance_distance=distance,
                        chunks=verified_chunks,
                    )
                )
        return contexts

    async def retrieve_source_chunks(
        self,
        project_id: UUID,
        source_ids: Sequence[UUID],
        *,
        limit: int,
    ) -> List[DocumentChunk]:
        return await self._vector_store.get_source_chunks(
            project_id,
            source_ids,
            limit=limit,
        )
