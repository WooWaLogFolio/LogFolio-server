from uuid import uuid4

import pytest
from pydantic import ValidationError

from logfolio_ai.evaluation.cost_guardrail_runner import (
    AnalysisCostObservation,
    CostGuardrailInput,
    evaluate_cost_guardrails,
)


def observation(**updates) -> AnalysisCostObservation:
    payload = {
        "analysis_run_id": uuid4(),
        "user_id": uuid4(),
        "estimated_cost_usd": 0.1,
        "estimated_cost_krw": 20,
        "created_experience_count": 1,
        "accepted_experience_count": 1,
    }
    payload.update(updates)
    return AnalysisCostObservation(**payload)


def test_cost_guardrails_pass_within_all_hard_limits() -> None:
    heavy_user_id = uuid4()
    report = evaluate_cost_guardrails(
        CostGuardrailInput(
            period_month="2026-10",
            observations=[
                observation(
                    user_id=heavy_user_id,
                    estimated_cost_usd=2.5,
                    estimated_cost_krw=400,
                    created_experience_count=20,
                    accepted_experience_count=20,
                ),
                observation(),
            ],
        )
    )

    assert report.accepted is True
    assert report.cost_per_accepted_experience_krw == 20
    heavy_user = next(user for user in report.users if user.user_id == heavy_user_id)
    assert heavy_user.heavy_user is True
    assert heavy_user.heavy_user_cost_passed is True


def test_cost_guardrails_fail_when_cost_per_accepted_exceeds_50_krw() -> None:
    report = evaluate_cost_guardrails(
        CostGuardrailInput(
            period_month="2026-10",
            observations=[observation(estimated_cost_krw=51)],
        )
    )

    assert report.accepted is False
    gate = next(
        gate for gate in report.gates if gate.name == "cost_per_accepted_experience"
    )
    assert gate.status == "FAIL"


def test_cost_guardrails_fail_heavy_user_over_three_usd() -> None:
    report = evaluate_cost_guardrails(
        CostGuardrailInput(
            period_month="2026-10",
            observations=[
                observation(
                    estimated_cost_usd=3.01,
                    created_experience_count=20,
                    accepted_experience_count=20,
                )
            ],
        )
    )

    assert report.accepted is False
    assert report.users[0].heavy_user_cost_passed is False


def test_duplicate_analysis_run_is_rejected_to_prevent_double_counting() -> None:
    run_id = uuid4()

    with pytest.raises(ValidationError, match="analysisRunId must be unique"):
        CostGuardrailInput(
            period_month="2026-10",
            observations=[
                observation(analysis_run_id=run_id),
                observation(analysis_run_id=run_id),
            ],
        )
