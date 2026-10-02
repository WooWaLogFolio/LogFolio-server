from typing import List, Optional

from pydantic import Field

from logfolio_ai.models import (
    AnalysisResponse,
    AnalysisResultType,
    EvidenceType,
    InformationNeedType,
    PolicyViolationType,
    ProvenanceType,
    SubjectType,
    VerificationStatus,
)
from logfolio_ai.models.base import ContractModel


class ClaimExpectation(ContractModel):
    candidate_index: int = Field(ge=0)
    claim_index: int = Field(ge=0)
    subject_type: Optional[SubjectType] = None
    provenance_type: Optional[ProvenanceType] = None
    verification_status: Optional[VerificationStatus] = None
    evidence_type: Optional[EvidenceType] = None
    requires_user_confirmation: Optional[bool] = None
    violations_contain: List[PolicyViolationType] = Field(default_factory=list)


class EvaluationExpectation(ContractModel):
    claims: List[ClaimExpectation] = Field(default_factory=list)
    question_targets: Optional[List[str]] = None
    information_need: Optional[InformationNeedType] = None
    result_types: Optional[List[AnalysisResultType]] = None


class EvaluationCase(ContractModel):
    case_id: str = Field(min_length=1)
    category: str = Field(min_length=1)
    description: str = Field(min_length=1)
    source_text: str = Field(min_length=1)
    raw_response: AnalysisResponse
    expected: EvaluationExpectation


class EvaluationFailure(ContractModel):
    case_id: str
    message: str


class EvaluationReport(ContractModel):
    total: int = Field(ge=0)
    passed: int = Field(ge=0)
    failed: int = Field(ge=0)
    pass_rate: float = Field(ge=0, le=1)
    failures: List[EvaluationFailure] = Field(default_factory=list)
