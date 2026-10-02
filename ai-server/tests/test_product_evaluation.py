from pathlib import Path
from uuid import uuid4

import pytest

from logfolio_ai.evaluation.product_models import ProductEvalCase
from logfolio_ai.evaluation.product_runner import (
    estimate_cost,
    evaluate_product_output,
    export_csv,
    load_product_cases,
    run_product_eval,
)
from logfolio_ai.llm import LLMCallMetrics
from logfolio_ai.models import AnalysisResponse, ExperienceCandidate


def matching_new_experience(case: ProductEvalCase) -> AnalysisResponse:
    return AnalysisResponse(
        analysis_run_id=case.input.analysis_run_id,
        project_id=case.input.project_id,
        summary="새 경험을 발견했습니다.",
        candidates=[
            ExperienceCandidate(
                candidate_id=uuid4(),
                title="JWT 갱신 오류 해결",
                summary="갱신 로직을 수정해 오류를 해결했다.",
                claims=[],
            )
        ],
        questions=[],
    )


def test_product_dataset_contains_core_and_security_gold_cases() -> None:
    cases = load_product_cases()

    assert [case.case_id for case in cases] == [
        "NEW_01",
        "UPDATE_01",
        "CONTEXT_01",
        "ATTRIBUTION_01",
        "MERGE_01",
        "PROMPT_INJECTION_01",
    ]


def test_product_evaluator_compares_product_decisions() -> None:
    case = load_product_cases(case_id="NEW_01")[0]

    result = evaluate_product_output(case, matching_new_experience(case))

    assert result.passed is True
    assert result.result_type_match is True
    assert result.experience_count_match is True
    assert result.critical_policy_violation is False


def test_cost_estimate_uses_versioned_pricing() -> None:
    metrics = LLMCallMetrics(
        provider="gemini",
        model="test-model",
        input_tokens=1_000_000,
        cached_input_tokens=0,
        output_tokens=500_000,
        reasoning_tokens=0,
        latency_ms=100,
    )

    result = estimate_cost(
        metrics,
        {
            "version": "2026-10-02",
            "usdToKrw": 1400,
            "models": {
                "gemini/test-model": {
                    "inputPerMillionUsd": 1,
                    "outputPerMillionUsd": 2,
                }
            },
        },
    )

    assert result.estimated_cost_usd == 2
    assert result.estimated_cost_krw == 2800
    assert result.pricing_version == "2026-10-02"


@pytest.mark.asyncio
async def test_runner_repeats_hard_cases_three_times_and_exports_csv(tmp_path: Path) -> None:
    case = load_product_cases(case_id="ATTRIBUTION_01")[0]

    class ScriptedProvider:
        last_call_metrics = LLMCallMetrics(
            provider="scripted",
            model="test",
            input_tokens=10,
            cached_input_tokens=0,
            output_tokens=5,
            reasoning_tokens=0,
            latency_ms=1,
        )

        async def analyze_grounded(self, request):
            return AnalysisResponse(
                analysis_run_id=request.analysis_run_id,
                project_id=request.project_id,
                summary="개인 기여 확인이 필요합니다.",
                candidates=[],
                questions=[],
                information_need="ADDITIONAL_SOURCE",
                information_need_reason="개인 기여 기록이 필요합니다.",
            )

    report = await run_product_eval(
        [case],
        ScriptedProvider(),
        provider_name="scripted",
        model="test",
        dataset_name="test",
    )
    output = tmp_path / "result.csv"
    export_csv(report, output)

    assert report.total_runs == 3
    assert output.read_text(encoding="utf-8").count("ATTRIBUTION_01") == 3
