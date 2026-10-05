import pytest

from logfolio_ai.evaluation.resilience_runner import (
    load_resilience_cases,
    run_resilience_eval,
)


def test_resilience_dataset_covers_required_failure_policies() -> None:
    dataset_name, cases = load_resilience_cases()

    assert dataset_name == "resilience_core_v1"
    assert {case.scenario for case in cases} == {
        "INVALID_THEN_SUCCESS",
        "TIMEOUT",
        "NON_TRANSIENT_4XX",
        "INVALID_OUTPUT",
        "PARTIAL_SOURCE_INDEXING",
    }


@pytest.mark.asyncio
async def test_resilience_core_report_passes_all_cases() -> None:
    dataset_name, cases = load_resilience_cases()

    report = await run_resilience_eval(cases, dataset_name)

    assert report.total == 5
    assert report.passed == 5
    assert report.failed == 0
    assert report.pass_rate == 1.0
    assert all(result.passed for result in report.results)
