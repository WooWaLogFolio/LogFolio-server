import pytest

from logfolio_ai.evaluation.project_mismatch_runner import (
    load_project_mismatch_cases,
    run_project_mismatch_eval,
)


def test_project_mismatch_dataset_covers_confirmation_flow() -> None:
    dataset_name, cases = load_project_mismatch_cases()

    assert dataset_name == "project_mismatch_v1"
    assert {case.scenario for case in cases} == {
        "SUSPECTED_SOURCE",
        "CONFIRMED_SOURCE",
        "RELATED_SOURCE",
    }


@pytest.mark.asyncio
async def test_project_mismatch_report_passes_all_cases() -> None:
    dataset_name, cases = load_project_mismatch_cases()

    report = await run_project_mismatch_eval(cases, dataset_name)

    assert report.total == 3
    assert report.passed == 3
    assert report.failed == 0
    assert report.pass_rate == 1.0
    assert all(result.source_preserved for result in report.results)
