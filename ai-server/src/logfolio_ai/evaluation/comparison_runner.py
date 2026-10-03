import argparse
import csv
import json
import math
from enum import Enum
from pathlib import Path
from typing import List, Optional

from pydantic import Field

from logfolio_ai.evaluation.product_models import (
    AcceptanceGateStatus,
    ProductEvalReport,
)
from logfolio_ai.models.base import ContractModel


class ComparisonStatus(str, Enum):
    PASS = "PASS"
    READY_FOR_HUMAN_REVIEW = "READY_FOR_HUMAN_REVIEW"
    FAIL = "FAIL"


class ModelComparisonRow(ContractModel):
    provider: str
    model: str
    dataset: str
    status: ComparisonStatus
    pass_rate: float = Field(ge=0, le=1)
    p50_latency_ms: Optional[float] = Field(default=None, ge=0)
    p95_latency_ms: Optional[float] = Field(default=None, ge=0)
    timeout_rate: float = Field(ge=0, le=1)
    retry_rate: float = Field(ge=0, le=1)
    schema_failure_rate: float = Field(ge=0, le=1)
    critical_policy_error_count: int = Field(ge=0)
    total_estimated_cost_krw: Optional[float] = Field(default=None, ge=0)
    average_estimated_cost_krw: Optional[float] = Field(default=None, ge=0)
    failed_gates: List[str] = Field(default_factory=list)
    pending_gates: List[str] = Field(default_factory=list)


class ModelComparisonReport(ContractModel):
    reports_compared: int = Field(ge=0)
    rows: List[ModelComparisonRow]


def _percentile(values: List[int], percentile: float) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return float(ordered[index])


def summarize_report(report: ProductEvalReport) -> ModelComparisonRow:
    total = report.total_runs
    latencies = [run.usage.latency_ms for run in report.runs]
    timeout_count = sum(
        run.error_type is not None and "timeout" in run.error_type.lower()
        for run in report.runs
    )
    retry_count = sum(run.usage.retry_count > 0 for run in report.runs)
    schema_failure_count = sum(
        run.error_type in {"ValidationError", "JSONDecodeError"}
        for run in report.runs
    )
    critical_count = sum(
        bool(
            run.automatic_evaluation
            and run.automatic_evaluation.critical_policy_violation
        )
        for run in report.runs
    )
    failed_gates = [
        gate.name
        for gate in report.acceptance.gates
        if gate.status == AcceptanceGateStatus.FAIL
    ]
    pending_gates = [
        gate.name
        for gate in report.acceptance.gates
        if gate.status == AcceptanceGateStatus.NOT_EVALUATED
    ]
    if failed_gates:
        status = ComparisonStatus.FAIL
    elif pending_gates:
        status = ComparisonStatus.READY_FOR_HUMAN_REVIEW
    else:
        status = ComparisonStatus.PASS
    cost = report.total_estimated_cost_krw
    return ModelComparisonRow(
        provider=report.provider,
        model=report.model,
        dataset=report.dataset,
        status=status,
        pass_rate=report.pass_rate,
        p50_latency_ms=_percentile(latencies, 0.50),
        p95_latency_ms=_percentile(latencies, 0.95),
        timeout_rate=timeout_count / total if total else 0,
        retry_rate=retry_count / total if total else 0,
        schema_failure_rate=schema_failure_count / total if total else 0,
        critical_policy_error_count=critical_count,
        total_estimated_cost_krw=cost,
        average_estimated_cost_krw=(cost / total if cost is not None and total else None),
        failed_gates=failed_gates,
        pending_gates=pending_gates,
    )


def compare_reports(reports: List[ProductEvalReport]) -> ModelComparisonReport:
    rows = [summarize_report(report) for report in reports]
    status_order = {
        ComparisonStatus.PASS: 0,
        ComparisonStatus.READY_FOR_HUMAN_REVIEW: 1,
        ComparisonStatus.FAIL: 2,
    }
    rows.sort(
        key=lambda row: (
            status_order[row.status],
            -row.pass_rate,
            row.average_estimated_cost_krw
            if row.average_estimated_cost_krw is not None
            else float("inf"),
            row.p95_latency_ms if row.p95_latency_ms is not None else float("inf"),
        )
    )
    return ModelComparisonReport(reports_compared=len(rows), rows=rows)


def load_reports(paths: List[Path]) -> List[ProductEvalReport]:
    return [
        ProductEvalReport.model_validate_json(path.read_text(encoding="utf-8"))
        for path in paths
    ]


def export_csv(report: ModelComparisonReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(ModelComparisonRow.model_fields.keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in report.rows:
            payload = row.model_dump(mode="json")
            payload["failed_gates"] = ",".join(payload["failed_gates"])
            payload["pending_gates"] = ",".join(payload["pending_gates"])
            writer.writerow(payload)


def export_markdown(report: ModelComparisonReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# AI Model Comparison",
        "",
        "| Provider | Model | Status | Pass Rate | P50 | P95 | Avg Cost (KRW) | Pending |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in report.rows:
        average_cost = (
            f"{row.average_estimated_cost_krw:.2f}"
            if row.average_estimated_cost_krw is not None
            else "N/A"
        )
        lines.append(
            f"| {row.provider} | {row.model} | {row.status.value} | "
            f"{row.pass_rate:.1%} | {row.p50_latency_ms or 0:.0f}ms | "
            f"{row.p95_latency_ms or 0:.0f}ms | {average_cost} | "
            f"{', '.join(row.pending_gates) or '-'} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare LogFolio model eval reports")
    parser.add_argument("reports", type=Path, nargs="+")
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-csv", type=Path)
    parser.add_argument("--output-markdown", type=Path)
    args = parser.parse_args()
    report = compare_reports(load_reports(args.reports))
    rendered = report.model_dump_json(indent=2, by_alias=True)
    print(rendered)
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(rendered + "\n", encoding="utf-8")
    if args.output_csv:
        export_csv(report, args.output_csv)
    if args.output_markdown:
        export_markdown(report, args.output_markdown)


if __name__ == "__main__":
    main()
