from typing import Dict, Iterable, List, Set

from logfolio_ai.models import (
    AnalysisResponse,
    Claim,
    GapQuestion,
    InformationNeedType,
    PolicyViolationType,
    ProvenanceType,
    SubjectType,
    VerificationStatus,
)
from logfolio_ai.models.enums import EvidenceType

_AI_FORBIDDEN_PROVENANCE = {
    ProvenanceType.USER_INPUT,
    ProvenanceType.USER_CONFIRMED,
    ProvenanceType.USER_EDITED,
}
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

    def validate_claim(self, claim: Claim) -> Claim:
        updates = {}
        violations: List[PolicyViolationType] = []

        if claim.provenance_type in _AI_FORBIDDEN_PROVENANCE:
            updates["provenance_type"] = ProvenanceType.AI_INFERRED
            updates["verification_status"] = VerificationStatus.NEEDS_CONFIRMATION
            updates["requires_user_confirmation"] = True
            violations.append(PolicyViolationType.INVALID_PROVENANCE)

        if not claim.evidences:
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
            has_direct_user_signal = self._has_marker(claim, _FIRST_PERSON_MARKERS)
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
    ) -> List[GapQuestion]:
        answered_sections: Set[str] = {
            claim.section_type.upper()
            for claim in claims
            if claim.verification_status == VerificationStatus.VERIFIED
            and claim.provenance_type == ProvenanceType.SOURCE_EXTRACTED
        }
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

    def validate(self, response: AnalysisResponse) -> AnalysisResponse:
        validated_candidates = []
        all_claims: List[Claim] = []
        for candidate in response.candidates:
            claims = [self.validate_claim(claim) for claim in candidate.claims]
            all_claims.extend(claims)
            validated_candidates.append(candidate.model_copy(update={"claims": claims}))

        questions = self._filter_questions(response, all_claims)
        payload = response.model_dump()
        payload.update({"candidates": validated_candidates, "questions": questions})
        if (
            not questions
            and payload.get("information_need") == InformationNeedType.USER_ANSWER
        ):
            payload["information_need"] = None
            payload["information_need_reason"] = None
        return AnalysisResponse.model_validate(payload)
