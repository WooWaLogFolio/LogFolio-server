from pathlib import Path

from logfolio_ai.evaluation.comparison_runner import (
    ComparisonStatus,
    compare_reports,
    export_csv,
    export_markdown,
)
from logfolio_ai.evaluation.product_models import (
    AcceptanceGate,
    AcceptanceGateStatus,
    AcceptanceSummary,
    AutomaticEvaluation,
    CostEstimate,
    ProductEvalReport,
    ProductEvalRun,
)
from logfolio_ai.llm import LLMCallMetrics


def report(model: str, *, passed: bool, cost: float) -> ProductEvalReport:
    evaluation = AutomaticEvaluation(
        result_type_match=passed,
        target_experience_match=True,
        experience_count_match=True,
        question_requirement_match=True,
        question_intent_match=True,
        information_need_match=True,
        conflict_match=True,
        critical_policy_violation=False,
        forbidden_output=False,
        passed=passed,
    )
    run = ProductEvalRun(
        case_id="NEW_01", category="NEW_EXPERIENCE", run_number=1,
        provider="fixture", model=model, success=True,
        automatic_evaluation=evaluation,
        usage=LLMCallMetrics(
            provider="fixture", model=model, latency_ms=100,
        ),
        cost=CostEstimate(estimated_cost_krw=cost),
    )
    gates = [
        AcceptanceGate(
            name="automatic_quality",
            status=AcceptanceGateStatus.PASS if passed else AcceptanceGateStatus.FAIL,
        ),
        AcceptanceGate(
            name="human_quality_score",
            status=AcceptanceGateStatus.NOT_EVALUATED,
        ),
    ]
    return ProductEvalReport(
        dataset="test", provider="fixture", model=model,
        total_runs=1, passed_runs=int(passed), failed_runs=int(not passed),
        pass_rate=float(passed), total_estimated_cost_krw=cost,
        acceptance=AcceptanceSummary(
            accepted=False, evaluated_gate_count=1,
            passed_gate_count=int(passed), failed_gate_count=int(not passed),
            not_evaluated_gate_count=1, gates=gates,
        ),
        runs=[run],
    )


def test_comparison_ranks_eligible_model_before_failed_model() -> None:
    result = compare_reports([
        report("failed", passed=False, cost=1),
        report("ready", passed=True, cost=10),
    ])

    assert [row.model for row in result.rows] == ["ready", "failed"]
    assert result.rows[0].status == ComparisonStatus.READY_FOR_HUMAN_REVIEW
    assert result.rows[1].status == ComparisonStatus.FAIL


def test_comparison_exports_csv_and_markdown(tmp_path: Path) -> None:
    result = compare_reports([report("ready", passed=True, cost=10)])
    csv_path = tmp_path / "comparison.csv"
    markdown_path = tmp_path / "comparison.md"

    export_csv(result, csv_path)
    export_markdown(result, markdown_path)

    assert "READY_FOR_HUMAN_REVIEW" in csv_path.read_text(encoding="utf-8")
    assert "# AI Model Comparison" in markdown_path.read_text(encoding="utf-8")
