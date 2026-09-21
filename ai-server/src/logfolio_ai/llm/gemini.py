import asyncio
from typing import Any, Optional

from pydantic import ValidationError

from logfolio_ai.core.errors import AppError
from logfolio_ai.llm.models import GroundedAnalysisInput
from logfolio_ai.llm.prompt import build_grounded_analysis_prompt
from logfolio_ai.models import AnalysisResponse


class GeminiLLMProvider:
    def __init__(
        self,
        api_key: str,
        model: str,
        timeout_seconds: float,
        client: Optional[Any] = None,
    ) -> None:
        if client is None:
            from google import genai

            client = genai.Client(api_key=api_key)
        self._client = client
        self._model = model
        self._timeout_seconds = timeout_seconds

    async def analyze_grounded(
        self, request: GroundedAnalysisInput
    ) -> AnalysisResponse:
        return await self._generate(
            build_grounded_analysis_prompt(request),
            request.analysis_run_id,
            request.project_id,
        )

    async def _generate(
        self,
        prompt: str,
        analysis_run_id: Any,
        project_id: Any,
    ) -> AnalysisResponse:
        from google.genai import types

        try:
            response = await asyncio.wait_for(
                self._client.aio.models.generate_content(
                    model=self._model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
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
        return result.model_copy(
            update={
                "analysis_run_id": analysis_run_id,
                "project_id": project_id,
            }
        )
