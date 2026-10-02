import time
from contextvars import ContextVar
from typing import Optional

from logfolio_ai.llm.models import GroundedAnalysisInput, LLMCallMetrics
from logfolio_ai.models import AnalysisResponse


class FakeLLMProvider:
    """Deterministic provider for local development and contract tests."""

    def __init__(self) -> None:
        self._last_call_metrics: ContextVar[Optional[LLMCallMetrics]] = ContextVar(
            "fake_llm_call_metrics",
            default=None,
        )

    @property
    def last_call_metrics(self) -> Optional[LLMCallMetrics]:
        return self._last_call_metrics.get()

    async def analyze_grounded(
        self, request: GroundedAnalysisInput
    ) -> AnalysisResponse:
        started = time.perf_counter()
        result = AnalysisResponse(
            analysis_run_id=request.analysis_run_id,
            project_id=request.project_id,
            summary="Fake LLM 근거 기반 분석 결과입니다.",
            candidates=[],
            questions=[],
        )
        self._last_call_metrics.set(LLMCallMetrics(
            provider="fake",
            model="fake",
            input_tokens=0,
            cached_input_tokens=0,
            output_tokens=0,
            reasoning_tokens=0,
            latency_ms=max(0, round((time.perf_counter() - started) * 1000)),
            retry_count=0,
        ))
        return result
