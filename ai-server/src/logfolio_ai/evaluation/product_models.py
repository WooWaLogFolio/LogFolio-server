from enum import Enum
from typing import List, Optional

from pydantic import Field

from logfolio_ai.llm import GroundedAnalysisInput, LLMCallMetrics
from logfolio_ai.models import (
    AnalysisResponse,
    AnalysisResultType,
    InformationNeedType,
    PolicyViolationType,
)
from logfolio_ai.models.base import ContractModel


class ProductEvalExpectation(ContractModel):
    result_type: AnalysisResultType
    target_experience_id: Optional[str] = None
    expected_experience_count: int = Field(ge=0, le=3)
    requires_question: bool
    question_intents: List[str] = Field(default_factory=list, max_length=2)
    information_need: Optional[InformationNeedType] = None
    conflict: Optional[bool] = None
    expected_claim_keywords: List[str] = Field(default_factory=list)
    forbidden_claim_keywords: List[str] = Field(default_factory=list)
    required_evidence_chunk_ids: List[str] = Field(default_factory=list)
    forbidden_phrases: List[str] = Field(default_factory=list)


class ProductEvalCase(ContractModel):
    case_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    category: str = Field(min_length=1)
    difficulty: str = Field(pattern="^(EASY|MEDIUM|HARD)$")
    description: str = Field(min_length=1)
    input: GroundedAnalysisInput
    expected: ProductEvalExpectation
    human_rubric: List[str] = Field(default_factory=list)


class AutomaticEvaluation(ContractModel):
    result_type_match: bool
    target_experience_match: bool
    experience_count_match: bool
    question_requirement_match: bool
    question_intent_match: bool
    information_need_match: bool
    conflict_match: bool
    expected_claims_match: bool = True
    forbidden_claims_absent: bool = True
    required_evidence_match: bool = True
    schema_valid: bool = True
    critical_policy_violation: bool
    forbidden_output: bool
    passed: bool
    failures: List[str] = Field(default_factory=list)


class CostEstimate(ContractModel):
    estimated_cost_usd: Optional[float] = Field(default=None, ge=0)
    estimated_cost_krw: Optional[float] = Field(default=None, ge=0)
    pricing_version: Optional[str] = None


class ProductEvalRun(ContractModel):
    case_id: str
    category: str
    run_number: int = Field(ge=1)
    provider: str
    model: str
    success: bool
    error_type: Optional[str] = None
    output: Optional[AnalysisResponse] = None
    automatic_evaluation: Optional[AutomaticEvaluation] = None
    usage: LLMCallMetrics
    cost: CostEstimate = Field(default_factory=CostEstimate)


class AcceptanceGateStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_EVALUATED = "NOT_EVALUATED"


class AcceptanceGate(ContractModel):
    name: str
    status: AcceptanceGateStatus
    actual: Optional[float] = None
    threshold: Optional[float] = None
    unit: Optional[str] = None
    reason: Optional[str] = None


class AcceptanceSummary(ContractModel):
    accepted: bool
    evaluated_gate_count: int = Field(ge=0)
    passed_gate_count: int = Field(ge=0)
    failed_gate_count: int = Field(ge=0)
    not_evaluated_gate_count: int = Field(ge=0)
    gates: List[AcceptanceGate] = Field(default_factory=list)


class ProductEvalReport(ContractModel):
    dataset: str
    provider: str
    model: str
    total_runs: int = Field(ge=0)
    passed_runs: int = Field(ge=0)
    failed_runs: int = Field(ge=0)
    pass_rate: float = Field(ge=0, le=1)
    total_estimated_cost_usd: Optional[float] = Field(default=None, ge=0)
    total_estimated_cost_krw: Optional[float] = Field(default=None, ge=0)
    acceptance: AcceptanceSummary
    runs: List[ProductEvalRun] = Field(default_factory=list)


CRITICAL_POLICY_VIOLATIONS = {
    PolicyViolationType.TEAM_TO_USER_ATTRIBUTION,
    PolicyViolationType.UNSUPPORTED_ACHIEVEMENT,
    PolicyViolationType.UNSUPPORTED_ROLE,
    PolicyViolationType.INVALID_SOURCE_REFERENCE,
}
