import argparse
import json
from pathlib import Path
from typing import Iterable, List

from pydantic import TypeAdapter

from logfolio_ai.evaluation.models import (
    ClaimExpectation,
    EvaluationCase,
    EvaluationFailure,
    EvaluationReport,
)
from logfolio_ai.policy import AIPolicyValidator

DEFAULT_DATASET = (
    Path(__file__).resolve().parents[3] / "evals" / "datasets" / "policy_cases.json"
)


def load_cases(path: Path = DEFAULT_DATASET) -> List[EvaluationCase]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return TypeAdapter(List[EvaluationCase]).validate_python(payload)


def _check_claim(case: EvaluationCase, expected: ClaimExpectation, output) -> List[str]:
    messages: List[str] = []
    try:
        claim = output.candidates[expected.candidate_index].claims[expected.claim_index]
    except IndexError:
        return [
            f"claim not found at candidate={expected.candidate_index}, claim={expected.claim_index}"
        ]

    fields = (
        "subject_type",
        "provenance_type",
        "verification_status",
        "evidence_type",
        "requires_user_confirmation",
    )
    for field in fields:
        expected_value = getattr(expected, field)
        if expected_value is not None and getattr(claim, field) != expected_value:
            messages.append(
                f"{field}: expected {expected_value}, got {getattr(claim, field)}"
            )
    missing = [
        violation
        for violation in expected.violations_contain
        if violation not in claim.policy_violations
    ]
    if missing:
        messages.append(f"missing policy violations: {missing}")
    return messages


def evaluate_cases(cases: Iterable[EvaluationCase]) -> EvaluationReport:
    validator = AIPolicyValidator()
    failures: List[EvaluationFailure] = []
    total = 0

    for case in cases:
        total += 1
        output = validator.validate(
            case.raw_response,
            user_answers=case.user_answers,
        )
        messages: List[str] = []
        for expected_claim in case.expected.claims:
            messages.extend(_check_claim(case, expected_claim, output))

        if case.expected.question_targets is not None:
            actual_targets = [question.target_section for question in output.questions]
            if actual_targets != case.expected.question_targets:
                messages.append(
                    f"question targets: expected {case.expected.question_targets}, got {actual_targets}"
                )

        if (
            case.expected.information_need is not None
            and output.information_need != case.expected.information_need
        ):
            messages.append(
                "information need: expected "
                f"{case.expected.information_need}, got {output.information_need}"
            )

        if (
            case.expected.result_types is not None
            and output.result_types != case.expected.result_types
        ):
            messages.append(
                f"result types: expected {case.expected.result_types}, got {output.result_types}"
            )

        failures.extend(
            EvaluationFailure(case_id=case.case_id, message=message)
            for message in messages
        )

    failed_case_count = len({failure.case_id for failure in failures})
    passed = total - failed_case_count
    return EvaluationReport(
        total=total,
        passed=passed,
        failed=failed_case_count,
        pass_rate=passed / total if total else 0,
        failures=failures,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run LogFolio AI policy evaluations")
    parser.add_argument("dataset", nargs="?", type=Path, default=DEFAULT_DATASET)
    args = parser.parse_args()
    report = evaluate_cases(load_cases(args.dataset))
    print(report.model_dump_json(indent=2))
    raise SystemExit(1 if report.failed else 0)


if __name__ == "__main__":
    main()
