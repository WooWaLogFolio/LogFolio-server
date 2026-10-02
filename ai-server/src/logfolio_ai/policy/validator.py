from typing import Dict, Iterable, List, Sequence, Set
from uuid import UUID

from logfolio_ai.models import (
    AnalysisResponse,
    Claim,
    GapQuestion,
    InformationNeedType,
    PolicyViolationType,
    ProvenanceType,
    SubjectType,
    UserAnswer,
    VerificationStatus,
)
from logfolio_ai.models.enums import EvidenceType

_ANSWER_PROVENANCE = {ProvenanceType.USER_INPUT, ProvenanceType.USER_EDITED}
_FIRST_PERSON_MARKERS = ("내가", "나는", "제가", "저는", "본인이")
_TEAM_MARKERS = ("우리 팀", "프로젝트 팀", "팀은", "팀이", "팀에서", "팀원")
_QUESTION_PRIORITY: Dict[str, int] = {
    "CONTRIBUTION": 0,
    "ROLE": 0,
    "ACTION": 0,
    "DECISION": 1,
    "RESULT": 2,
    "OUTCOME": 2,
    "REASON": 3,
    "LEARNING": 4,
}


class AIPolicyValidator:
    """Apply deterministic safety rules after LLM schema validation."""

    @staticmethod
    def _append_violations(
        existing: Iterable[PolicyViolationType],
        additions: Iterable[PolicyViolationType],
    ) -> List[PolicyViolationType]:
        result = list(existing)
        for violation in additions:
            if violation not in result:
                result.append(violation)
        return result

    @staticmethod
    def _has_marker(claim: Claim, markers: Iterable[str]) -> bool:
        return any(
            marker in evidence.excerpt
            for evidence in claim.evidences
            for marker in markers
        )

    @staticmethod
    def _has_valid_answer_support(
        claim: Claim,
        answers_by_id: Dict[UUID, UserAnswer],
    ) -> bool:
        if claim.provenance_type not in _ANSWER_PROVENANCE:
            return False
        if not claim.supporting_answer_ids:
            return False
        answers = [answers_by_id.get(answer_id) for answer_id in claim.supporting_answer_ids]
        return all(
            answer is not None
            and answer.target_section.upper() == claim.section_type.upper()
            and answer.provenance_type == claim.provenance_type
            for answer in answers
        )

    def validate_claim(
        self,
        claim: Claim,
        answers_by_id: Dict[UUID, UserAnswer],
    ) -> Claim:
        updates = {}
        violations: List[PolicyViolationType] = []
        has_valid_answer_support = self._has_valid_answer_support(
            claim,
            answers_by_id,
        )

        if claim.provenance_type == ProvenanceType.USER_CONFIRMED or (
            claim.provenance_type in _ANSWER_PROVENANCE
            and not has_valid_answer_support
        ):
            updates["provenance_type"] = ProvenanceType.AI_INFERRED
            updates["verification_status"] = VerificationStatus.NEEDS_CONFIRMATION
            updates["requires_user_confirmation"] = True
            violations.append(PolicyViolationType.INVALID_PROVENANCE)

        if not claim.evidences and has_valid_answer_support:
            updates["evidence_type"] = EvidenceType.NONE
            updates["verification_status"] = VerificationStatus.VERIFIED
            updates["requires_user_confirmation"] = False
        elif not claim.evidences:
            updates["evidence_type"] = EvidenceType.NONE
            updates["provenance_type"] = ProvenanceType.AI_INFERRED
            updates["verification_status"] = VerificationStatus.NEEDS_CONFIRMATION
            updates["requires_user_confirmation"] = True
            violations.append(PolicyViolationType.MISSING_EVIDENCE)
            section = claim.section_type.upper()
            if section in {"RESULT", "OUTCOME", "ACHIEVEMENT"}:
                violations.append(PolicyViolationType.UNSUPPORTED_ACHIEVEMENT)
            if section in {"ROLE", "CONTRIBUTION"}:
                violations.append(PolicyViolationType.UNSUPPORTED_ROLE)

        if claim.subject_type == SubjectType.USER:
            has_direct_user_signal = has_valid_answer_support or self._has_marker(
                claim,
                _FIRST_PERSON_MARKERS,
            )
            if not has_direct_user_signal:
                updates["subject_type"] = SubjectType.UNKNOWN
                updates["provenance_type"] = ProvenanceType.AI_INFERRED
                updates["verification_status"] = VerificationStatus.NEEDS_CONFIRMATION
                updates["requires_user_confirmation"] = True
                violations.append(PolicyViolationType.UNSUPPORTED_USER_CONTRIBUTION)
                if self._has_marker(claim, _TEAM_MARKERS):
                    violations.append(PolicyViolationType.TEAM_TO_USER_ATTRIBUTION)

        effective_provenance = updates.get("provenance_type", claim.provenance_type)
        effective_subject = updates.get("subject_type", claim.subject_type)
        if (
            effective_provenance == ProvenanceType.AI_INFERRED
            or effective_subject == SubjectType.UNKNOWN
        ):
            updates["verification_status"] = VerificationStatus.NEEDS_CONFIRMATION
            updates["requires_user_confirmation"] = True

        updates["policy_violations"] = self._append_violations(
            claim.policy_violations,
            violations,
        )
        payload = claim.model_dump()
        payload.update(updates)
        return Claim.model_validate(payload)

    @staticmethod
    def _normalize_question(question: str) -> str:
        return " ".join(question.lower().split())

    def _filter_questions(
        self,
        response: AnalysisResponse,
        claims: List[Claim],
        user_answers: Sequence[UserAnswer],
    ) -> List[GapQuestion]:
        answered_sections: Set[str] = {
            claim.section_type.upper()
            for claim in claims
            if claim.verification_status == VerificationStatus.VERIFIED
            and claim.provenance_type
            in {
                ProvenanceType.SOURCE_EXTRACTED,
                ProvenanceType.USER_INPUT,
                ProvenanceType.USER_EDITED,
            }
        }
        answered_sections.update(
            answer.target_section.upper() for answer in user_answers
        )
        seen: Set[str] = set()
        kept: List[GapQuestion] = []
        for question in sorted(
            response.questions,
            key=lambda item: _QUESTION_PRIORITY.get(item.target_section.upper(), 99),
        ):
            normalized = self._normalize_question(question.question)
            if question.target_section.upper() in answered_sections or normalized in seen:
                continue
            seen.add(normalized)
            kept.append(question)
        return kept[:2]

    def validate(
        self,
        response: AnalysisResponse,
        *,
        user_answers: Sequence[UserAnswer] = (),
    ) -> AnalysisResponse:
        answers_by_id = {answer.answer_id: answer for answer in user_answers}
        validated_candidates = []
        all_claims: List[Claim] = []
        for candidate in response.candidates:
            claims = [
                self.validate_claim(claim, answers_by_id)
                for claim in candidate.claims
            ]
            all_claims.extend(claims)
            validated_candidates.append(candidate.model_copy(update={"claims": claims}))

        questions = self._filter_questions(response, all_claims, user_answers)
        payload = response.model_dump()
        payload.update({"candidates": validated_candidates, "questions": questions})
        if (
            not questions
            and payload.get("information_need") == InformationNeedType.USER_ANSWER
        ):
            payload["information_need"] = None
            payload["information_need_reason"] = None
        return AnalysisResponse.model_validate(payload)
