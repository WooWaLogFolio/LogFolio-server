from typing import List, Optional
from uuid import UUID, uuid4

import pytest

from logfolio_ai.analysis import AnalysisOrchestrator
from logfolio_ai.core.errors import AppError
from logfolio_ai.llm import GroundedAnalysisInput
from logfolio_ai.models import (
    AnalysisRequest,
    AnalysisResponse,
    Claim,
    DocumentPage,
    DocumentSource,
    Evidence,
    EvidenceType,
    ExperienceCandidate,
    ProvenanceType,
    SubjectType,
    VerificationStatus,
)
from logfolio_ai.rag import AnalysisPurpose, IndexingResult, RetrievalContext
from logfolio_ai.vector_store import VectorSearchResult


class RecordingRagService:
    def __init__(self, contexts: List[RetrievalContext]) -> None:
        self.contexts = contexts
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
        self, project_id: UUID
    ) -> List[RetrievalContext]:
        assert project_id == self.indexed_project_id
        return self.contexts


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
                project_file_id=uuid4(),
                original_name="project.pdf",
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
        project_file_id=uuid4(),
        original_name="project.pdf",
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
                                project_file_id=result.project_file_id,
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
async def test_orchestrator_rejects_evidence_not_in_retrieved_chunks() -> None:
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
                                project_file_id=uuid4(),
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

    with pytest.raises(AppError) as error:
        await orchestrator.analyze(analysis_request)

    assert error.value.code == "UNGROUNDED_EVIDENCE"
