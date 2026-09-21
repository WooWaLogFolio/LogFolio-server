from logfolio_ai.evaluation import evaluate_cases, load_cases


def test_policy_evaluation_dataset_passes() -> None:
    cases = load_cases()

    report = evaluate_cases(cases)

    assert report.total >= 5
    assert report.failed == 0
    assert report.passed == report.total
    assert report.pass_rate == 1.0
