from typing import Dict, Iterable, List, Sequence, Set, Tuple
from uuid import UUID

from logfolio_ai.models import (
    AnalysisResponse,
    AnalysisResultType,
    Claim,
    ConflictDetail,
    ExperienceCandidate,
    GapQuestion,
    InformationNeedType,
    PolicyViolationType,
    ProvenanceType,
    SubjectType,
    UserAnswer,
    UserCorrection,
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

    @staticmethod
    def _normalize_claim_content(value: str) -> str:
        return " ".join(value.lower().split())

    def _claim_key(self, claim: Claim) -> Tuple[str, str]:
        return (
            claim.section_type.upper(),
            self._normalize_claim_content(claim.content),
        )

    def _new_candidate_key(self, candidate: ExperienceCandidate) -> Tuple:
        """Identify only exact duplicate new-experience proposals.

        Shared Sources or Evidence are deliberately excluded: one Source can contain
        multiple independent experiences, so evidence overlap alone is never a merge
        signal.
        """
        return (
            self._normalize_claim_content(candidate.title),
            self._normalize_claim_content(candidate.summary),
            tuple(sorted(self._claim_key(claim) for claim in candidate.claims)),
        )

    def _merge_candidates(
        self,
        candidates: Sequence[ExperienceCandidate],
    ) -> Tuple[List[ExperienceCandidate], Dict[UUID, UUID]]:
        merged: List[ExperienceCandidate] = []
        positions: Dict[Tuple, int] = {}
        candidate_id_remap: Dict[UUID, UUID] = {}

        for candidate in candidates:
            if candidate.result_type == AnalysisResultType.EXISTING_UPDATE:
                key = ("EXISTING_UPDATE", candidate.target_experience_id)
            else:
                key = ("NEW_EXPERIENCE",) + self._new_candidate_key(candidate)

            if key not in positions:
                positions[key] = len(merged)
                merged.append(candidate)
                continue

            kept_index = positions[key]
            kept = merged[kept_index]
            candidate_id_remap[candidate.candidate_id] = kept.candidate_id

            claim_keys = {self._claim_key(item) for item in kept.claims}
            combined_claims = list(kept.claims)
            for item in candidate.claims:
                item_key = self._claim_key(item)
                if item_key not in claim_keys:
                    claim_keys.add(item_key)
                    combined_claims.append(item)

            conflict_keys = {
                (
                    item.section_type.upper(),
                    self._normalize_claim_content(item.existing_content),
                    self._normalize_claim_content(item.proposed_content),
                )
                for item in kept.conflicts
            }
            combined_conflicts = list(kept.conflicts)
            for item in candidate.conflicts:
                item_key = (
                    item.section_type.upper(),
                    self._normalize_claim_content(item.existing_content),
                    self._normalize_claim_content(item.proposed_content),
                )
                if item_key not in conflict_keys:
                    conflict_keys.add(item_key)
                    combined_conflicts.append(item)

            merged[kept_index] = kept.model_copy(
                update={
                    "claims": combined_claims,
                    "conflict": bool(combined_conflicts),
                    "conflicts": combined_conflicts,
                }
            )

        return merged, candidate_id_remap

    def _matches_rejected_evidence(
        self,
        claim: Claim,
        correction: UserCorrection,
    ) -> bool:
        claim_chunk_ids = {evidence.chunk_id for evidence in claim.evidences}
        rejected_chunk_ids = set(correction.evidence_chunk_ids)
        if rejected_chunk_ids:
            return bool(claim_chunk_ids) and claim_chunk_ids.issubset(
                rejected_chunk_ids
            )

        claim_source_ids = {evidence.source_id for evidence in claim.evidences}
        rejected_source_ids = set(correction.evidence_source_ids)
        if rejected_source_ids:
            return bool(claim_source_ids) and claim_source_ids.issubset(
                rejected_source_ids
            )
        return not claim_chunk_ids and not claim_source_ids

    def _is_rejected_claim(
        self,
        claim: Claim,
        candidate,
        corrections: Sequence[UserCorrection],
    ) -> bool:
        for correction in corrections:
            if correction.decision != "REJECTED" or not correction.original_content:
                continue
            if correction.section_type and (
                correction.section_type.upper() != claim.section_type.upper()
            ):
                continue
            if correction.experience_id is not None and (
                candidate.target_experience_id != correction.experience_id
            ):
                continue
            if self._normalize_claim_content(
                correction.original_content
            ) != self._normalize_claim_content(claim.content):
                continue
            if self._matches_rejected_evidence(claim, correction):
                return True
        return False

    def _protect_user_edits(
        self,
        candidate,
        claims: Sequence[Claim],
        conflicts: Sequence[ConflictDetail],
        corrections: Sequence[UserCorrection],
    ) -> List[ConflictDetail]:
        if candidate.target_experience_id is None:
            return list(conflicts)

        latest_by_section = {}
        for correction in corrections:
            if (
                correction.decision == "EDITED"
                and correction.experience_id == candidate.target_experience_id
                and correction.section_type
                and correction.corrected_content
            ):
                latest_by_section[correction.section_type.upper()] = correction

        protected = list(conflicts)
        existing_pairs = {
            (
                conflict.section_type.upper(),
                self._normalize_claim_content(conflict.existing_content),
                self._normalize_claim_content(conflict.proposed_content),
            )
            for conflict in protected
        }
        for claim in claims:
            correction = latest_by_section.get(claim.section_type.upper())
            if correction is None:
                continue
            if self._normalize_claim_content(
                claim.content
            ) == self._normalize_claim_content(correction.corrected_content):
                continue
            pair = (
                claim.section_type.upper(),
                self._normalize_claim_content(correction.corrected_content),
                self._normalize_claim_content(claim.content),
            )
            if pair in existing_pairs:
                continue
            protected.append(
                ConflictDetail(
                    section_type=claim.section_type,
                    existing_content=correction.corrected_content,
                    proposed_content=claim.content,
                    reason=(
                        "사용자가 수정해 확정한 값과 새 AI 제안이 다르므로 "
                        "자동으로 덮어쓰지 않고 확인이 필요합니다."
                    ),
                )
            )
            existing_pairs.add(pair)
        return protected

    def validate(
        self,
        response: AnalysisResponse,
        *,
        user_answers: Sequence[UserAnswer] = (),
        corrections: Sequence[UserCorrection] = (),
    ) -> AnalysisResponse:
        answers_by_id = {answer.answer_id: answer for answer in user_answers}
        validated_candidates = []
        removed_candidate_ids = set()
        for candidate in response.candidates:
            claims = []
            for claim in candidate.claims:
                validated_claim = self.validate_claim(claim, answers_by_id)
                if self._is_rejected_claim(
                    validated_claim,
                    candidate,
                    corrections,
                ):
                    continue
                claims.append(validated_claim)
            if candidate.claims and not claims:
                removed_candidate_ids.add(candidate.candidate_id)
                continue
            valid_claim_pairs = {
                (
                    claim.section_type.upper(),
                    self._normalize_claim_content(claim.content),
                )
                for claim in claims
            }
            conflicts = [
                conflict
                for conflict in candidate.conflicts
                if (
                    conflict.section_type.upper(),
                    self._normalize_claim_content(conflict.proposed_content),
                )
                in valid_claim_pairs
            ]
            conflicts = self._protect_user_edits(
                candidate,
                claims,
                conflicts,
                corrections,
            )
            validated_candidates.append(
                candidate.model_copy(
                    update={
                        "claims": claims,
                        "conflict": bool(conflicts),
                        "conflicts": conflicts,
                    }
                )
            )

        validated_candidates, candidate_id_remap = self._merge_candidates(
            validated_candidates
        )
        all_claims = [
            claim for candidate in validated_candidates for claim in candidate.claims
        ]
        questions = self._filter_questions(response, all_claims, user_answers)
        questions = [
            question.model_copy(
                update={
                    "candidate_id": candidate_id_remap.get(
                        question.candidate_id,
                        question.candidate_id,
                    )
                }
            )
            if question.candidate_id not in removed_candidate_ids
            else question.model_copy(update={"candidate_id": None})
            for question in questions
        ]
        payload = response.model_dump()
        payload.update({"candidates": validated_candidates, "questions": questions})
        if not validated_candidates and not questions:
            payload["no_update_reason"] = (
                response.no_update_reason
                or "사용자가 동일한 근거로 이미 거절한 제안입니다."
            )
        if (
            not questions
            and payload.get("information_need") == InformationNeedType.USER_ANSWER
        ):
            payload["information_need"] = None
            payload["information_need_reason"] = None
        return AnalysisResponse.model_validate(payload)
