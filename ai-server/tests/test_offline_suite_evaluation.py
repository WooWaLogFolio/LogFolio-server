import pytest

from logfolio_ai.evaluation.offline_suite_runner import run_offline_suite


@pytest.mark.asyncio
async def test_offline_suite_passes_all_dependency_free_quality_gates() -> None:
    report = await run_offline_suite()

    assert report.accepted is True
    assert report.failed == 0
    assert report.passed == report.total
    assert {check.name for check in report.checks} == {
        "AI_POLICY",
        "FULL_PIPELINE",
        "FAILURE_RECOVERY",
        "SOURCE_LIFECYCLE",
        "PROJECT_MISMATCH",
    }
    assert all(check.error is None for check in report.checks)
    assert {check.name for check in report.deferred_checks} == {
        "LOCAL_E5_RETRIEVAL",
        "REAL_PROVIDER_PRODUCT_EVAL",
        "HUMAN_QUALITY_EVAL",
        "SPRING_INTEGRATION",
    }
