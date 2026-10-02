from uuid import uuid4

from logfolio_ai.models import (
    AnalysisResultType,
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
    UserAnswer,
    UserCorrection,
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


def test_removed_answered_question_recomputes_response_state() -> None:
    answered = claim(section_type="RESULT")
    result = AIPolicyValidator().validate(
        response(
            [answered],
            [
                GapQuestion(
                    question_id=uuid4(),
                    target_section="RESULT",
                    question="프로젝트 결과는 무엇인가요?",
                )
            ],
        )
    )

    assert result.questions == []
    assert result.information_need is None
    assert result.result_types == [AnalysisResultType.NEW_EXPERIENCE]


def test_claim_can_use_valid_stored_user_answer_provenance() -> None:
    answer = UserAnswer(
        answer_id=uuid4(),
        question_id=uuid4(),
        target_section="CONTRIBUTION",
        answer="백엔드 API 설계를 직접 담당했습니다.",
    )
    answered_claim = claim(
        section_type="CONTRIBUTION",
        content="백엔드 API 설계를 담당했다.",
        subject_type=SubjectType.USER,
        provenance_type=ProvenanceType.USER_INPUT,
        verification_status=VerificationStatus.VERIFIED,
        evidence_type=EvidenceType.NONE,
        evidences=[],
        supporting_answer_ids=[answer.answer_id],
        requires_user_confirmation=False,
    )
    questions = [
        GapQuestion(
            question_id=uuid4(),
            target_section="CONTRIBUTION",
            question="직접 담당한 부분은 무엇인가요?",
        )
    ]

    result = AIPolicyValidator().validate(
        response([answered_claim], questions),
        user_answers=[answer],
    )
    validated_claim = result.candidates[0].claims[0]

    assert validated_claim.provenance_type == ProvenanceType.USER_INPUT
    assert validated_claim.subject_type == SubjectType.USER
    assert validated_claim.verification_status == VerificationStatus.VERIFIED
    assert result.questions == []


def test_unknown_answer_id_cannot_create_user_input_provenance() -> None:
    unsupported = claim(
        section_type="CONTRIBUTION",
        content="백엔드 API 설계를 담당했다.",
        subject_type=SubjectType.USER,
        provenance_type=ProvenanceType.USER_INPUT,
        verification_status=VerificationStatus.VERIFIED,
        evidence_type=EvidenceType.NONE,
        evidences=[],
        supporting_answer_ids=[uuid4()],
        requires_user_confirmation=False,
    )

    result = AIPolicyValidator().validate(response([unsupported]))
    validated_claim = result.candidates[0].claims[0]

    assert validated_claim.provenance_type == ProvenanceType.AI_INFERRED
    assert validated_claim.verification_status == VerificationStatus.NEEDS_CONFIRMATION
    assert PolicyViolationType.INVALID_PROVENANCE in validated_claim.policy_violations


def test_stored_answer_removes_repeated_question_without_generated_claim() -> None:
    answer = UserAnswer(
        answer_id=uuid4(),
        question_id=uuid4(),
        target_section="RESULT",
        answer="오류 문의가 줄었습니다.",
    )
    repeated_question = GapQuestion(
        question_id=uuid4(),
        target_section="RESULT",
        question="어떤 결과가 있었나요?",
    )

    result = AIPolicyValidator().validate(
        response([], [repeated_question]),
        user_answers=[answer],
    )

    assert result.questions == []
    assert result.information_need is None


def test_rejected_claim_with_same_evidence_is_not_proposed_again() -> None:
    rejected_claim = claim()
    correction = UserCorrection(
        section_type=rejected_claim.section_type,
        original_content=rejected_claim.content,
        decision="REJECTED",
        evidence_source_ids=[rejected_claim.evidences[0].source_id],
        evidence_chunk_ids=[rejected_claim.evidences[0].chunk_id],
    )

    result = AIPolicyValidator().validate(
        response([rejected_claim]),
        corrections=[correction],
    )

    assert result.candidates == []
    assert result.result_types == [AnalysisResultType.NO_UPDATE]
    assert "이미 거절" in result.no_update_reason


def test_rejected_claim_can_be_reconsidered_with_new_evidence() -> None:
    old_evidence = evidence("프로젝트 팀은 사용자 인터뷰를 진행했다.")
    new_evidence = evidence("추가 인터뷰 기록에서 같은 활동이 다시 확인됐다.")
    proposed = claim(evidences=[old_evidence, new_evidence])
    correction = UserCorrection(
        section_type=proposed.section_type,
        original_content=proposed.content,
        decision="REJECTED",
        evidence_source_ids=[old_evidence.source_id],
        evidence_chunk_ids=[old_evidence.chunk_id],
    )

    result = AIPolicyValidator().validate(
        response([proposed]),
        corrections=[correction],
    )

    assert len(result.candidates) == 1
    assert len(result.candidates[0].claims) == 1


def test_rejection_without_evidence_snapshot_does_not_block_evidenced_claim() -> None:
    proposed = claim()
    correction = UserCorrection(
        section_type=proposed.section_type,
        original_content=proposed.content,
        decision="REJECTED",
    )

    result = AIPolicyValidator().validate(
        response([proposed]),
        corrections=[correction],
    )

    assert len(result.candidates) == 1
