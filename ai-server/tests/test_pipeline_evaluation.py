import pytest

from logfolio_ai.evaluation.pipeline_runner import (
    evaluate_pipeline_case,
    load_pipeline_cases,
    run_pipeline_eval,
)


def test_pipeline_dataset_contains_end_to_end_policy_cases() -> None:
    name, cases = load_pipeline_cases()

    assert name == "pipeline_core_v1"
    assert [case.case_id for case in cases] == [
        "PIPELINE_VALID_01",
        "PIPELINE_INVALID_EVIDENCE_01",
        "PIPELINE_ATTRIBUTION_01",
        "PIPELINE_EMPTY_RETRIEVAL_01",
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("case_index", [0, 1, 2, 3])
async def test_pipeline_cases_pass(case_index: int) -> None:
    _, cases = load_pipeline_cases()

    result = await evaluate_pipeline_case(cases[case_index])

    assert result.passed is True, result.failures


@pytest.mark.asyncio
async def test_pipeline_report_aggregates_case_results() -> None:
    name, cases = load_pipeline_cases()

    report = await run_pipeline_eval(cases, name)

    assert report.total == 4
    assert report.passed == 4
    assert report.failed == 0
    assert report.pass_rate == 1
