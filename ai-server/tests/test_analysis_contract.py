from uuid import uuid4

import pytest
from pydantic import ValidationError

from logfolio_ai.models import (
    AnalysisResultType,
    AnalysisRequest,
    AnalysisResponse,
    Claim,
    DocumentPage,
    DocumentSource,
    Evidence,
    EvidenceType,
    ExperienceCandidate,
    ExistingExperience,
    GapQuestion,
    ProvenanceType,
    SubjectType,
    SourceType,
    VerificationStatus,
)


def make_document() -> DocumentSource:
    return DocumentSource(
        source_id=uuid4(),
        source_name="project.pdf",
        pages=[DocumentPage(page_number=1, text="JWT 인증 API를 구현했다.")],
    )


def make_evidence() -> Evidence:
    return Evidence(
        source_id=uuid4(),
        chunk_id=uuid4(),
        page_number=1,
        excerpt="박수빈은 JWT 인증 API 구현을 담당했다.",
    )


def make_claim() -> Claim:
    return Claim(
        section_type="CONTRIBUTION",
        content="JWT 인증 API 구현을 담당했다.",
        subject_type=SubjectType.USER,
        provenance_type=ProvenanceType.SOURCE_EXTRACTED,
        verification_status=VerificationStatus.VERIFIED,
        evidence_type=EvidenceType.DIRECT,
        evidences=[make_evidence()],
        requires_user_confirmation=False,
    )


def test_request_accepts_at_most_three_documents() -> None:
    with pytest.raises(ValidationError):
        AnalysisRequest(
            analysis_run_id=uuid4(),
            project_id=uuid4(),
            documents=[make_document() for _ in range(4)],
        )


def test_response_accepts_at_most_three_candidates_and_two_questions() -> None:
    candidates = [
        ExperienceCandidate(
            candidate_id=uuid4(),
            title=f"경험 {index}",
            summary="인증 기능 구현 경험",
            claims=[make_claim()],
        )
        for index in range(3)
    ]
    questions = [
        GapQuestion(
            question_id=uuid4(),
            candidate_id=candidates[0].candidate_id,
            target_section="RESULT",
            question=f"결과를 알려주세요. {index}",
        )
        for index in range(2)
    ]

    response = AnalysisResponse(
        analysis_run_id=uuid4(),
        project_id=uuid4(),
        summary="프로젝트 분석 초안",
        candidates=candidates,
        questions=questions,
    )

    assert len(response.candidates) == 3
    assert len(response.questions) == 2


def test_question_candidate_must_reference_returned_candidate() -> None:
    candidate = ExperienceCandidate(
        candidate_id=uuid4(),
        title="인증 기능 구현 경험",
        summary="인증 기능 구현 경험",
        claims=[make_claim()],
    )

    with pytest.raises(
        ValidationError,
        match="question candidateId must reference a returned candidate",
    ):
        AnalysisResponse(
            analysis_run_id=uuid4(),
            project_id=uuid4(),
            summary="프로젝트 분석 초안",
            candidates=[candidate],
            questions=[
                GapQuestion(
                    question_id=uuid4(),
                    candidate_id=uuid4(),
                    target_section="RESULT",
                    question="결과를 알려주세요.",
                )
            ],
        )


def test_source_extracted_claim_requires_evidence() -> None:
    with pytest.raises(ValidationError, match="SOURCE_EXTRACTED claim requires evidence"):
        Claim(
            section_type="ACTION",
            content="JWT 인증 API를 구현했다.",
            subject_type=SubjectType.USER,
            provenance_type=ProvenanceType.SOURCE_EXTRACTED,
            verification_status=VerificationStatus.VERIFIED,
            evidence_type=EvidenceType.NONE,
            requires_user_confirmation=False,
        )


def test_needs_confirmation_requires_confirmation_flag() -> None:
    with pytest.raises(ValidationError, match="requiresUserConfirmation=true"):
        Claim(
            section_type="CONTRIBUTION",
            content="사용자 인터뷰에 참여한 것으로 보인다.",
            subject_type=SubjectType.UNKNOWN,
            provenance_type=ProvenanceType.AI_INFERRED,
            verification_status=VerificationStatus.NEEDS_CONFIRMATION,
            evidence_type=EvidenceType.INDIRECT,
            evidences=[make_evidence()],
            requires_user_confirmation=False,
        )


def test_contract_serializes_with_camel_case_keys() -> None:
    request = AnalysisRequest(
        analysis_run_id=uuid4(),
        project_id=uuid4(),
        documents=[make_document()],
    )

    payload = request.model_dump(mode="json", by_alias=True)

    assert "analysisRunId" in payload
    assert "projectId" in payload
    assert "sourceId" in payload["documents"][0]
    assert "pageNumber" in payload["documents"][0]["pages"][0]


def test_contract_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        AnalysisRequest.model_validate(
            {
                "analysisRunId": str(uuid4()),
                "projectId": str(uuid4()),
                "documents": [
                    {
                        "sourceId": str(uuid4()),
                        "sourceName": "project.pdf",
                        "pages": [{"text": "프로젝트 자료"}],
                    }
                ],
                "unexpectedField": True,
            }
        )


def test_request_accepts_preindexed_sources_and_existing_experiences() -> None:
    source_id = uuid4()
    experience_id = uuid4()

    request = AnalysisRequest(
        analysis_run_id=uuid4(),
        project_id=uuid4(),
        source_ids=[source_id],
        existing_experiences=[
            ExistingExperience(
                experience_id=experience_id,
                title="인증 개선",
                summary="JWT 인증을 개선한 경험",
            )
        ],
    )

    assert request.source_ids == [source_id]
    assert request.existing_experiences[0].experience_id == experience_id


def test_request_rejects_mixed_inline_and_preindexed_sources() -> None:
    with pytest.raises(ValidationError, match="cannot be used together"):
        AnalysisRequest(
            analysis_run_id=uuid4(),
            project_id=uuid4(),
            source_ids=[uuid4()],
            documents=[make_document()],
        )


def test_existing_update_requires_target_experience() -> None:
    with pytest.raises(ValidationError, match="requires targetExperienceId"):
        ExperienceCandidate(
            candidate_id=uuid4(),
            result_type=AnalysisResultType.EXISTING_UPDATE,
            title="기존 경험 보강",
            summary="새 근거를 추가합니다.",
        )


def test_empty_analysis_is_classified_as_no_update() -> None:
    response = AnalysisResponse(
        analysis_run_id=uuid4(),
        project_id=uuid4(),
        summary="반영할 내용이 없습니다.",
        candidates=[],
        questions=[],
        no_update_reason="새롭게 구조화할 정보가 없습니다.",
    )

    assert response.result_types == [AnalysisResultType.NO_UPDATE]


def test_quick_log_is_a_supported_source_type() -> None:
    source = DocumentSource(
        source_id=uuid4(),
        source_type=SourceType.QUICK_LOG,
        source_name="30초 기록",
        pages=[DocumentPage(text="사용자 테스트 결과를 보고 기능을 수정했다.")],
    )

    assert source.source_type == SourceType.QUICK_LOG
