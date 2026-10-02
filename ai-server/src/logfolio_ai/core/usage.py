from dataclasses import dataclass
from typing import Optional

from logfolio_ai.models import AIUsageRecord, LLMCallMetrics


@dataclass(frozen=True)
class UsagePricing:
    version: Optional[str] = None
    input_per_million_usd: Optional[float] = None
    cached_input_per_million_usd: Optional[float] = None
    output_per_million_usd: Optional[float] = None
    reasoning_per_million_usd: Optional[float] = None
    usd_to_krw: Optional[float] = None


class UsageCostCalculator:
    def __init__(self, pricing: UsagePricing) -> None:
        self._pricing = pricing

    def build_record(self, metrics: LLMCallMetrics) -> AIUsageRecord:
        token_values = (
            metrics.input_tokens,
            metrics.cached_input_tokens,
            metrics.output_tokens,
            metrics.reasoning_tokens,
        )
        rates = (
            self._pricing.input_per_million_usd,
            self._pricing.cached_input_per_million_usd,
            self._pricing.output_per_million_usd,
            self._pricing.reasoning_per_million_usd,
        )
        cost_usd = None
        cost_krw = None
        if all(value is not None for value in token_values) and all(
            rate is not None for rate in rates
        ):
            cost_usd = sum(
                value * rate for value, rate in zip(token_values, rates)
            ) / 1_000_000
            if self._pricing.usd_to_krw is not None:
                cost_krw = cost_usd * self._pricing.usd_to_krw

        return AIUsageRecord(
            **metrics.model_dump(),
            estimated_cost_usd=cost_usd,
            estimated_cost_krw=cost_krw,
            pricing_version=self._pricing.version,
        )
