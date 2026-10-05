import pytest

from logfolio_ai.evaluation.source_lifecycle_runner import (
    load_source_lifecycle_cases,
    run_source_lifecycle_eval,
)


def test_source_lifecycle_dataset_covers_duplicate_and_delete_policies() -> None:
    dataset_name, cases = load_source_lifecycle_cases()

    assert dataset_name == "source_lifecycle_v1"
    assert {case.scenario for case in cases} == {
        "EXACT_DUPLICATE",
        "PROJECT_ISOLATION",
        "DELETE_EXCLUDES_RETRIEVAL",
        "DELETE_RELEASES_CONTENT_HASH",
    }


@pytest.mark.asyncio
async def test_source_lifecycle_report_passes_all_cases() -> None:
    dataset_name, cases = load_source_lifecycle_cases()

    report = await run_source_lifecycle_eval(cases, dataset_name)

    assert report.total == 4
    assert report.passed == 4
    assert report.failed == 0
    assert report.pass_rate == 1.0
    assert all(result.passed for result in report.results)
