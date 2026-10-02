from typing import List, Optional
from uuid import UUID

from pydantic import Field, model_validator

from logfolio_ai.models.base import ContractModel
from logfolio_ai.models.enums import (
    AnalysisResultType,
    EvidenceType,
    InformationNeedType,
    PolicyViolationType,
    ProvenanceType,
    SubjectType,
    SourceType,
    SourceWarningAction,
    SourceWarningType,
    VerificationStatus,
)


class DocumentPage(ContractModel):
    page_number: Optional[int] = Field(default=None, ge=1)
    text: str = Field(min_length=1)


class DocumentSource(ContractModel):
    source_id: UUID
    source_type: SourceType = SourceType.PROJECT_FILE
    source_name: str = Field(min_length=1, max_length=255)
    mime_type: Optional[str] = Field(default=None, max_length=100)
    content_hash: Optional[str] = Field(
        default=None,
        pattern="^[a-f0-9]{64}$",
        description="SHA-256 of the original file bytes or canonical Quick Log text.",
    )
    pages: List[DocumentPage] = Field(min_length=1)


class ProjectContext(ContractModel):
    name: str = Field(min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=4000)
    activity_type: Optional[str] = Field(default=None, max_length=100)
    user_role: Optional[str] = Field(default=None, max_length=200)


class AnalysisRequest(ContractModel):
    analysis_run_id: UUID
    project_id: UUID
    source_ids: List[UUID] = Field(default_factory=list, max_length=50)
    project_context: Optional[ProjectContext] = None
    confirmed_source_ids: List[UUID] = Field(default_factory=list, max_length=50)
    documents: List[DocumentSource] = Field(
        default_factory=list,
        max_length=3,
        description="Deprecated inline indexing input. Use the Source indexing API.",
    )
    existing_experiences: List["ExistingExperience"] = Field(
        default_factory=list,
        max_length=100,
    )
    corrections: List["UserCorrection"] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def validate_analysis_sources(self) -> "AnalysisRequest":
        if not self.source_ids and not self.documents:
            raise ValueError("sourceIds or legacy documents must contain at least one source")
        if self.source_ids and self.documents:
            raise ValueError("sourceIds and legacy documents cannot be used together")
        effective_source_ids = set(self.source_ids) or {
            document.source_id for document in self.documents
        }
        if not set(self.confirmed_source_ids).issubset(effective_source_ids):
            raise ValueError("confirmedSourceIds must be included in analysis sources")
        return self


class ExistingClaim(ContractModel):
    section_type: str = Field(min_length=1)
    content: str = Field(min_length=1)


class ExistingEvidence(ContractModel):
    evidence_id: UUID
    source_id: UUID
    chunk_id: UUID


class ExistingExperience(ContractModel):
    experience_id: UUID
    title: str = Field(min_length=1, max_length=255)
    summary: Optional[str] = None
    claims: List[ExistingClaim] = Field(default_factory=list)
    evidence_ids: List[UUID] = Field(default_factory=list)
    evidences: List[ExistingEvidence] = Field(default_factory=list)


class UserCorrection(ContractModel):
    experience_id: Optional[UUID] = None
    section_type: Optional[str] = None
    original_content: Optional[str] = None
    corrected_content: Optional[str] = None
    decision: str = Field(pattern="^(EDITED|REJECTED)$")


class Evidence(ContractModel):
    source_id: UUID
    source_type: SourceType = SourceType.PROJECT_FILE
    chunk_id: UUID
    page_number: Optional[int] = Field(default=None, ge=1)
    excerpt: str = Field(min_length=1)


class Claim(ContractModel):
    section_type: str = Field(
        min_length=1,
        description="Spring-owned experience section value defined by the shared ERD contract.",
    )
    content: str = Field(min_length=1)
    subject_type: SubjectType
    provenance_type: ProvenanceType
    verification_status: VerificationStatus
    evidence_type: EvidenceType
    evidences: List[Evidence] = Field(default_factory=list)
    policy_violations: List[PolicyViolationType] = Field(default_factory=list)
    requires_user_confirmation: bool

    @model_validator(mode="after")
    def validate_grounding_contract(self) -> "Claim":
        has_evidence = bool(self.evidences)

        if self.evidence_type == EvidenceType.NONE and has_evidence:
            raise ValueError("evidenceType NONE cannot include evidences")

        if self.evidence_type != EvidenceType.NONE and not has_evidence:
            raise ValueError("DIRECT or INDIRECT evidenceType requires evidence")

        if self.provenance_type == ProvenanceType.SOURCE_EXTRACTED and not has_evidence:
            raise ValueError("SOURCE_EXTRACTED claim requires evidence")

        if (
            self.verification_status == VerificationStatus.NEEDS_CONFIRMATION
            and not self.requires_user_confirmation
        ):
            raise ValueError(
                "NEEDS_CONFIRMATION requires requiresUserConfirmation=true"
            )

        return self


