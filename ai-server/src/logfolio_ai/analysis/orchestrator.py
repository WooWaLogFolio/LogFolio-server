import logging
import time
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from logfolio_ai.core.errors import AppError
from logfolio_ai.llm import GroundedAnalysisInput, GroundedChunk, LLMProvider
from logfolio_ai.models import AnalysisRequest, AnalysisResponse
from logfolio_ai.policy import AIPolicyValidator
from logfolio_ai.rag import (
    AnalysisPurpose,
    ExistingExperienceContext,
    RagService,
    RetrievalContext,
)


logger = logging.getLogger("uvicorn.error")


class AnalysisOrchestrator:
    def __init__(
        self,
        rag_service: RagService,
        llm_provider: LLMProvider,
        *,
        max_grounded_chunks: int = 15,
        policy_validator: Optional[AIPolicyValidator] = None,
    ) -> None:
        self._rag_service = rag_service
        self._llm_provider = llm_provider
        self._max_grounded_chunks = max_grounded_chunks
        self._policy_validator = policy_validator or AIPolicyValidator()

    def _build_grounded_chunks(
        self,
        contexts: List[RetrievalContext],
    ) -> List[GroundedChunk]:
        by_chunk_id: Dict[UUID, Tuple[GroundedChunk, List[AnalysisPurpose]]] = {}

        for context in contexts:
            for result in context.chunks:
                existing = by_chunk_id.get(result.chunk_id)
                if existing is None:
                    chunk = GroundedChunk(
                        chunk_id=result.chunk_id,
                        source_id=result.source_id,
                        source_type=result.source_type,
                        source_name=result.source_name,
                        page_number=result.page_number,
                        section_title=result.section_title,
                        text=result.text,
                        distance=result.distance,
                        purposes=[context.purpose],
                    )
                    by_chunk_id[result.chunk_id] = (chunk, [context.purpose])
                    continue

                chunk, purposes = existing
                if context.purpose not in purposes:
                    purposes.append(context.purpose)
                if result.distance < chunk.distance:
                    chunk = chunk.model_copy(update={"distance": result.distance})
                by_chunk_id[result.chunk_id] = (chunk, purposes)

        merged = [
            chunk.model_copy(update={"purposes": purposes})
            for chunk, purposes in by_chunk_id.values()
        ]
        merged.sort(key=lambda chunk: (chunk.distance, str(chunk.chunk_id)))
        return merged[: self._max_grounded_chunks]

    def _validate_evidence(
        self,
        response: AnalysisResponse,
        grounded_chunks: List[GroundedChunk],
    ) -> None:
        chunks = {chunk.chunk_id: chunk for chunk in grounded_chunks}
        for candidate in response.candidates:
            for claim in candidate.claims:
                for evidence in claim.evidences:
                    source = chunks.get(evidence.chunk_id)
                    if (
                        source is None
                        or source.source_id != evidence.source_id
                        or source.source_type != evidence.source_type
                    ):
                        raise AppError(
                            code="UNGROUNDED_EVIDENCE",
                            message="AI가 검색되지 않은 근거를 반환했습니다.",
                            status_code=502,
                        )
                    if evidence.excerpt not in source.text:
                        raise AppError(
                            code="INVALID_EVIDENCE_QUOTE",
                            message="AI 인용문이 검색된 원문과 일치하지 않습니다.",
                            status_code=502,
                        )
                    if (
                        evidence.page_number is not None
                        and evidence.page_number != source.page_number
                    ):
                        raise AppError(
                            code="INVALID_EVIDENCE_LOCATION",
                            message="AI 근거의 페이지가 원문 위치와 일치하지 않습니다.",
                            status_code=502,
                        )

    def _add_existing_evidence(
        self,
        grounded_chunks: List[GroundedChunk],
        contexts: List[ExistingExperienceContext],
    ) -> List[GroundedChunk]:
        by_chunk_id = {chunk.chunk_id: chunk for chunk in grounded_chunks}
        for context in contexts:
            for chunk in context.chunks:
                existing = by_chunk_id.get(chunk.chunk_id)
                if existing is None:
                    by_chunk_id[chunk.chunk_id] = GroundedChunk(
                        chunk_id=chunk.chunk_id,
                        source_id=chunk.source_id,
                        source_type=chunk.source_type,
                        source_name=chunk.source_name,
                        page_number=chunk.page_number,
                        section_title=chunk.section_title,
                        text=chunk.text,
                        distance=context.relevance_distance,
                        related_experience_ids=[context.experience_id],
                    )
                    continue
                related_ids = list(existing.related_experience_ids)
                if context.experience_id not in related_ids:
                    related_ids.append(context.experience_id)
                by_chunk_id[chunk.chunk_id] = existing.model_copy(
                    update={"related_experience_ids": related_ids}
                )
        merged = list(by_chunk_id.values())
        merged.sort(
            key=lambda chunk: (
                0 if chunk.related_experience_ids else 1,
                chunk.distance,
                str(chunk.chunk_id),
            )
        )
        return merged[: self._max_grounded_chunks]

    async def analyze(self, request: AnalysisRequest) -> AnalysisResponse:
        started_at = time.perf_counter()
        if request.documents:
            await self._rag_service.index_documents(request.project_id, request.documents)
        indexed_at = time.perf_counter()
        source_ids = request.source_ids or [
            document.source_id for document in request.documents
        ]
        contexts = await self._rag_service.retrieve_analysis_context(
            request.project_id,
            source_ids=source_ids,
        )
        retrieved_at = time.perf_counter()
        grounded_chunks = self._build_grounded_chunks(contexts)
        existing_contexts = await self._rag_service.retrieve_related_experience_context(
            request.project_id,
            source_ids,
            request.existing_experiences,
        )
        grounded_chunks = self._add_existing_evidence(
            grounded_chunks,
            existing_contexts,
        )
        grounded_input = GroundedAnalysisInput(
            analysis_run_id=request.analysis_run_id,
            project_id=request.project_id,
            chunks=grounded_chunks,
            existing_experiences=request.existing_experiences,
            corrections=request.corrections,
        )
        logger.info(
            "Analysis grounding prepared: index=%.3fs retrieve=%.3fs chunks=%d",
            indexed_at - started_at,
            retrieved_at - indexed_at,
            len(grounded_chunks),
        )
        response = await self._llm_provider.analyze_grounded(grounded_input)
        generated_at = time.perf_counter()
        existing_ids = {
            experience.experience_id for experience in request.existing_experiences
        }
        related_existing_ids = {
            context.experience_id for context in existing_contexts
        }
        for candidate in response.candidates:
            if (
                candidate.target_experience_id is not None
                and candidate.target_experience_id not in existing_ids
            ):
                raise AppError(
                    code="INVALID_TARGET_EXPERIENCE",
                    message="AI가 요청에 없는 기존 경험을 보강 대상으로 반환했습니다.",
                    status_code=502,
                )
            if (
                candidate.target_experience_id is not None
                and candidate.target_experience_id not in related_existing_ids
            ):
                raise AppError(
                    code="UNRELATED_TARGET_EXPERIENCE",
                    message="AI가 관련 근거가 조회되지 않은 경험을 보강 대상으로 반환했습니다.",
                    status_code=502,
                )
        self._validate_evidence(response, grounded_chunks)
        validated = self._policy_validator.validate(response)
        completed_at = time.perf_counter()
        logger.info(
            "Analysis stages completed: index=%.3fs retrieve=%.3fs "
            "generate=%.3fs validate=%.3fs total=%.3fs chunks=%d",
            indexed_at - started_at,
            retrieved_at - indexed_at,
            generated_at - retrieved_at,
            completed_at - generated_at,
            completed_at - started_at,
            len(grounded_chunks),
        )
        return validated
