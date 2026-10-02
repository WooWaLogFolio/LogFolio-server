from uuid import uuid4

from logfolio_ai.llm import GroundedAnalysisInput, GroundedChunk
from logfolio_ai.models import (
    ExistingClaim,
    ExistingExperience,
    SourceType,
    UserAnswer,
    UserCorrection,
)
from logfolio_ai.privacy import PrivacyRedactor


def test_redactor_masks_mvp_sensitive_patterns() -> None:
    original = (
        "김민수 개발자 이메일 minsu@example.com, 전화 010-1234-5678, "
        "주민번호 990101-1234567, 계좌번호 110-123-456789, "
        "주소: 서울시 종로구 세종대로 1, 건강정보: 당뇨 치료 중, "
        "API key sk-abcdefghijklmnop"
    )

    redacted, summary = PrivacyRedactor().redact_text(original)

    assert "김민수" not in redacted
    assert "minsu@example.com" not in redacted
    assert "010-1234-5678" not in redacted
    assert "990101-1234567" not in redacted
    assert "110-123-456789" not in redacted
    assert "서울시 종로구 세종대로 1" not in redacted
    assert "당뇨 치료 중" not in redacted
    assert "sk-abcdefghijklmnop" not in redacted
    assert "[제3자] 개발자" in redacted
    assert "[이메일]" in redacted
    assert "[전화번호]" in redacted
    assert "[고유식별정보]" in redacted
    assert "계좌번호 [금융정보]" in redacted
    assert "주소: [주소정보]" in redacted
    assert "건강정보: [민감정보]" in redacted
    assert "[비밀정보]" in redacted
    assert summary.total == 8


def test_grounded_input_is_sanitized_without_mutating_internal_data() -> None:
    experience_id = uuid4()
    answer = UserAnswer(
        answer_id=uuid4(),
        question_id=uuid4(),
        target_section="CONTRIBUTION",
        answer="연락처는 010-9876-5432입니다.",
    )
    request = GroundedAnalysisInput(
        analysis_run_id=uuid4(),
        project_id=uuid4(),
        chunks=[
            GroundedChunk(
                chunk_id=uuid4(),
                source_id=uuid4(),
                source_type=SourceType.PROJECT_FILE,
                source_name="minsu@example.com 회의록",
                text="김민수 팀원이 API를 구현했다.",
                distance=0.1,
            )
        ],
        existing_experiences=[
            ExistingExperience(
                experience_id=experience_id,
                title="minsu@example.com 인터뷰",
                claims=[
                    ExistingClaim(
                        section_type="ACTION",
                        content="010-1111-2222로 참여자를 모집했다.",
                    )
                ],
            )
        ],
        corrections=[
            UserCorrection(
                experience_id=experience_id,
                section_type="ACTION",
                original_content="계좌번호 110-123-456789를 받았다.",
                corrected_content="계좌번호 110-999-888888를 받았다.",
                decision="EDITED",
            )
        ],
        answers=[answer],
    )

    sanitized, summary = PrivacyRedactor().sanitize_grounded_input(request)

    assert "minsu@example.com" not in sanitized.chunks[0].source_name
    assert "김민수" not in sanitized.chunks[0].text
    assert "minsu@example.com" not in sanitized.existing_experiences[0].title
    assert "010-1111-2222" not in sanitized.existing_experiences[0].claims[0].content
    assert "110-123-456789" not in sanitized.corrections[0].original_content
    assert "010-9876-5432" not in sanitized.answers[0].answer
    assert summary.total == 7

    assert request.chunks[0].source_name == "minsu@example.com 회의록"
    assert request.answers[0].answer == answer.answer
