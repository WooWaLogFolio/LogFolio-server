import argparse
import asyncio
import csv
import json
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from logfolio_ai.core.config import Settings
from logfolio_ai.evaluation.product_models import (
    CRITICAL_POLICY_VIOLATIONS,
    AutomaticEvaluation,
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
        runs=runs,
    )


def export_csv(report: ProductEvalReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "caseId", "runNumber", "provider", "model", "success", "passed",
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
