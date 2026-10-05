from typing import Optional

from pydantic import Field

from logfolio_ai.models.base import ContractModel


class LLMCallMetrics(ContractModel):
    provider: str
    model: str
    input_tokens: Optional[int] = Field(default=None, ge=0)
    cached_input_tokens: Optional[int] = Field(default=None, ge=0)
    output_tokens: Optional[int] = Field(default=None, ge=0)
    reasoning_tokens: Optional[int] = Field(default=None, ge=0)
    latency_ms: int = Field(ge=0)
    retry_count: int = Field(default=0, ge=0)
    success: bool = True
    error_type: Optional[str] = None


class AIUsageRecord(LLMCallMetrics):
    task_type: str = "PROJECT_ANALYSIS"
    estimated_cost_usd: Optional[float] = Field(default=None, ge=0)
    estimated_cost_krw: Optional[float] = Field(default=None, ge=0)
    pricing_version: Optional[str] = None