class ConflictDetail(ContractModel):
    section_type: str = Field(min_length=1)
    existing_content: str = Field(min_length=1)
    proposed_content: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class ExperienceCandidate(ContractModel):
    candidate_id: UUID
    result_type: AnalysisResultType = AnalysisResultType.NEW_EXPERIENCE
    target_experience_id: Optional[UUID] = None
    conflict: bool = False
    conflicts: List[ConflictDetail] = Field(default_factory=list, max_length=10)
    title: str = Field(min_length=1, max_length=255)
    summary: str = Field(min_length=1)
    claims: List[Claim] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_result_mapping(self) -> "ExperienceCandidate":
        if (
            self.result_type == AnalysisResultType.EXISTING_UPDATE
            and self.target_experience_id is None
        ):
            raise ValueError("EXISTING_UPDATE requires targetExperienceId")
        if (
            self.result_type != AnalysisResultType.EXISTING_UPDATE
            and self.target_experience_id is not None
        ):
            raise ValueError("only EXISTING_UPDATE can reference targetExperienceId")
        if self.conflict and self.result_type != AnalysisResultType.EXISTING_UPDATE:
            raise ValueError("conflict is only valid for EXISTING_UPDATE")
        if self.conflict and not self.conflicts:
            raise ValueError("conflict=true requires conflict details")
        if not self.conflict and self.conflicts:
            raise ValueError("conflict details require conflict=true")
        claim_pairs = {
            (claim.section_type.upper(), " ".join(claim.content.split()))
            for claim in self.claims
        }
        invalid_proposals = [
            detail
            for detail in self.conflicts
            if (
                detail.section_type.upper(),
                " ".join(detail.proposed_content.split()),
            )
            not in claim_pairs
        ]
        if invalid_proposals:
            raise ValueError("conflict proposedContent must reference a candidate claim")
        return self


class GapQuestion(ContractModel):
    question_id: UUID
    candidate_id: Optional[UUID] = Field(
        default=None,
        description=(
            "Experience candidate this question supplements. Null when no candidate "
            "can be created from the available evidence."
        ),
    )
    target_section: str = Field(
        min_length=1,
        description="Spring-owned target section value defined by the shared ERD contract.",
    )
    question: str = Field(min_length=1)
    suggested_answers: List[str] = Field(default_factory=list)


class SourceWarning(ContractModel):
    source_id: UUID
    source_name: str = Field(min_length=1, max_length=255)
    warning_type: SourceWarningType = SourceWarningType.POSSIBLE_PROJECT_MISMATCH
    distance: float = Field(ge=0, le=2)
    message: str = Field(min_length=1)
    allowed_actions: List[SourceWarningAction] = Field(
        default_factory=lambda: [
            SourceWarningAction.EXCLUDE_FROM_ANALYSIS,
            SourceWarningAction.INCLUDE_ANYWAY,
        ]
    )


class AnalysisResponse(ContractModel):
    analysis_run_id: UUID
    project_id: UUID
    summary: str = Field(min_length=1)
    candidates: List[ExperienceCandidate] = Field(default_factory=list, max_length=3)
    questions: List[GapQuestion] = Field(default_factory=list, max_length=2)
    source_warnings: List[SourceWarning] = Field(default_factory=list, max_length=50)
    information_need: Optional[InformationNeedType] = None
    information_need_reason: Optional[str] = Field(default=None, min_length=1)
    result_types: List[AnalysisResultType] = Field(default_factory=list)
    no_update_reason: Optional[str] = None

    @model_validator(mode="after")
    def validate_question_candidate_references(self) -> "AnalysisResponse":
        candidate_ids = {candidate.candidate_id for candidate in self.candidates}
        unknown_ids = {
            question.candidate_id
            for question in self.questions
            if question.candidate_id is not None
            and question.candidate_id not in candidate_ids
        }
        if unknown_ids:
            raise ValueError("question candidateId must reference a returned candidate")
        result_types = {candidate.result_type for candidate in self.candidates}
        if self.questions:
            result_types.add(AnalysisResultType.NEEDS_CONTEXT)
            if self.information_need is None:
                self.information_need = InformationNeedType.USER_ANSWER
        if self.information_need == InformationNeedType.USER_ANSWER and not self.questions:
            raise ValueError("USER_ANSWER informationNeed requires questions")
        if self.information_need == InformationNeedType.ADDITIONAL_SOURCE:
            if self.candidates or self.questions:
                raise ValueError(
                    "ADDITIONAL_SOURCE cannot include candidates or questions"
                )
            if self.information_need_reason is None:
                raise ValueError(
                    "ADDITIONAL_SOURCE requires informationNeedReason"
                )
            result_types.add(AnalysisResultType.NEEDS_CONTEXT)
        if self.information_need_reason is not None and self.information_need is None:
            raise ValueError("informationNeedReason requires informationNeed")
        if self.source_warnings:
            result_types.add(AnalysisResultType.NEEDS_CONTEXT)
        if (
            not self.candidates
            and not self.questions
            and not self.source_warnings
            and self.information_need is None
        ):
            result_types.add(AnalysisResultType.NO_UPDATE)
        if AnalysisResultType.NO_UPDATE in result_types and (
            self.candidates or self.questions or self.source_warnings
        ):
            raise ValueError(
                "NO_UPDATE cannot include candidates, questions, or source warnings"
            )
        self.result_types = sorted(result_types, key=lambda value: value.value)
        return self


class SourceIndexRequest(ContractModel):
    project_id: UUID
    sources: List[DocumentSource] = Field(min_length=1, max_length=20)


class SourceIndexItem(ContractModel):
    source_id: UUID
    source_type: SourceType
    status: str = Field(pattern="^(INDEXED|DUPLICATE|FAILED)$")
    chunk_count: int = Field(default=0, ge=0)
    duplicate_of_source_id: Optional[UUID] = None
    error_code: Optional[str] = None


class SourceIndexResponse(ContractModel):
    project_id: UUID
    indexed_count: int = Field(ge=0)
    duplicate_count: int = Field(default=0, ge=0)
    failed_count: int = Field(ge=0)
    items: List[SourceIndexItem]
