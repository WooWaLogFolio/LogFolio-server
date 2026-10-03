from pathlib import Path

from logfolio_ai.evaluation.human_runner import (
    HumanEvaluationDataset,
    HumanEvaluationEntry,
    HumanEvaluationStatus,
    HumanScores,
    evaluate_dataset,
    evaluate_entry,
    export_csv,
)


def entry(**updates) -> HumanEvaluationEntry:
    payload = {
        "case_id": "NEW_01",
        "run_number": 1,
        "provider": "fixture",
        "model": "test",
        "scores": HumanScores(
            accuracy=4, specificity=4, core_relevance=4, individuality=4,
            structure=4, non_duplication=4, reusability=4,
            no_exaggeration=4,
        ),
        "critical_error": False,
    }
    payload.update(updates)
    return HumanEvaluationEntry(**payload)


def test_human_eval_passes_complete_quality_scores() -> None:
    result = evaluate_entry(entry())

    assert result.status == HumanEvaluationStatus.PASS
    assert result.average_score == 4


def test_human_eval_fails_hard_accuracy_floor() -> None:
    scores = entry().scores.model_copy(update={"accuracy": 2})
    result = evaluate_entry(entry(scores=scores))

    assert result.status == HumanEvaluationStatus.FAIL
    assert "accuracy=2 below 3" in result.failures


def test_human_eval_fails_critical_error_regardless_of_average() -> None:
    scores = HumanScores(**{field: 5 for field in HumanScores.model_fields})
    result = evaluate_entry(entry(scores=scores, critical_error=True))

    assert result.status == HumanEvaluationStatus.FAIL
    assert "criticalError=true" in result.failures


def test_human_eval_marks_unscored_template_incomplete() -> None:
    result = evaluate_entry(entry(scores=HumanScores(), critical_error=None))

    assert result.status == HumanEvaluationStatus.INCOMPLETE
    assert result.average_score is None


def test_human_eval_report_and_csv(tmp_path: Path) -> None:
    dataset = HumanEvaluationDataset(
        version="v1",
        evaluations=[entry(), entry(run_number=2, scores=HumanScores())],
    )
    report = evaluate_dataset(dataset)
    output = tmp_path / "human.csv"
    export_csv(report, output)

    assert report.total == 2
    assert report.passed == 1
    assert report.incomplete == 1
    assert report.accepted is False
    assert "INCOMPLETE" in output.read_text(encoding="utf-8")
