from pathlib import Path
from uuid import uuid4

import pytest

from logfolio_ai.evaluation.product_models import ProductEvalCase
from logfolio_ai.evaluation.product_runner import (
    build_acceptance_summary,
    estimate_cost,
    evaluate_product_output,
    export_csv,
    load_product_cases,
    run_product_eval,
)
from logfolio_ai.llm import LLMCallMetrics
from logfolio_ai.models import AnalysisResponse, ExperienceCandidate
from logfolio_ai.evaluation.product_models import (
    AutomaticEvaluation,
    CostEstimate,
    ProductEvalRun,
)


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
        "SPLIT_01",
        "CONFLICT_01",
        "ADDITIONAL_SOURCE_01",
        "NO_UPDATE_01",
        "REJECTED_VALUE_01",
        "PRIVACY_01",
        "PROMPT_INJECTION_01",
        "USER_EDITED_01",
        "MIXED_SOURCE_01",
        "AMBIGUOUS_MAPPING_01",
        "ANSWERED_CONTEXT_01",
        "EVIDENCE_GROUNDING_01",
        "QUICK_FILE_CONFLICT_01",
        "REJECTED_NEW_EVIDENCE_01",
        "INSUFFICIENT_MIXED_01",
    ]


def test_product_dataset_has_unique_case_and_analysis_ids() -> None:
    cases = load_product_cases()

    assert len(cases) == 20
    assert len({case.case_id for case in cases}) == len(cases)
    assert len({case.input.analysis_run_id for case in cases}) == len(cases)


def test_product_evaluator_compares_product_decisions() -> None:
    case = load_product_cases(case_id="NEW_01")[0]

    result = evaluate_product_output(case, matching_new_experience(case))

    assert result.passed is True
    assert result.result_type_match is True
    assert result.experience_count_match is True
    assert result.critical_policy_violation is False


def test_product_evaluator_checks_information_need() -> None:
    case = load_product_cases(case_id="ADDITIONAL_SOURCE_01")[0]
    output = AnalysisResponse(
        analysis_run_id=case.input.analysis_run_id,
        project_id=case.input.project_id,
        summary="추가 자료가 필요합니다.",
        candidates=[],
        questions=[],
        information_need="ADDITIONAL_SOURCE",
        information_need_reason="행동과 결정이 드러나는 기록이 필요합니다.",
    )

    result = evaluate_product_output(case, output)

    assert result.passed is True
    assert result.information_need_match is True


def test_product_evaluator_detects_missing_conflict() -> None:
    case = load_product_cases(case_id="CONFLICT_01")[0]
    experience_id = case.input.existing_experiences[0].experience_id
    output = AnalysisResponse(
        analysis_run_id=case.input.analysis_run_id,
        project_id=case.input.project_id,
        summary="기존 경험 보강",
        candidates=[
            ExperienceCandidate(
                candidate_id=uuid4(),
                result_type="EXISTING_UPDATE",
                target_experience_id=experience_id,
                title="인터뷰 경험",
                summary="새 Source를 반영합니다.",
                claims=[],
            )
        ],
    )

    result = evaluate_product_output(case, output)

    assert result.passed is False
    assert result.conflict_match is False
    assert "conflict expected=True actual=False" in result.failures


def test_product_evaluator_checks_claim_keywords_and_evidence_ids() -> None:
    case = load_product_cases(case_id="NEW_01")[0]
    case = case.model_copy(update={
        "expected": case.expected.model_copy(update={
            "expected_claim_keywords": ["동기화"],
            "forbidden_claim_keywords": ["인터뷰"],
            "required_evidence_chunk_ids": [
                "30000000-0000-0000-0000-000000000001"
            ],
        })
    })

    result = evaluate_product_output(case, matching_new_experience(case))

    assert result.passed is False
    assert result.expected_claims_match is False
    assert result.required_evidence_match is False


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


def _passing_run(category: str, *, latency_ms: int = 10, retry_count: int = 0):
    evaluation = AutomaticEvaluation(
        result_type_match=True,
        target_experience_match=True,
        experience_count_match=True,
        question_requirement_match=True,
        question_intent_match=True,
        information_need_match=True,
        conflict_match=True,
        critical_policy_violation=False,
        forbidden_output=False,
        passed=True,
    )
    return ProductEvalRun(
        case_id=f"{category}_01",
        category=category,
        run_number=1,
        provider="scripted",
        model="test",
        success=True,
        automatic_evaluation=evaluation,
        usage=LLMCallMetrics(
            provider="scripted",
            model="test",
            latency_ms=latency_ms,
            retry_count=retry_count,
        ),
        cost=CostEstimate(),
    )


def test_acceptance_summary_applies_automated_gates() -> None:
    summary = build_acceptance_summary([
        _passing_run("NEW_EXPERIENCE"),
        _passing_run("EXISTING_UPDATE"),
        _passing_run("MERGE"),
        _passing_run("SPLIT"),
    ])

    assert summary.accepted is False
    assert summary.failed_gate_count == 0
    assert summary.not_evaluated_gate_count == 2


def test_acceptance_summary_fails_latency_and_retry_gates() -> None:
    summary = build_acceptance_summary([
        _passing_run("NEW_EXPERIENCE", latency_ms=25_001, retry_count=2),
        _passing_run("MERGE"),
    ])
    statuses = {gate.name: gate.status for gate in summary.gates}

    assert summary.accepted is False
    assert statuses["p95_latency"] == "FAIL"
    assert statuses["retry_limit"] == "FAIL"
