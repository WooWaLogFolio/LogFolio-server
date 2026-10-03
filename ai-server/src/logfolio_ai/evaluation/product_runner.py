import argparse
import asyncio
import csv
import json
import math
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from logfolio_ai.core.config import Settings
from logfolio_ai.evaluation.product_models import (
    CRITICAL_POLICY_VIOLATIONS,
    AutomaticEvaluation,
    AcceptanceGate,
    AcceptanceGateStatus,
    AcceptanceSummary,
    CostEstimate,
    ProductEvalCase,
    ProductEvalReport,
    ProductEvalRun,
)
from logfolio_ai.llm import LLMCallMetrics, LLMProvider
from logfolio_ai.llm.factory import build_llm_provider
from logfolio_ai.models import AnalysisResponse
from logfolio_ai.policy import AIPolicyValidator


EVALS_ROOT = Path(__file__).resolve().parents[3] / "evals"
DEFAULT_DATASET = EVALS_ROOT / "datasets" / "product_core_v1.json"


def _rate(values: List[bool]) -> Optional[float]:
    return sum(values) / len(values) if values else None


def _percentile(values: List[int], percentile: float) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return float(ordered[index])


def build_acceptance_summary(runs: List[ProductEvalRun]) -> AcceptanceSummary:
    """Apply the v1 automated acceptance gates without inventing unavailable data."""
    successful = [
        run for run in runs
        if run.success and run.automatic_evaluation is not None
    ]

    def accuracy_gate(name: str, categories: set, threshold: float) -> AcceptanceGate:
        selected = [
            run.automatic_evaluation.passed
            for run in successful
            if run.category.upper() in categories
        ]
        actual = _rate(selected)
        if actual is None:
            return AcceptanceGate(
                name=name,
                status=AcceptanceGateStatus.NOT_EVALUATED,
                threshold=threshold,
                unit="ratio",
                reason="No matching evaluation cases were executed.",
            )
        return AcceptanceGate(
            name=name,
            status=(
                AcceptanceGateStatus.PASS
                if actual >= threshold
                else AcceptanceGateStatus.FAIL
            ),
            actual=actual,
            threshold=threshold,
            unit="ratio",
        )

    critical_count = sum(
        bool(run.automatic_evaluation.critical_policy_violation)
        for run in successful
    )
    invalid_schema_count = sum(
        run.error_type in {"ValidationError", "JSONDecodeError"} for run in runs
    )
    p95_latency = _percentile([run.usage.latency_ms for run in runs], 0.95)
    retry_excess_count = sum(run.usage.retry_count > 1 for run in runs)
    question_rate = _rate([
        run.automatic_evaluation.question_requirement_match
        for run in successful
    ])

    gates = [
        accuracy_gate(
            "existing_new_accuracy",
            {"NEW_EXPERIENCE", "EXISTING_UPDATE"},
            0.90,
        ),
        accuracy_gate("merge_split_accuracy", {"MERGE", "SPLIT"}, 0.90),
        AcceptanceGate(
            name="execution_success",
            status=(
                AcceptanceGateStatus.PASS
                if runs and all(run.success for run in runs)
                else AcceptanceGateStatus.FAIL
            ),
            actual=_rate([run.success for run in runs]) or 0,
            threshold=1,
            unit="ratio",
            reason=("No runs were executed." if not runs else None),
        ),
        AcceptanceGate(
            name="question_need_accuracy",
            status=(
                AcceptanceGateStatus.NOT_EVALUATED if question_rate is None
                else AcceptanceGateStatus.PASS if question_rate >= 0.90
                else AcceptanceGateStatus.FAIL
            ),
            actual=question_rate,
            threshold=0.90,
            unit="ratio",
            reason=("No successful evaluation runs." if question_rate is None else None),
        ),
        AcceptanceGate(
            name="critical_policy_errors",
            status=(AcceptanceGateStatus.PASS if critical_count == 0 else AcceptanceGateStatus.FAIL),
            actual=float(critical_count),
            threshold=0,
            unit="count",
        ),
        AcceptanceGate(
            name="invalid_schema_errors",
            status=(AcceptanceGateStatus.PASS if invalid_schema_count == 0 else AcceptanceGateStatus.FAIL),
            actual=float(invalid_schema_count),
            threshold=0,
            unit="count",
        ),
        AcceptanceGate(
            name="p95_latency",
            status=(
                AcceptanceGateStatus.NOT_EVALUATED if p95_latency is None
                else AcceptanceGateStatus.PASS if p95_latency <= 25_000
                else AcceptanceGateStatus.FAIL
            ),
            actual=p95_latency,
            threshold=25_000,
            unit="ms",
            reason=("No runs were executed." if p95_latency is None else None),
        ),
        AcceptanceGate(
            name="retry_limit",
            status=(AcceptanceGateStatus.PASS if retry_excess_count == 0 else AcceptanceGateStatus.FAIL),
            actual=float(retry_excess_count),
            threshold=0,
            unit="runs_over_one_retry",
        ),
        AcceptanceGate(
            name="cost_per_accepted_experience",
            status=AcceptanceGateStatus.NOT_EVALUATED,
            threshold=50,
            unit="KRW",
            reason="Requires Spring review acceptance data.",
        ),
        AcceptanceGate(
            name="human_quality_score",
            status=AcceptanceGateStatus.NOT_EVALUATED,
            threshold=4,
            unit="score_out_of_5",
            reason="Requires human rubric scores.",
        ),
    ]
    evaluated = [gate for gate in gates if gate.status != AcceptanceGateStatus.NOT_EVALUATED]
    passed = sum(gate.status == AcceptanceGateStatus.PASS for gate in evaluated)
    failed = sum(gate.status == AcceptanceGateStatus.FAIL for gate in evaluated)
    return AcceptanceSummary(
        accepted=bool(evaluated) and failed == 0 and len(evaluated) == len(gates),
        evaluated_gate_count=len(evaluated),
        passed_gate_count=passed,
        failed_gate_count=failed,
        not_evaluated_gate_count=len(gates) - len(evaluated),
        gates=gates,
    )


