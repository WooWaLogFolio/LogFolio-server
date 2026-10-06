import argparse
import csv
import json
from enum import Enum
from pathlib import Path
from typing import List, Optional

from pydantic import Field

from logfolio_ai.evaluation.product_models import ProductEvalReport
from logfolio_ai.models.base import ContractModel


class HumanScores(ContractModel):
    accuracy: Optional[int] = Field(default=None, ge=1, le=5)
    specificity: Optional[int] = Field(default=None, ge=1, le=5)
    core_relevance: Optional[int] = Field(default=None, ge=1, le=5)
    individuality: Optional[int] = Field(default=None, ge=1, le=5)
    structure: Optional[int] = Field(default=None, ge=1, le=5)
    non_duplication: Optional[int] = Field(default=None, ge=1, le=5)
    reusability: Optional[int] = Field(default=None, ge=1, le=5)
    no_exaggeration: Optional[int] = Field(default=None, ge=1, le=5)

    def values(self) -> List[int]:
        return [
            value
            for value in self.model_dump().values()
            if value is not None
        ]

    def complete(self) -> bool:
        return len(self.values()) == len(type(self).model_fields)


class HumanEvaluationEntry(ContractModel):
    case_id: str = Field(min_length=1)
    run_number: int = Field(ge=1)
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    reviewer: Optional[str] = Field(default=None, max_length=100)
    scores: HumanScores = Field(default_factory=HumanScores)
    critical_error: Optional[bool] = None
    notes: Optional[str] = Field(default=None, max_length=2000)


class HumanEvaluationDataset(ContractModel):
    version: str = Field(min_length=1)
    evaluations: List[HumanEvaluationEntry]


class HumanEvaluationStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    INCOMPLETE = "INCOMPLETE"


class HumanEvaluationResult(ContractModel):
    case_id: str
    run_number: int
    provider: str
    model: str
    status: HumanEvaluationStatus
    average_score: Optional[float] = Field(default=None, ge=1, le=5)
    failures: List[str] = Field(default_factory=list)


class HumanEvaluationReport(ContractModel):
    version: str
    total: int = Field(ge=0)
    completed: int = Field(ge=0)
    passed: int = Field(ge=0)
    failed: int = Field(ge=0)
    incomplete: int = Field(ge=0)
    overall_average_score: Optional[float] = Field(default=None, ge=1, le=5)
    accepted: bool
    results: List[HumanEvaluationResult]


def evaluate_entry(entry: HumanEvaluationEntry) -> HumanEvaluationResult:
    if not entry.scores.complete() or entry.critical_error is None:
        return HumanEvaluationResult(
            case_id=entry.case_id,
            run_number=entry.run_number,
            provider=entry.provider,
            model=entry.model,
            status=HumanEvaluationStatus.INCOMPLETE,
            failures=["All scores and criticalError are required."],
        )

    values = entry.scores.values()
    average = sum(values) / len(values)
    failures: List[str] = []
    if entry.critical_error:
        failures.append("criticalError=true")
    if average < 4.0:
        failures.append(f"averageScore={average:.2f} below 4.00")
    if entry.scores.accuracy is not None and entry.scores.accuracy < 3:
        failures.append(f"accuracy={entry.scores.accuracy} below 3")
    if entry.scores.individuality is not None and entry.scores.individuality < 3:
        failures.append(f"individuality={entry.scores.individuality} below 3")
    return HumanEvaluationResult(
        case_id=entry.case_id,
        run_number=entry.run_number,
        provider=entry.provider,
        model=entry.model,
        status=(HumanEvaluationStatus.FAIL if failures else HumanEvaluationStatus.PASS),
        average_score=average,
        failures=failures,
    )


def evaluate_dataset(dataset: HumanEvaluationDataset) -> HumanEvaluationReport:
    results = [evaluate_entry(entry) for entry in dataset.evaluations]
    complete_scores = [
        result.average_score
        for result in results
        if result.average_score is not None
    ]
    passed = sum(result.status == HumanEvaluationStatus.PASS for result in results)
    failed = sum(result.status == HumanEvaluationStatus.FAIL for result in results)
    incomplete = sum(
        result.status == HumanEvaluationStatus.INCOMPLETE for result in results
    )
    return HumanEvaluationReport(
        version=dataset.version,
        total=len(results),
        completed=len(results) - incomplete,
        passed=passed,
        failed=failed,
        incomplete=incomplete,
        overall_average_score=(
            sum(complete_scores) / len(complete_scores) if complete_scores else None
        ),
        accepted=bool(results) and failed == 0 and incomplete == 0,
        results=results,
    )


def create_template(report: ProductEvalReport, version: str) -> HumanEvaluationDataset:
    return HumanEvaluationDataset(
        version=version,
        evaluations=[
            HumanEvaluationEntry(
                case_id=run.case_id,
                run_number=run.run_number,
                provider=run.provider,
                model=run.model,
            )
            for run in report.runs
            if run.success and run.output is not None
        ],
    )


def export_csv(report: HumanEvaluationReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "caseId", "runNumber", "provider", "model", "status",
        "averageScore", "failures",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for result in report.results:
            writer.writerow({
                "caseId": result.case_id,
                "runNumber": result.run_number,
                "provider": result.provider,
                "model": result.model,
                "status": result.status.value,
                "averageScore": result.average_score,
                "failures": "; ".join(result.failures),
            })


def main() -> None:
    parser = argparse.ArgumentParser(description="Run LogFolio Human Eval scoring")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", type=Path)
    source.add_argument("--product-report", type=Path)
    parser.add_argument("--version", default="human_eval_v1")
    parser.add_argument("--template-output", type=Path)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-csv", type=Path)
    args = parser.parse_args()

    if args.product_report:
        if args.template_output is None:
            parser.error("--product-report requires --template-output")
        product_report = ProductEvalReport.model_validate_json(
            args.product_report.read_text(encoding="utf-8")
        )
        template = create_template(product_report, args.version)
        args.template_output.parent.mkdir(parents=True, exist_ok=True)
        args.template_output.write_text(
            template.model_dump_json(indent=2, by_alias=True) + "\n",
            encoding="utf-8",
        )
        print(template.model_dump_json(indent=2, by_alias=True))
        return

    dataset = HumanEvaluationDataset.model_validate_json(
        args.input.read_text(encoding="utf-8")
    )
    report = evaluate_dataset(dataset)
    rendered = report.model_dump_json(indent=2, by_alias=True)
    print(rendered)
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(rendered + "\n", encoding="utf-8")
    if args.output_csv:
        export_csv(report, args.output_csv)
    raise SystemExit(0 if report.accepted else 1)


if __name__ == "__main__":
    main()
