import asyncio
import logging
import time
from contextvars import ContextVar
from typing import Any, Optional

from pydantic import ValidationError

from logfolio_ai.core.errors import AppError
from logfolio_ai.llm.models import GroundedAnalysisInput, LLMCallMetrics
from logfolio_ai.llm.prompt import SYSTEM_POLICY, build_grounded_analysis_prompt
from logfolio_ai.models import AnalysisResponse
from logfolio_ai.privacy import PrivacyRedactor


logger = logging.getLogger(__name__)
_RETRYABLE_CODES = {"LLM_TIMEOUT", "LLM_PROVIDER_ERROR", "LLM_INVALID_RESPONSE"}
_RETRYABLE_HTTP_STATUSES = {408, 409, 425, 429}


class GeminiLLMProvider:
    def __init__(
        self,
        api_key: str,
        model: str,
        timeout_seconds: float,
        client: Optional[Any] = None,
        max_attempts: int = 2,
        privacy_redactor: Optional[PrivacyRedactor] = None,
    ) -> None:
        if client is None:
            from google import genai

            client = genai.Client(api_key=api_key)
        self._client = client
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._max_attempts = max_attempts
        self._privacy_redactor = privacy_redactor or PrivacyRedactor()
        self._last_call_metrics: ContextVar[Optional[LLMCallMetrics]] = ContextVar(
            "gemini_llm_call_metrics",
            default=None,
        )

    @property
    def last_call_metrics(self) -> Optional[LLMCallMetrics]:
        return self._last_call_metrics.get()

    async def analyze_grounded(
        self, request: GroundedAnalysisInput
    ) -> AnalysisResponse:
        provider_input, redaction_summary = (
            self._privacy_redactor.sanitize_grounded_input(request)
        )
        if redaction_summary.total:
            logger.info(
                "Gemini input minimized: fields=%d categories=%s",
                redaction_summary.total,
                sorted(redaction_summary.counts),
            )
        prompt = build_grounded_analysis_prompt(provider_input)
        started = time.perf_counter()
        for attempt in range(1, self._max_attempts + 1):
            try:
                result, usage = await self._generate(
                    prompt,
                    request.analysis_run_id,
                    request.project_id,
                )
                self._last_call_metrics.set(LLMCallMetrics(
                    provider="gemini",
                    model=self._model,
                    input_tokens=self._usage_value(usage, "prompt_token_count"),
                    cached_input_tokens=self._usage_value(
                        usage, "cached_content_token_count"
                    ),
                    output_tokens=self._usage_value(usage, "candidates_token_count"),
                    reasoning_tokens=self._usage_value(usage, "thoughts_token_count"),
                    latency_ms=max(
                        0, round((time.perf_counter() - started) * 1000)
                    ),
                    retry_count=attempt - 1,
                ))
                return result
            except AppError as exc:
                if exc.code not in _RETRYABLE_CODES or attempt >= self._max_attempts:
                    self._last_call_metrics.set(LLMCallMetrics(
                        provider="gemini",
                        model=self._model,
                        latency_ms=max(
                            0, round((time.perf_counter() - started) * 1000)
                        ),
                        retry_count=attempt - 1,
                        success=False,
                        error_type=exc.code,
                    ))
                    raise
                logger.warning(
                    "Retrying Gemini request: attempt=%d next_attempt=%d code=%s",
                    attempt,
                    attempt + 1,
                    exc.code,
                )
        raise RuntimeError("unreachable")

    @staticmethod
    def _usage_value(usage: Any, field: str) -> Optional[int]:
        value = getattr(usage, field, None) if usage is not None else None
        return int(value) if isinstance(value, (int, float)) and value >= 0 else None

    async def _generate(
        self,
        prompt: str,
        analysis_run_id: Any,
        project_id: Any,
    ) -> tuple[AnalysisResponse, Any]:
        from google.genai import types

        try:
            response = await asyncio.wait_for(
                self._client.aio.models.generate_content(
                    model=self._model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_POLICY.strip(),
                        response_mime_type="application/json",
                        # Let the SDK derive its supported schema from the Pydantic
                        # model. Sending Pydantic's raw JSON Schema can include
                        # keywords Gemini rejects with INVALID_ARGUMENT.
                        response_schema=AnalysisResponse,
                        temperature=0.1,
                    ),
                ),
                timeout=self._timeout_seconds,
            )
        except asyncio.TimeoutError as exc:
            raise AppError(
                code="LLM_TIMEOUT",
                message="LLM 응답 제한 시간을 초과했습니다.",
                status_code=504,
            ) from exc
        except Exception as exc:
            status_code = getattr(exc, "status_code", None)
            # google-genai ClientError exposes HTTP status as ``code`` rather
            # than ``status_code``. Treat non-retryable 4xx errors accordingly.
            if not isinstance(status_code, int):
                status_code = getattr(exc, "code", None)
            provider_message = str(exc).replace("\n", " ")[:500]
            logger.warning(
                "Gemini request failed: error_type=%s status_code=%s message=%s",
                type(exc).__name__,
                status_code,
                provider_message,
            )
            if (
                isinstance(status_code, int)
                and 400 <= status_code < 500
                and status_code not in _RETRYABLE_HTTP_STATUSES
            ):
                raise AppError(
                    code="LLM_REQUEST_ERROR",
                    message="LLM 요청 설정 또는 인증을 확인해야 합니다.",
                    status_code=502,
                ) from exc
            raise AppError(
                code="LLM_PROVIDER_ERROR",
                message="LLM 공급자 호출에 실패했습니다.",
                status_code=502,
            ) from exc

        try:
            result = AnalysisResponse.model_validate_json(response.text)
        except (ValidationError, ValueError, TypeError) as exc:
            raise AppError(
                code="LLM_INVALID_RESPONSE",
                message="LLM 응답이 분석 계약과 일치하지 않습니다.",
                status_code=502,
            ) from exc

        # Tracking identifiers are server-owned and must never be trusted to the model.
        normalized = result.model_copy(
            update={
                "analysis_run_id": analysis_run_id,
                "project_id": project_id,
                "input_source_ids": [],
                "referenced_source_ids": [],
                "ai_usage": None,
            }
        )
        return normalized, getattr(response, "usage_metadata", None)