def load_product_cases(
    dataset_path: Path = DEFAULT_DATASET,
    case_id: Optional[str] = None,
) -> List[ProductEvalCase]:
    payload = json.loads(dataset_path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        raw_cases = payload
    else:
        raw_cases = [
            json.loads((dataset_path.parent.parent / item).read_text(encoding="utf-8"))
            for item in payload["caseFiles"]
        ]
    cases = [ProductEvalCase.model_validate(item) for item in raw_cases]
    if case_id is not None:
        cases = [case for case in cases if case.case_id == case_id]
        if not cases:
            raise ValueError(f"unknown case: {case_id}")
    return cases


def evaluate_product_output(
    case: ProductEvalCase,
    output: AnalysisResponse,
) -> AutomaticEvaluation:
    expected = case.expected
    failures: List[str] = []
    result_type_match = expected.result_type in output.result_types
    if not result_type_match:
        failures.append(
            f"resultType expected={expected.result_type.value} actual="
            f"{[item.value for item in output.result_types]}"
        )

    actual_target_ids = {
        str(candidate.target_experience_id)
        for candidate in output.candidates
        if candidate.target_experience_id is not None
    }
    target_experience_match = (
        expected.target_experience_id is None
        or expected.target_experience_id in actual_target_ids
    )
    if not target_experience_match:
        failures.append(
            f"targetExperienceId expected={expected.target_experience_id} "
            f"actual={sorted(actual_target_ids)}"
        )

    experience_count_match = len(output.candidates) == expected.expected_experience_count
    if not experience_count_match:
        failures.append(
            f"experienceCount expected={expected.expected_experience_count} "
            f"actual={len(output.candidates)}"
        )

    actual_requires_question = bool(output.questions)
    question_requirement_match = actual_requires_question == expected.requires_question
    if not question_requirement_match:
        failures.append(
            f"requiresQuestion expected={expected.requires_question} "
            f"actual={actual_requires_question}"
        )

    actual_intents = [question.target_section for question in output.questions]
    question_intent_match = all(
        intent in actual_intents for intent in expected.question_intents
    )
    if not question_intent_match:
        failures.append(
            f"questionIntents expected={expected.question_intents} actual={actual_intents}"
        )

    information_need_match = (
        expected.information_need is None
        or output.information_need == expected.information_need
    )
    if not information_need_match:
        failures.append(
            f"informationNeed expected={expected.information_need.value} "
            f"actual={output.information_need.value if output.information_need else None}"
        )

    actual_conflict = any(candidate.conflict for candidate in output.candidates)
    conflict_match = expected.conflict is None or actual_conflict == expected.conflict
    if not conflict_match:
        failures.append(
            f"conflict expected={expected.conflict} actual={actual_conflict}"
        )

    claim_text = " ".join(
        claim.content.lower()
        for candidate in output.candidates
        for claim in candidate.claims
    )
    missing_claim_keywords = [
        keyword
        for keyword in expected.expected_claim_keywords
        if keyword.lower() not in claim_text
    ]
    expected_claims_match = not missing_claim_keywords
    if not expected_claims_match:
        failures.append(f"missingClaimKeywords={missing_claim_keywords}")

    matched_forbidden_claims = [
        keyword
        for keyword in expected.forbidden_claim_keywords
        if keyword.lower() in claim_text
    ]
    forbidden_claims_absent = not matched_forbidden_claims
    if not forbidden_claims_absent:
        failures.append(f"forbiddenClaimKeywords={matched_forbidden_claims}")

    actual_evidence_chunk_ids = {
        str(evidence.chunk_id)
        for candidate in output.candidates
        for claim in candidate.claims
        for evidence in claim.evidences
    }
    missing_evidence_ids = [
        chunk_id
        for chunk_id in expected.required_evidence_chunk_ids
        if chunk_id not in actual_evidence_chunk_ids
    ]
    required_evidence_match = not missing_evidence_ids
    if not required_evidence_match:
        failures.append(f"missingEvidenceChunkIds={missing_evidence_ids}")

    violations = {
        violation
        for candidate in output.candidates
        for claim in candidate.claims
        for violation in claim.policy_violations
    }
    critical_policy_violation = bool(violations & CRITICAL_POLICY_VIOLATIONS)
    if critical_policy_violation:
        failures.append(
            "criticalPolicyViolation="
            f"{sorted(item.value for item in violations & CRITICAL_POLICY_VIOLATIONS)}"
        )

    serialized = output.model_dump_json(by_alias=True).lower()
    matched_forbidden = [
        phrase for phrase in expected.forbidden_phrases if phrase.lower() in serialized
    ]
    forbidden_output = bool(matched_forbidden)
    if forbidden_output:
        failures.append(f"forbiddenOutput={matched_forbidden}")

    return AutomaticEvaluation(
        result_type_match=result_type_match,
        target_experience_match=target_experience_match,
        experience_count_match=experience_count_match,
        question_requirement_match=question_requirement_match,
        question_intent_match=question_intent_match,
        information_need_match=information_need_match,
        conflict_match=conflict_match,
        expected_claims_match=expected_claims_match,
        forbidden_claims_absent=forbidden_claims_absent,
        required_evidence_match=required_evidence_match,
        critical_policy_violation=critical_policy_violation,
        forbidden_output=forbidden_output,
        passed=not failures,
        failures=failures,
    )


def estimate_cost(
    metrics: LLMCallMetrics,
    pricing: Optional[Dict[str, Any]],
) -> CostEstimate:
    if not pricing:
        return CostEstimate()
    model_prices = pricing.get("models", {}).get(f"{metrics.provider}/{metrics.model}")
    if model_prices is None:
        return CostEstimate(pricing_version=pricing.get("version"))
    token_values = (
        metrics.input_tokens,
        metrics.cached_input_tokens,
        metrics.output_tokens,
        metrics.reasoning_tokens,
    )
    if any(value is None for value in token_values):
        return CostEstimate(pricing_version=pricing.get("version"))
    usd = (
        metrics.input_tokens * model_prices.get("inputPerMillionUsd", 0)
        + metrics.cached_input_tokens * model_prices.get("cachedInputPerMillionUsd", 0)
        + metrics.output_tokens * model_prices.get("outputPerMillionUsd", 0)
        + metrics.reasoning_tokens * model_prices.get("reasoningPerMillionUsd", 0)
    ) / 1_000_000
    usd_to_krw = pricing.get("usdToKrw")
    return CostEstimate(
        estimated_cost_usd=usd,
        estimated_cost_krw=usd * usd_to_krw if usd_to_krw is not None else None,
        pricing_version=pricing.get("version"),
    )


async def run_product_eval(
    cases: Iterable[ProductEvalCase],
    provider: LLMProvider,
    *,
    provider_name: str,
    model: str,
    dataset_name: str,
    repeat: int = 1,
    pricing: Optional[Dict[str, Any]] = None,
) -> ProductEvalReport:
    validator = AIPolicyValidator()
    runs: List[ProductEvalRun] = []
    for case in cases:
        case_repeat = max(repeat, 3 if case.difficulty == "HARD" else 1)
        for run_number in range(1, case_repeat + 1):
            started = time.perf_counter()
            try:
                raw_output = await provider.analyze_grounded(case.input)
                output = validator.validate(
                    raw_output,
                    user_answers=case.input.answers,
                    corrections=case.input.corrections,
                )
                evaluation = evaluate_product_output(case, output)
                measured = getattr(provider, "last_call_metrics", None)
                metrics = measured or LLMCallMetrics(
                    provider=provider_name,
                    model=model,
                    latency_ms=max(0, round((time.perf_counter() - started) * 1000)),
                )
                runs.append(
                    ProductEvalRun(
                        case_id=case.case_id,
                        category=case.category,
                        run_number=run_number,
                        provider=provider_name,
                        model=model,
                        success=True,
                        output=output,
                        automatic_evaluation=evaluation,
                        usage=metrics,
                        cost=estimate_cost(metrics, pricing),
                    )
                )
            except Exception as exc:
                runs.append(
                    ProductEvalRun(
                        case_id=case.case_id,
                        category=case.category,
                        run_number=run_number,
                        provider=provider_name,
                        model=model,
                        success=False,
                        error_type=type(exc).__name__,
                        usage=LLMCallMetrics(
                            provider=provider_name,
                            model=model,
                            latency_ms=max(0, round((time.perf_counter() - started) * 1000)),
                        ),
                    )
                )

    passed = sum(
        run.success
        and run.automatic_evaluation is not None
        and run.automatic_evaluation.passed
        for run in runs
    )
    usd_values = [run.cost.estimated_cost_usd for run in runs if run.cost.estimated_cost_usd is not None]
    krw_values = [run.cost.estimated_cost_krw for run in runs if run.cost.estimated_cost_krw is not None]
    return ProductEvalReport(
        dataset=dataset_name,
        provider=provider_name,
        model=model,
        total_runs=len(runs),
        passed_runs=passed,
        failed_runs=len(runs) - passed,
        pass_rate=passed / len(runs) if runs else 0,
        total_estimated_cost_usd=sum(usd_values) if usd_values else None,
        total_estimated_cost_krw=sum(krw_values) if krw_values else None,
        acceptance=build_acceptance_summary(runs),
        runs=runs,
    )


def export_csv(report: ProductEvalReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "caseId", "category", "runNumber", "provider", "model", "success", "passed",
        "latencyMs", "retryCount", "inputTokens", "cachedInputTokens",
        "outputTokens", "reasoningTokens", "estimatedCostUsd",
        "estimatedCostKrw", "errorType",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for run in report.runs:
            writer.writerow({
                "caseId": run.case_id,
                "category": run.category,
                "runNumber": run.run_number,
                "provider": run.provider,
                "model": run.model,
                "success": run.success,
                "passed": bool(run.automatic_evaluation and run.automatic_evaluation.passed),
                "latencyMs": run.usage.latency_ms,
                "retryCount": run.usage.retry_count,
                "inputTokens": run.usage.input_tokens,
                "cachedInputTokens": run.usage.cached_input_tokens,
                "outputTokens": run.usage.output_tokens,
                "reasoningTokens": run.usage.reasoning_tokens,
                "estimatedCostUsd": run.cost.estimated_cost_usd,
                "estimatedCostKrw": run.cost.estimated_cost_krw,
                "errorType": run.error_type,
            })


def _load_optional_json(path: Optional[Path]) -> Optional[Dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8")) if path else None


def main() -> None:
    parser = argparse.ArgumentParser(description="Run LogFolio product model evaluations")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--case")
    parser.add_argument("--provider", choices=("fake", "gemini"), default="fake")
    parser.add_argument("--model")
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--pricing", type=Path)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-csv", type=Path)
    args = parser.parse_args()
    if args.repeat < 1:
        parser.error("--repeat must be at least 1")

    settings = Settings(llm_provider=args.provider)
    if args.model:
        settings = settings.model_copy(update={"gemini_model": args.model})
    provider = build_llm_provider(settings)
    model = args.model or (settings.gemini_model if args.provider == "gemini" else "fake")
    report = asyncio.run(run_product_eval(
        load_product_cases(args.dataset, args.case),
        provider,
        provider_name=args.provider,
        model=model,
        dataset_name=args.dataset.stem,
        repeat=args.repeat,
        pricing=_load_optional_json(args.pricing),
    ))
    rendered = report.model_dump_json(indent=2, by_alias=True)
    print(rendered)
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(rendered + "\n", encoding="utf-8")
    if args.output_csv:
        export_csv(report, args.output_csv)
    raise SystemExit(0 if report.failed_runs == 0 else 1)


if __name__ == "__main__":
    main()
