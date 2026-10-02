import re
from dataclasses import dataclass
from typing import Dict, Tuple

from logfolio_ai.llm.models import GroundedAnalysisInput


@dataclass(frozen=True)
class RedactionSummary:
    counts: Dict[str, int]

    @property
    def total(self) -> int:
        return sum(self.counts.values())


class PrivacyRedactor:
    """Minimize personal and secret data before an external LLM call."""

    _PATTERNS = (
        (
            "SECRET",
            re.compile(r"\b(?:AIza[0-9A-Za-z_-]{20,}|sk-[0-9A-Za-z_-]{16,})\b"),
            "[비밀정보]",
        ),
        (
            "RESIDENT_ID",
            re.compile(r"(?<!\d)\d{6}-?[1-4]\d{6}(?!\d)"),
            "[고유식별정보]",
        ),
        (
            "EMAIL",
            re.compile(
                r"(?<![A-Za-z0-9._%+-])"
                r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
                r"(?=$|[^A-Za-z0-9.-])"
            ),
            "[이메일]",
        ),
        (
            "PHONE",
            re.compile(r"(?<!\d)(?:01[016789]|0[2-6][1-5]?)[- .]?\d{3,4}[- .]?\d{4}(?!\d)"),
            "[전화번호]",
        ),
        (
            "FINANCIAL",
            re.compile(
                r"(?P<label>(?:계좌(?:번호)?|카드번호)\s*[:：]?\s*)"
                r"\d[\d -]{7,22}\d"
            ),
            r"\g<label>[금융정보]",
        ),
        (
            "ADDRESS",
            re.compile(r"(?P<label>(?:주소|상세주소)\s*[:：]\s*)[^\n,;]{3,120}"),
            r"\g<label>[주소정보]",
        ),
        (
            "THIRD_PARTY_NAME",
            re.compile(
                r"(?<![가-힣])([가-힣]{2,4})(?=\s*(?:개발자|기획자|디자이너|"
                r"팀원|고객|인터뷰\s*참여자))"
            ),
            "[제3자]",
        ),
        (
            "SENSITIVE",
            re.compile(
                r"(?P<label>(?:건강정보|질병|병력|정치성향|종교)\s*[:：]\s*)"
                r"[^\n,;]{1,100}"
            ),
            r"\g<label>[민감정보]",
        ),
    )

    def redact_text(self, value: str) -> Tuple[str, RedactionSummary]:
        redacted = value
        counts: Dict[str, int] = {}
        for category, pattern, replacement in self._PATTERNS:
            redacted, count = pattern.subn(replacement, redacted)
            if count:
                counts[category] = counts.get(category, 0) + count
        return redacted, RedactionSummary(counts=counts)

    def sanitize_grounded_input(
        self,
        request: GroundedAnalysisInput,
    ) -> Tuple[GroundedAnalysisInput, RedactionSummary]:
        counts: Dict[str, int] = {}

        def sanitize(value):
            if value is None:
                return None
            redacted, summary = self.redact_text(value)
            for category, count in summary.counts.items():
                counts[category] = counts.get(category, 0) + count
            return redacted

        chunks = [
            chunk.model_copy(
                update={
                    "source_name": sanitize(chunk.source_name),
                    "section_title": sanitize(chunk.section_title),
                    "text": sanitize(chunk.text),
                }
            )
            for chunk in request.chunks
        ]
        experiences = [
            experience.model_copy(
                update={
                    "title": sanitize(experience.title),
                    "summary": sanitize(experience.summary),
                    "claims": [
                        claim.model_copy(update={"content": sanitize(claim.content)})
                        for claim in experience.claims
                    ],
                }
            )
            for experience in request.existing_experiences
        ]
        corrections = [
            correction.model_copy(
                update={
                    "original_content": sanitize(correction.original_content),
                    "corrected_content": sanitize(correction.corrected_content),
                }
            )
            for correction in request.corrections
        ]
        answers = [
            answer.model_copy(update={"answer": sanitize(answer.answer)})
            for answer in request.answers
        ]
        sanitized = request.model_copy(
            update={
                "chunks": chunks,
                "existing_experiences": experiences,
                "corrections": corrections,
                "answers": answers,
            }
        )
        return sanitized, RedactionSummary(counts=counts)
