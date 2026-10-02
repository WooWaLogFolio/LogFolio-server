from uuid import uuid4

from logfolio_ai.models import (
    AnalysisResponse,
    Claim,
    Evidence,
    EvidenceType,
    ExperienceCandidate,
    GapQuestion,
    PolicyViolationType,
    ProvenanceType,
    SubjectType,
    VerificationStatus,
)
from logfolio_ai.policy import AIPolicyValidator


def evidence(excerpt: str) -> Evidence:
    return Evidence(
        source_id=uuid4(),
        chunk_id=uuid4(),
        page_number=1,
        excerpt=excerpt,
    )


def claim(**updates) -> Claim:
    values = {
        "section_type": "ACTION",
        "content": "사용자 인터뷰를 진행했다.",
        "subject_type": SubjectType.TEAM,
        "provenance_type": ProvenanceType.SOURCE_EXTRACTED,
        "verification_status": VerificationStatus.VERIFIED,
        "evidence_type": EvidenceType.DIRECT,
        "evidences": [evidence("프로젝트 팀은 사용자 인터뷰를 진행했다.")],
        "requires_user_confirmation": False,
    }
    values.update(updates)
    return Claim(**values)


def response(claims, questions=None) -> AnalysisResponse:
    return AnalysisResponse(
        analysis_run_id=uuid4(),
        project_id=uuid4(),
        summary="분석 초안",
        candidates=[
            ExperienceCandidate(
                candidate_id=uuid4(),
                title="프로젝트 경험",
                summary="경험 요약",
                claims=claims,
            )
        ],
        questions=questions or [],
    )


def test_team_activity_cannot_be_attributed_to_user() -> None:
    user_claim = claim(subject_type=SubjectType.USER)

    validated = AIPolicyValidator().validate(response([user_claim]))
    result = validated.candidates[0].claims[0]

    assert result.subject_type == SubjectType.UNKNOWN
    assert result.provenance_type == ProvenanceType.AI_INFERRED
    assert result.verification_status == VerificationStatus.NEEDS_CONFIRMATION
    assert result.requires_user_confirmation is True
    assert PolicyViolationType.UNSUPPORTED_USER_CONTRIBUTION in result.policy_violations
    assert PolicyViolationType.TEAM_TO_USER_ATTRIBUTION in result.policy_violations


def test_explicit_first_person_evidence_can_keep_user_subject() -> None:
    user_claim = claim(
        subject_type=SubjectType.USER,
        evidences=[evidence("저는 사용자 인터뷰 설계를 담당했습니다.")],
    )

    validated = AIPolicyValidator().validate(response([user_claim]))
    result = validated.candidates[0].claims[0]

    assert result.subject_type == SubjectType.USER
    assert result.verification_status == VerificationStatus.VERIFIED
    assert result.requires_user_confirmation is False


def test_ai_cannot_create_user_confirmed_provenance() -> None:
    invalid_claim = claim(provenance_type=ProvenanceType.USER_CONFIRMED)

    validated = AIPolicyValidator().validate(response([invalid_claim]))
    result = validated.candidates[0].claims[0]

    assert result.provenance_type == ProvenanceType.AI_INFERRED
    assert result.verification_status == VerificationStatus.NEEDS_CONFIRMATION
    assert PolicyViolationType.INVALID_PROVENANCE in result.policy_violations


def test_unsupported_outcome_is_flagged_for_confirmation() -> None:
    outcome = claim(
        section_type="RESULT",
        content="전환율이 30% 향상됐다.",
        subject_type=SubjectType.UNKNOWN,
        provenance_type=ProvenanceType.AI_INFERRED,
        verification_status=VerificationStatus.NEEDS_CONFIRMATION,
        evidence_type=EvidenceType.NONE,
        evidences=[],
        requires_user_confirmation=True,
    )

    validated = AIPolicyValidator().validate(response([outcome]))
    result = validated.candidates[0].claims[0]

    assert PolicyViolationType.MISSING_EVIDENCE in result.policy_violations
    assert PolicyViolationType.UNSUPPORTED_ACHIEVEMENT in result.policy_violations
    assert result.verification_status == VerificationStatus.NEEDS_CONFIRMATION


def test_question_is_removed_when_source_already_answers_section() -> None:
    answered = claim(section_type="RESULT")
    questions = [
        GapQuestion(
            question_id=uuid4(),
            target_section="RESULT",
            question="프로젝트 결과는 무엇인가요?",
        ),
        GapQuestion(
            question_id=uuid4(),
            target_section="LEARNING",
            question="무엇을 배웠나요?",
        ),
    ]

    validated = AIPolicyValidator().validate(response([answered], questions))

    assert [question.target_section for question in validated.questions] == ["LEARNING"]


def test_questions_are_sorted_by_product_priority() -> None:
    questions = [
        GapQuestion(
            question_id=uuid4(),
            target_section="LEARNING",
            question="무엇을 배웠나요?",
        ),
        GapQuestion(
            question_id=uuid4(),
            target_section="CONTRIBUTION",
            question="직접 담당한 부분은 무엇인가요?",
        ),
    ]

    validated = AIPolicyValidator().validate(response([], questions))

    assert [question.target_section for question in validated.questions] == [
        "CONTRIBUTION",
        "LEARNING",
    ]
