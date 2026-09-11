from typing import List, Optional
from uuid import UUID

from pydantic import Field, model_validator

from logfolio_ai.models.base import ContractModel
from logfolio_ai.models.enums import (
    EvidenceType,
    PolicyViolationType,
    ProvenanceType,
    SubjectType,
    VerificationStatus,
)


class DocumentPage(ContractModel):
    page_number: Optional[int] = Field(default=None, ge=1)
    text: str = Field(min_length=1)


class DocumentSource(ContractModel):
    source_id: UUID
    file_name: str = Field(min_length=1, max_length=255)
    mime_type: Optional[str] = Field(default=None, max_length=100)
    pages: List[DocumentPage] = Field(min_length=1)


class AnalysisRequest(ContractModel):
    analysis_run_id: UUID
    project_id: UUID
    documents: List[DocumentSource] = Field(min_length=1, max_length=3)


class Evidence(ContractModel):
    source_id: UUID
    chunk_id: UUID
    page_number: Optional[int] = Field(default=None, ge=1)
    quote: str = Field(min_length=1)


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


class ExperienceCandidate(ContractModel):
    candidate_id: UUID
    title: str = Field(min_length=1, max_length=255)
    summary: str = Field(min_length=1)
    claims: List[Claim] = Field(default_factory=list)


class GapQuestion(ContractModel):
    question_id: UUID
    target_section: str = Field(
        min_length=1,
        description="Spring-owned target section value defined by the shared ERD contract.",
    )
    question: str = Field(min_length=1)
    suggested_answers: List[str] = Field(default_factory=list)


class AnalysisResponse(ContractModel):
    analysis_run_id: UUID
    project_id: UUID
    summary: str = Field(min_length=1)
    candidates: List[ExperienceCandidate] = Field(default_factory=list, max_length=3)
    questions: List[GapQuestion] = Field(default_factory=list, max_length=2)
