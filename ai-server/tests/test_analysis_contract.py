from uuid import uuid4

import pytest
from pydantic import ValidationError

from logfolio_ai.models import (
    AnalysisRequest,
    AnalysisResponse,
    Claim,
    DocumentPage,
    DocumentSource,
    Evidence,
    EvidenceType,
    ExperienceCandidate,
    GapQuestion,
    ProvenanceType,
    SubjectType,
    VerificationStatus,
)


def make_document() -> DocumentSource:
    return DocumentSource(
        project_file_id=uuid4(),
        original_name="project.pdf",
        pages=[DocumentPage(page_number=1, text="JWT 인증 API를 구현했다.")],
    )


def make_evidence() -> Evidence:
    return Evidence(
        project_file_id=uuid4(),
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
    assert "projectFileId" in payload["documents"][0]
    assert "pageNumber" in payload["documents"][0]["pages"][0]


def test_contract_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        AnalysisRequest.model_validate(
            {
                "analysisRunId": str(uuid4()),
                "projectId": str(uuid4()),
                "documents": [
                    {
                        "projectFileId": str(uuid4()),
                        "originalName": "project.pdf",
                        "pages": [{"text": "프로젝트 자료"}],
                    }
                ],
                "unexpectedField": True,
            }
        )
