from logfolio_ai.core.usage import UsageCostCalculator, UsagePricing
from logfolio_ai.models import LLMCallMetrics


def test_usage_cost_calculates_only_with_complete_versioned_rates() -> None:
    calculator = UsageCostCalculator(
        UsagePricing(
            version="2026-10-02",
            input_per_million_usd=1,
            cached_input_per_million_usd=0.5,
            output_per_million_usd=2,
            reasoning_per_million_usd=3,
            usd_to_krw=1400,
        )
    )

    result = calculator.build_record(
        LLMCallMetrics(
            provider="gemini",
            model="test-model",
            input_tokens=1_000_000,
            cached_input_tokens=100_000,
            output_tokens=500_000,
            reasoning_tokens=100_000,
            latency_ms=123,
            retry_count=1,
        )
    )

    assert result.task_type == "PROJECT_ANALYSIS"
    assert result.estimated_cost_usd == 2.35
    assert result.estimated_cost_krw == 3290
    assert result.pricing_version == "2026-10-02"


def test_usage_cost_does_not_invent_cost_when_pricing_is_incomplete() -> None:
    calculator = UsageCostCalculator(
        UsagePricing(version="missing-output-rate", input_per_million_usd=1)
    )

    result = calculator.build_record(
        LLMCallMetrics(
            provider="gemini",
            model="test-model",
            input_tokens=10,
            cached_input_tokens=0,
            output_tokens=5,
            reasoning_tokens=0,
            latency_ms=1,
        )
    )

    assert result.estimated_cost_usd is None
    assert result.estimated_cost_krw is None
    assert result.pricing_version == "missing-output-rate"
