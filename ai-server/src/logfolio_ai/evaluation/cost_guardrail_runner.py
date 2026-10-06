import argparse
import json
from pathlib import Path
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import Field, model_validator

from logfolio_ai.evaluation.product_models import (
    AcceptanceGate,
    AcceptanceGateStatus,
)
from logfolio_ai.models.base import ContractModel


class AnalysisCostObservation(ContractModel):
    analysis_run_id: UUID
    user_id: UUID
    estimated_cost_usd: float = Field(ge=0)
    estimated_cost_krw: float = Field(ge=0)
    created_experience_count: int = Field(default=0, ge=0)
    updated_experience_count: int = Field(default=0, ge=0)
    accepted_experience_count: int = Field(default=0, ge=0)
    rejected_experience_count: int = Field(default=0, ge=0)


class CostGuardrailInput(ContractModel):
    period_month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    observations: List[AnalysisCostObservation]

    @model_validator(mode="after")
    def analysis_runs_must_be_unique(self) -> "CostGuardrailInput":
        run_ids = [item.analysis_run_id for item in self.observations]
        if len(run_ids) != len(set(run_ids)):
            raise ValueError("analysisRunId must be unique to prevent duplicate cost totals")
        return self


class UserMonthlyCost(ContractModel):
    user_id: UUID
    analysis_count: int = Field(ge=0)
    created_experience_count: int = Field(ge=0)
    updated_experience_count: int = Field(ge=0)
    accepted_experience_count: int = Field(ge=0)
    cost_usd: float = Field(ge=0)
    cost_krw: float = Field(ge=0)
    heavy_user: bool
    heavy_user_cost_passed: Optional[bool] = None


class CostGuardrailReport(ContractModel):
    period_month: str
    accepted: bool
    total_analysis_count: int = Field(ge=0)
    total_accepted_experience_count: int = Field(ge=0)
    total_cost_usd: float = Field(ge=0)
    total_cost_krw: float = Field(ge=0)
    cost_per_accepted_experience_krw: Optional[float] = Field(default=None, ge=0)
    users: List[UserMonthlyCost]
    gates: List[AcceptanceGate]


def _cost_per_accepted_gate(
    total_cost_krw: float,
    accepted_count: int,
) -> tuple[AcceptanceGate, Optional[float]]:
    if accepted_count == 0:
        if total_cost_krw == 0:
            return (
                AcceptanceGate(
                    name="cost_per_accepted_experience",
                    status=AcceptanceGateStatus.NOT_EVALUATED,
                    threshold=50,
                    unit="KRW",
                    reason="No AI cost or accepted Experience was recorded.",
                ),
                None,
            )
        return (
            AcceptanceGate(
                name="cost_per_accepted_experience",
                status=AcceptanceGateStatus.FAIL,
                threshold=50,
                unit="KRW",
                reason="AI cost exists but no Experience was accepted.",
            ),
            None,
        )
    actual = total_cost_krw / accepted_count
    return (
        AcceptanceGate(
            name="cost_per_accepted_experience",
            status=(
                AcceptanceGateStatus.PASS
                if actual <= 50
                else AcceptanceGateStatus.FAIL
            ),
            actual=actual,
            threshold=50,
            unit="KRW",
        ),
        actual,
    )


def evaluate_cost_guardrails(payload: CostGuardrailInput) -> CostGuardrailReport:
    grouped: Dict[UUID, List[AnalysisCostObservation]] = {}
    for observation in payload.observations:
        grouped.setdefault(observation.user_id, []).append(observation)

    users: List[UserMonthlyCost] = []
    for user_id, observations in sorted(grouped.items(), key=lambda item: str(item[0])):
        created = sum(item.created_experience_count for item in observations)
        updated = sum(item.updated_experience_count for item in observations)
        accepted = sum(item.accepted_experience_count for item in observations)
        cost_usd = sum(item.estimated_cost_usd for item in observations)
        cost_krw = sum(item.estimated_cost_krw for item in observations)
        heavy_user = created + updated >= 20
        users.append(
            UserMonthlyCost(
                user_id=user_id,
                analysis_count=len(observations),
                created_experience_count=created,
                updated_experience_count=updated,
                accepted_experience_count=accepted,
                cost_usd=cost_usd,
                cost_krw=cost_krw,
                heavy_user=heavy_user,
                heavy_user_cost_passed=(cost_usd <= 3 if heavy_user else None),
            )
        )

    total_cost_usd = sum(item.estimated_cost_usd for item in payload.observations)
    total_cost_krw = sum(item.estimated_cost_krw for item in payload.observations)
    total_accepted = sum(
        item.accepted_experience_count for item in payload.observations
    )
    cost_gate, cost_per_accepted = _cost_per_accepted_gate(
        total_cost_krw,
        total_accepted,
    )
    heavy_failures = sum(
        user.heavy_user and not user.heavy_user_cost_passed for user in users
    )
    gates = [
        cost_gate,
        AcceptanceGate(
            name="heavy_user_monthly_cost",
            status=(
                AcceptanceGateStatus.PASS
                if heavy_failures == 0
                else AcceptanceGateStatus.FAIL
            ),
            actual=float(heavy_failures),
            threshold=0,
            unit="users_over_3_usd",
        ),
        AcceptanceGate(
            name="beta_monthly_total_cost_hard_limit",
            status=(
                AcceptanceGateStatus.PASS
                if total_cost_usd <= 150
                else AcceptanceGateStatus.FAIL
            ),
            actual=total_cost_usd,
            threshold=150,
            unit="USD",
        ),
        AcceptanceGate(
            name="beta_monthly_total_cost_target",
            status=(
                AcceptanceGateStatus.PASS
                if total_cost_usd <= 100
                else AcceptanceGateStatus.FAIL
            ),
            actual=total_cost_usd,
            threshold=100,
            unit="USD",
        ),
    ]
    hard_gates = gates[:3]
    return CostGuardrailReport(
        period_month=payload.period_month,
        accepted=all(gate.status == AcceptanceGateStatus.PASS for gate in hard_gates),
        total_analysis_count=len(payload.observations),
        total_accepted_experience_count=total_accepted,
        total_cost_usd=total_cost_usd,
        total_cost_krw=total_cost_krw,
        cost_per_accepted_experience_krw=cost_per_accepted,
        users=users,
        gates=gates,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate LogFolio monthly AI cost guardrails"
    )
    parser.add_argument("input", type=Path)
    parser.add_argument("--output-json", type=Path)
    args = parser.parse_args()
    payload = CostGuardrailInput.model_validate_json(
        args.input.read_text(encoding="utf-8")
    )
    report = evaluate_cost_guardrails(payload)
    rendered = report.model_dump_json(indent=2, by_alias=True)
    print(rendered)
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(rendered + "\n", encoding="utf-8")
    raise SystemExit(0 if report.accepted else 1)


if __name__ == "__main__":
    main()
