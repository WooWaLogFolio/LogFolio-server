import argparse
import asyncio
from pathlib import Path
from typing import Awaitable, Callable, List, Optional

from pydantic import Field

from logfolio_ai.evaluation.pipeline_runner import (
    load_pipeline_cases,
    run_pipeline_eval,
)
from logfolio_ai.evaluation.project_mismatch_runner import (
    load_project_mismatch_cases,
    run_project_mismatch_eval,
)
from logfolio_ai.evaluation.resilience_runner import (
    load_resilience_cases,
    run_resilience_eval,
)
from logfolio_ai.evaluation.runner import evaluate_cases, load_cases
from logfolio_ai.evaluation.source_lifecycle_runner import (
    load_source_lifecycle_cases,
    run_source_lifecycle_eval,
)
from logfolio_ai.models.base import ContractModel


class OfflineCheckResult(ContractModel):
    name: str
    dataset: str
    total: int = Field(ge=0)
    passed: int = Field(ge=0)
    failed: int = Field(ge=0)
    pass_rate: float = Field(ge=0, le=1)
    error: Optional[str] = None


class DeferredCheck(ContractModel):
    name: str
    reason: str


class OfflineSuiteReport(ContractModel):
    accepted: bool
    total: int = Field(ge=0)
    passed: int = Field(ge=0)
    failed: int = Field(ge=0)
    pass_rate: float = Field(ge=0, le=1)
    checks: List[OfflineCheckResult]
    deferred_checks: List[DeferredCheck]


def _result(name: str, dataset: str, report) -> OfflineCheckResult:
    return OfflineCheckResult(
        name=name,
        dataset=dataset,
        total=report.total,
        passed=report.passed,
        failed=report.failed,
        pass_rate=report.pass_rate,
    )


async def _run_async_check(
    name: str,
    loader: Callable[[], tuple],
    runner: Callable[[list, str], Awaitable],
) -> OfflineCheckResult:
    dataset = "unknown"
    try:
        dataset, cases = loader()
        return _result(name, dataset, await runner(cases, dataset))
    except Exception as exc:
        return OfflineCheckResult(
            name=name,
            dataset=dataset,
            total=1,
            passed=0,
            failed=1,
            pass_rate=0,
            error=f"{type(exc).__name__}: {exc}",
        )


async def run_offline_suite() -> OfflineSuiteReport:
    checks: List[OfflineCheckResult] = []
    try:
        policy_report = evaluate_cases(load_cases())
        checks.append(_result("AI_POLICY", "policy_cases", policy_report))
    except Exception as exc:
        checks.append(
            OfflineCheckResult(
                name="AI_POLICY",
                dataset="policy_cases",
                total=1,
                passed=0,
                failed=1,
                pass_rate=0,
                error=f"{type(exc).__name__}: {exc}",
            )
        )

    async_checks = [
        ("FULL_PIPELINE", load_pipeline_cases, run_pipeline_eval),
        ("FAILURE_RECOVERY", load_resilience_cases, run_resilience_eval),
        (
            "SOURCE_LIFECYCLE",
            load_source_lifecycle_cases,
            run_source_lifecycle_eval,
        ),
        (
            "PROJECT_MISMATCH",
            load_project_mismatch_cases,
            run_project_mismatch_eval,
        ),
    ]
    for name, loader, runner in async_checks:
        checks.append(await _run_async_check(name, loader, runner))

    total = sum(check.total for check in checks)
    passed = sum(check.passed for check in checks)
    failed = sum(check.failed for check in checks)
    return OfflineSuiteReport(
        accepted=failed == 0,
        total=total,
        passed=passed,
        failed=failed,
        pass_rate=passed / total if total else 0,
        checks=checks,
        deferred_checks=[
            DeferredCheck(
                name="LOCAL_E5_RETRIEVAL",
                reason="로컬 모델 파일과 embedding 추가 의존성이 필요한 별도 평가",
            ),
            DeferredCheck(
                name="REAL_PROVIDER_PRODUCT_EVAL",
                reason="실제 Gemini API 호출 승인과 비용이 필요한 별도 평가",
            ),
            DeferredCheck(
                name="HUMAN_QUALITY_EVAL",
                reason="실제 모델 결과에 대한 사람의 점수 입력이 필요한 별도 평가",
            ),
            DeferredCheck(
                name="SPRING_INTEGRATION",
                reason="Spring 서버와 운영 계약 연결 후 실행하는 별도 통합 평가",
            ),
        ],
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run all dependency-free LogFolio AI offline quality gates"
    )
    parser.add_argument("--output-json", type=Path)
    args = parser.parse_args()
    report = asyncio.run(run_offline_suite())
    rendered = report.model_dump_json(indent=2, by_alias=True)
    print(rendered)
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(rendered + "\n", encoding="utf-8")
    raise SystemExit(0 if report.accepted else 1)


if __name__ == "__main__":
    main()
