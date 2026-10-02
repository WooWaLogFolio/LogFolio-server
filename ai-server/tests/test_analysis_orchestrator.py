from typing import List, Optional
from uuid import UUID, uuid4

import pytest

from logfolio_ai.analysis import AnalysisOrchestrator
from logfolio_ai.chunking import DocumentChunk
from logfolio_ai.llm import GroundedAnalysisInput
from logfolio_ai.models import (
    AnalysisRequest,
    AnalysisResponse,
    AnalysisResultType,
    Claim,
    DocumentPage,
    DocumentSource,
    Evidence,
    EvidenceType,
    ExperienceCandidate,
    ExistingEvidence,
    ExistingExperience,
    ProvenanceType,
    SubjectType,
    VerificationStatus,
)
from logfolio_ai.rag import (
    AnalysisPurpose,
    ExistingExperienceContext,
    IndexingResult,
    RetrievalContext,
)
from logfolio_ai.vector_store import VectorSearchResult


class RecordingRagService:
    def __init__(
        self,
        contexts: List[RetrievalContext],
        existing_contexts: Optional[List[ExistingExperienceContext]] = None,
        source_chunks: Optional[List[DocumentChunk]] = None,
    ) -> None:
        self.contexts = contexts
        self.existing_contexts = existing_contexts or []
        self.source_chunks = source_chunks or []
        self.indexed_project_id: Optional[UUID] = None
        self.indexed_documents: List[DocumentSource] = []

    async def index_documents(
        self, project_id: UUID, documents: List[DocumentSource]
    ) -> IndexingResult:
        self.indexed_project_id = project_id
        self.indexed_documents = list(documents)
        return IndexingResult(
            document_count=len(self.indexed_documents),
            chunk_count=1,
            embedding_model="test-model",
        )

    async def retrieve_analysis_context(
        self, project_id: UUID, *, source_ids: Optional[List[UUID]] = None
    ) -> List[RetrievalContext]:
        assert project_id == self.indexed_project_id
        return self.contexts

    async def retrieve_related_experience_context(
        self,
        project_id: UUID,
        source_ids: List[UUID],
        existing_experiences,
    ) -> List[ExistingExperienceContext]:
        del project_id, source_ids, existing_experiences
        return self.existing_contexts

    async def retrieve_source_chunks(
        self,
        project_id: UUID,
        source_ids: List[UUID],
        *,
        limit: int,
    ) -> List[DocumentChunk]:
        del project_id, source_ids
        return self.source_chunks[:limit]


class RecordingLLMProvider:
    def __init__(self, response: AnalysisResponse) -> None:
        self.response = response
        self.grounded_input: Optional[GroundedAnalysisInput] = None

    async def analyze(self, request: AnalysisRequest) -> AnalysisResponse:
        raise AssertionError("orchestrator must not send the raw request to the LLM")

    async def analyze_grounded(
        self, request: GroundedAnalysisInput
    ) -> AnalysisResponse:
        self.grounded_input = request
        return self.response


def request() -> AnalysisRequest:
    return AnalysisRequest(
        analysis_run_id=uuid4(),
        project_id=uuid4(),
        documents=[
            DocumentSource(
                source_id=uuid4(),
                source_name="project.pdf",
                pages=[
                    DocumentPage(
                        page_number=1,
                        text="JWT 인증 API를 구현했다. 검색되지 않을 비밀 문장.",
                    )
                ],
            )
        ],
    )


def search_result(*, distance: float = 0.2) -> VectorSearchResult:
    return VectorSearchResult(
        chunk_id=uuid4(),
        source_id=uuid4(),
        source_name="project.pdf",
        sequence=0,
        page_number=1,
        char_start=0,
        char_end=15,
        text="JWT 인증 API를 구현했다.",
        distance=distance,
    )


def empty_response(analysis_request: AnalysisRequest) -> AnalysisResponse:
    return AnalysisResponse(
        analysis_run_id=analysis_request.analysis_run_id,
        project_id=analysis_request.project_id,
        summary="근거 기반 분석",
        candidates=[],
        questions=[],
    )


@pytest.mark.asyncio
async def test_orchestrator_sends_only_deduplicated_retrieved_chunks() -> None:
    analysis_request = request()
    result = search_result()
    contexts = [
        RetrievalContext(
            purpose=AnalysisPurpose.USER_CONTRIBUTION,
            query="사용자 기여",
            chunks=[result],
        ),
        RetrievalContext(
            purpose=AnalysisPurpose.OUTCOME,
            query="결과",
            chunks=[result.model_copy(update={"distance": 0.1})],
        ),
    ]
    rag = RecordingRagService(contexts)
    llm = RecordingLLMProvider(empty_response(analysis_request))
    orchestrator = AnalysisOrchestrator(rag, llm, max_grounded_chunks=15)

    await orchestrator.analyze(analysis_request)

    assert rag.indexed_documents == analysis_request.documents
    assert llm.grounded_input is not None
    assert len(llm.grounded_input.chunks) == 1
    grounded = llm.grounded_input.chunks[0]
    assert grounded.distance == pytest.approx(0.1)
    assert grounded.purposes == [
        AnalysisPurpose.USER_CONTRIBUTION,
        AnalysisPurpose.OUTCOME,
    ]
    assert "검색되지 않을 비밀 문장" not in grounded.text


