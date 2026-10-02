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

    @staticmethod
    def _is_valid_evidence(
        claim,
        chunks: Dict[UUID, GroundedChunk],
    ) -> bool:
        for evidence in claim.evidences:
            source = chunks.get(evidence.chunk_id)
            if (
                source is None
                or source.source_id != evidence.source_id
                or source.source_type != evidence.source_type
            ):
                return False
            if evidence.excerpt not in source.text:
                return False
            if (
                evidence.page_number is not None
                and evidence.page_number != source.page_number
            ):
                return False
        return True

    def _filter_invalid_evidence(
        self,
        response: AnalysisResponse,
        grounded_chunks: List[GroundedChunk],
    ) -> AnalysisResponse:
        chunks = {chunk.chunk_id: chunk for chunk in grounded_chunks}
        candidates = []
        removed_candidate_ids = set()
        removed_claim_count = 0
        for candidate in response.candidates:
            valid_claims = [
                claim
                for claim in candidate.claims
                if self._is_valid_evidence(claim, chunks)
            ]
            removed_claim_count += len(candidate.claims) - len(valid_claims)
            if candidate.claims and not valid_claims:
                removed_candidate_ids.add(candidate.candidate_id)
                continue
            candidates.append(candidate.model_copy(update={"claims": valid_claims}))

        questions = [
            question.model_copy(update={"candidate_id": None})
            if question.candidate_id in removed_candidate_ids
            else question
            for question in response.questions
        ]
        payload = response.model_dump()
        payload.update({"candidates": candidates, "questions": questions})
        if not candidates and not questions:
            payload["no_update_reason"] = (
                response.no_update_reason
                or "근거 검증을 통과한 분석 결과가 없습니다."
            )
        filtered = AnalysisResponse.model_validate(payload)
        if removed_claim_count:
            logger.warning(
                "Invalid AI evidence filtered: claims=%d candidates=%d",
                removed_claim_count,
                len(removed_candidate_ids),
            )
        return filtered

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

    @staticmethod
    def _build_source_fallback_chunks(source_chunks) -> List[GroundedChunk]:
        return [
            GroundedChunk(
                chunk_id=chunk.chunk_id,
                source_id=chunk.source_id,
                source_type=chunk.source_type,
                source_name=chunk.source_name,
                page_number=chunk.page_number,
                section_title=chunk.section_title,
                text=chunk.text,
                distance=0.0,
                retrieval_fallback=True,
            )
            for chunk in source_chunks
        ]

    async def analyze(self, request: AnalysisRequest) -> AnalysisResponse:
        started_at = time.perf_counter()
        if request.documents:
            await self._rag_service.index_documents(request.project_id, request.documents)
        indexed_at = time.perf_counter()
        source_ids = request.source_ids or [
            document.source_id for document in request.documents
        ]
        if request.project_context is not None:
            source_warnings = (
                await self._rag_service.find_suspected_project_mismatches(
                    request.project_id,
                    source_ids,
                    request.project_context,
                    confirmed_source_ids=request.confirmed_source_ids,
                )
            )
            if source_warnings:
                logger.info(
                    "Analysis waiting for possible project mismatch confirmation: "
                    "project_id=%s sources=%d",
                    request.project_id,
                    len(source_warnings),
                )
                return AnalysisResponse(
                    analysis_run_id=request.analysis_run_id,
                    project_id=request.project_id,
                    summary="현재 프로젝트와 관련성이 낮아 보이는 Source가 있습니다.",
                    candidates=[],
                    questions=[],
                    source_warnings=source_warnings,
                )
        contexts = await self._rag_service.retrieve_analysis_context(
            request.project_id,
            source_ids=source_ids,
        )
        retrieved_at = time.perf_counter()
        grounded_chunks = self._build_grounded_chunks(contexts)
        if not grounded_chunks:
            source_chunks = await self._rag_service.retrieve_source_chunks(
                request.project_id,
                source_ids,
                limit=self._max_grounded_chunks,
            )
            grounded_chunks = self._build_source_fallback_chunks(source_chunks)
            if not grounded_chunks:
                logger.info(
                    "Analysis stopped without retrieval evidence: project_id=%s sources=%d",
                    request.project_id,
                    len(source_ids),
                )
                return AnalysisResponse(
                    analysis_run_id=request.analysis_run_id,
                    project_id=request.project_id,
                    summary="검색 가능한 새 Source 근거가 없습니다.",
                    candidates=[],
                    questions=[],
                    no_update_reason=(
                        "요청한 Source가 아직 인덱싱되지 않았거나 검색 가능한 텍스트가 없습니다."
                    ),
                )
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
        grounded_response = self._filter_invalid_evidence(response, grounded_chunks)
        validated = self._policy_validator.validate(grounded_response)
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
