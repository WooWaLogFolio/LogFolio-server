from uuid import uuid4

from logfolio_ai.models import (
    AnalysisResponse,
    AnalysisResultType,
    Claim,
    Evidence,
    EvidenceType,
    ExperienceCandidate,
    ExistingClaim,
    ExistingExperience,
    GapQuestion,
    ProvenanceType,
    SubjectType,
    VerificationStatus,
)
from logfolio_ai.models.refinement import (
    ExperienceRefinementRequest,
    RefinementStatus,
    refinement_response,
)


def grounded_claim(section: str, content: str) -> Claim:
    return Claim(
        section_type=section,
        content=content,
        subject_type=SubjectType.USER,
        provenance_type=ProvenanceType.SOURCE_EXTRACTED,
        verification_status=VerificationStatus.VERIFIED,
        evidence_type=EvidenceType.DIRECT,
        evidences=[
            Evidence(
                source_id=uuid4(),
                chunk_id=uuid4(),
                page_number=1,
                excerpt="JWT 인증 API 구현을 담당했다.",
            )
        ],
        requires_user_confirmation=False,
    )


def test_refinement_returns_only_target_experience_proposals() -> None:
    project_id = uuid4()
    experience_id = uuid4()
    target_candidate_id = uuid4()
    unrelated_candidate_id = uuid4()
    request = ExperienceRefinementRequest(
        review_session_id=uuid4(),
        project_id=project_id,
        source_ids=[uuid4()],
        experience=ExistingExperience(
            experience_id=experience_id,
            title="인증 기능 개발",
            summary="JWT 인증 구현",
            claims=[ExistingClaim(section_type="ACTION", content="로그인을 구현했다.")],
        ),
    )
    analysis = AnalysisResponse(
        analysis_run_id=request.review_session_id,
        project_id=project_id,
        summary="기존 경험의 실행 내용을 보완했습니다.",
        candidates=[
            ExperienceCandidate(
                candidate_id=target_candidate_id,
                result_type=AnalysisResultType.EXISTING_UPDATE,
                target_experience_id=experience_id,
                title="인증 기능 개발",
                summary="JWT 인증 구현",
                claims=[grounded_claim("ACTION", "JWT 인증 API를 구현했다.")],
            ),
            ExperienceCandidate(
                candidate_id=unrelated_candidate_id,
                title="다른 경험",
                summary="다듬기 대상이 아닌 새 경험",
                claims=[grounded_claim("ACTION", "다른 기능을 구현했다.")],
            ),
        ],
        questions=[
            GapQuestion(
                question_id=uuid4(),
                candidate_id=target_candidate_id,
                target_section="RESULT",
                question="구현 후 어떤 변화가 있었나요?",
            ),
            GapQuestion(
                question_id=uuid4(),
                candidate_id=unrelated_candidate_id,
                target_section="ROLE",
                question="다른 경험의 역할은 무엇인가요?",
            ),
        ],
    )

    response = refinement_response(request, analysis)

    assert response.status == RefinementStatus.REVIEW_READY
    assert len(response.review_items) == 1
    assert response.review_items[0].item_type == "ACTION"
    assert response.review_items[0].original_content == "로그인을 구현했다."
    assert response.review_items[0].proposed_content == "JWT 인증 API를 구현했다."
    assert [question.candidate_id for question in response.questions] == [
        target_candidate_id
    ]


def test_refinement_omits_unchanged_claims() -> None:
    project_id = uuid4()
    experience_id = uuid4()
    request = ExperienceRefinementRequest(
        review_session_id=uuid4(),
        project_id=project_id,
        source_ids=[uuid4()],
        experience=ExistingExperience(
            experience_id=experience_id,
            title="인증 기능 개발",
            claims=[
                ExistingClaim(
                    section_type="ACTION",
                    content="JWT 인증 API를 구현했다.",
                )
            ],
        ),
    )
    candidate = ExperienceCandidate(
        candidate_id=uuid4(),
        result_type=AnalysisResultType.EXISTING_UPDATE,
        target_experience_id=experience_id,
        title="인증 기능 개발",
        summary="변경 없음",
        claims=[grounded_claim("ACTION", "  JWT 인증 API를 구현했다.  ")],
    )
    analysis = AnalysisResponse(
        analysis_run_id=request.review_session_id,
        project_id=project_id,
        summary="기존 내용과 같습니다.",
        candidates=[candidate],
    )

    response = refinement_response(request, analysis)

    assert response.status == RefinementStatus.NO_UPDATE
    assert response.review_items == []
    assert response.no_update_reason is not None