@pytest.mark.asyncio
async def test_orchestrator_accepts_exact_excerpt_from_retrieved_chunk() -> None:
    analysis_request = request()
    result = search_result()
    response = AnalysisResponse(
        analysis_run_id=analysis_request.analysis_run_id,
        project_id=analysis_request.project_id,
        summary="근거 기반 분석",
        candidates=[
            ExperienceCandidate(
                candidate_id=uuid4(),
                title="인증 구현",
                summary="JWT 인증 구현 경험",
                claims=[
                    Claim(
                        section_type="ACTION",
                        content="JWT 인증 API를 구현했다.",
                        subject_type=SubjectType.TEAM,
                        provenance_type=ProvenanceType.SOURCE_EXTRACTED,
                        verification_status=VerificationStatus.VERIFIED,
                        evidence_type=EvidenceType.DIRECT,
                        evidences=[
                            Evidence(
                                source_id=result.source_id,
                                chunk_id=result.chunk_id,
                                page_number=1,
                                excerpt="JWT 인증 API를 구현했다.",
                            )
                        ],
                        requires_user_confirmation=False,
                    )
                ],
            )
        ],
        questions=[],
    )
    rag = RecordingRagService(
        [
            RetrievalContext(
                purpose=AnalysisPurpose.USER_CONTRIBUTION,
                query="기여",
                chunks=[result],
            )
        ]
    )
    orchestrator = AnalysisOrchestrator(rag, RecordingLLMProvider(response))

    assert await orchestrator.analyze(analysis_request) == response


@pytest.mark.asyncio
async def test_orchestrator_excludes_candidate_with_ungrounded_evidence() -> None:
    analysis_request = request()
    result = search_result()
    response = AnalysisResponse(
        analysis_run_id=analysis_request.analysis_run_id,
        project_id=analysis_request.project_id,
        summary="근거 기반 분석",
        candidates=[
            ExperienceCandidate(
                candidate_id=uuid4(),
                title="잘못된 근거",
                summary="검색되지 않은 근거",
                claims=[
                    Claim(
                        section_type="ACTION",
                        content="근거가 없는 주장",
                        subject_type=SubjectType.UNKNOWN,
                        provenance_type=ProvenanceType.SOURCE_EXTRACTED,
                        verification_status=VerificationStatus.VERIFIED,
                        evidence_type=EvidenceType.DIRECT,
                        evidences=[
                            Evidence(
                                source_id=uuid4(),
                                chunk_id=uuid4(),
                                excerpt="존재하지 않는 인용문",
                            )
                        ],
                        requires_user_confirmation=False,
                    )
                ],
            )
        ],
        questions=[],
    )
    rag = RecordingRagService(
        [
            RetrievalContext(
                purpose=AnalysisPurpose.USER_CONTRIBUTION,
                query="기여",
                chunks=[result],
            )
        ]
    )
    orchestrator = AnalysisOrchestrator(rag, RecordingLLMProvider(response))

    result_response = await orchestrator.analyze(analysis_request)

    assert result_response.candidates == []
    assert result_response.result_types == [AnalysisResultType.NO_UPDATE]
    assert result_response.no_update_reason == "근거 검증을 통과한 분석 결과가 없습니다."


@pytest.mark.asyncio
async def test_orchestrator_keeps_valid_claim_when_sibling_evidence_is_invalid() -> None:
    analysis_request = request()
    retrieved = search_result()
    valid_claim = Claim(
        section_type="ACTION",
        content="JWT 인증 API를 구현했다.",
        subject_type=SubjectType.TEAM,
        provenance_type=ProvenanceType.SOURCE_EXTRACTED,
        verification_status=VerificationStatus.VERIFIED,
        evidence_type=EvidenceType.DIRECT,
        evidences=[
            Evidence(
                source_id=retrieved.source_id,
                chunk_id=retrieved.chunk_id,
                page_number=1,
                excerpt="JWT 인증 API를 구현했다.",
            )
        ],
        requires_user_confirmation=False,
    )
    invalid_claim = valid_claim.model_copy(
        update={
            "content": "검색되지 않은 성과",
            "evidences": [
                Evidence(
                    source_id=uuid4(),
                    chunk_id=uuid4(),
                    excerpt="없는 인용문",
                )
            ],
        }
    )
    response = AnalysisResponse(
        analysis_run_id=analysis_request.analysis_run_id,
        project_id=analysis_request.project_id,
        summary="일부 근거 기반 분석",
        candidates=[
            ExperienceCandidate(
                candidate_id=uuid4(),
                title="인증 구현",
                summary="검증된 Claim만 유지",
                claims=[valid_claim, invalid_claim],
            )
        ],
    )
    rag = RecordingRagService(
        [
            RetrievalContext(
                purpose=AnalysisPurpose.USER_CONTRIBUTION,
                query="기여",
                chunks=[retrieved],
            )
        ]
    )

    result_response = await AnalysisOrchestrator(
        rag, RecordingLLMProvider(response)
    ).analyze(analysis_request)

    assert len(result_response.candidates) == 1
    assert result_response.candidates[0].claims == [valid_claim]


@pytest.mark.asyncio
async def test_orchestrator_adds_selected_existing_evidence_before_final_analysis() -> None:
    analysis_request = request()
    experience_id = uuid4()
    old_source_id = uuid4()
    old_chunk_id = uuid4()
    analysis_request.existing_experiences = [
        ExistingExperience(
            experience_id=experience_id,
            title="기존 인증 경험",
            evidences=[
                ExistingEvidence(
                    evidence_id=uuid4(),
                    source_id=old_source_id,
                    chunk_id=old_chunk_id,
                )
            ],
        )
    ]
    old_chunk = DocumentChunk(
        chunk_id=old_chunk_id,
        source_id=old_source_id,
        source_name="old.pdf",
        sequence=0,
        char_start=0,
        char_end=14,
        token_count=4,
        text="기존 JWT 인증 구현 근거",
    )
    new_source = analysis_request.documents[0]
    new_chunk = DocumentChunk(
        chunk_id=uuid4(),
        source_id=new_source.source_id,
        source_name=new_source.source_name,
        sequence=0,
        char_start=0,
        char_end=13,
        token_count=4,
        text="새 JWT 인증 개선 근거",
    )
    response = AnalysisResponse(
        analysis_run_id=analysis_request.analysis_run_id,
        project_id=analysis_request.project_id,
        summary="기존 경험을 보강합니다.",
        candidates=[
            ExperienceCandidate(
                candidate_id=uuid4(),
                result_type=AnalysisResultType.EXISTING_UPDATE,
                target_experience_id=experience_id,
                title="기존 인증 경험 보강",
                summary="새 근거를 추가합니다.",
            )
        ],
    )
    rag = RecordingRagService(
        [],
        [
            ExistingExperienceContext(
                experience_id=experience_id,
                relevance_distance=0.2,
                chunks=[old_chunk],
            )
        ],
        [new_chunk],
    )
    llm = RecordingLLMProvider(response)

    result = await AnalysisOrchestrator(rag, llm).analyze(analysis_request)

    assert result.candidates[0].target_experience_id == experience_id
    assert llm.grounded_input is not None
    assert llm.grounded_input.chunks[0].chunk_id == old_chunk_id
    assert llm.grounded_input.chunks[0].related_experience_ids == [experience_id]


@pytest.mark.asyncio
async def test_empty_semantic_retrieval_uses_new_source_chunks_without_forced_mapping() -> None:
    analysis_request = request()
    source = analysis_request.documents[0]
    fallback_chunk = DocumentChunk(
        chunk_id=uuid4(),
        source_id=source.source_id,
        source_name=source.source_name,
        sequence=0,
        char_start=0,
        char_end=14,
        token_count=4,
        text="새 Source 자체 근거",
    )
    rag = RecordingRagService([], source_chunks=[fallback_chunk])
    llm = RecordingLLMProvider(empty_response(analysis_request))

    await AnalysisOrchestrator(rag, llm).analyze(analysis_request)

    assert llm.grounded_input is not None
    assert llm.grounded_input.chunks[0].chunk_id == fallback_chunk.chunk_id
    assert llm.grounded_input.chunks[0].retrieval_fallback is True
    assert llm.grounded_input.chunks[0].related_experience_ids == []


@pytest.mark.asyncio
async def test_no_indexed_source_chunks_returns_no_update_without_llm_call() -> None:
    analysis_request = request()
    rag = RecordingRagService([])
    llm = RecordingLLMProvider(empty_response(analysis_request))

    response = await AnalysisOrchestrator(rag, llm).analyze(analysis_request)

    assert response.result_types == [AnalysisResultType.NO_UPDATE]
    assert response.candidates == []
    assert response.questions == []
    assert "인덱싱" in response.no_update_reason
    assert llm.grounded_input is None
