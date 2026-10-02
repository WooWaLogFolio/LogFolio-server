import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from logfolio_ai.core.config import Settings
from logfolio_ai.core.errors import AppError
from logfolio_ai.llm.factory import build_llm_provider
from logfolio_ai.llm.fake import FakeLLMProvider
from logfolio_ai.llm.gemini import GeminiLLMProvider
from logfolio_ai.llm.models import GroundedAnalysisInput, GroundedChunk
from logfolio_ai.llm.prompt import SYSTEM_POLICY
from logfolio_ai.models import AnalysisResponse, AnalysisResultType, InformationNeedType
from logfolio_ai.rag import AnalysisPurpose


def grounded_request() -> GroundedAnalysisInput:
    return GroundedAnalysisInput(
        analysis_run_id=uuid4(),
        project_id=uuid4(),
        chunks=[
            GroundedChunk(
                chunk_id=uuid4(),
                source_id=uuid4(),
                source_name="project.pdf",
                page_number=1,
                text="팀은 인터뷰를 진행했다.",
                distance=0.1,
                purposes=[AnalysisPurpose.PROJECT_OVERVIEW],
            )
        ],
    )


@pytest.mark.asyncio
async def test_fake_provider_is_deterministic() -> None:
    request = grounded_request()

    result = await FakeLLMProvider().analyze_grounded(request)

    assert result.analysis_run_id == request.analysis_run_id
    assert result.project_id == request.project_id
    assert result.candidates == []
    assert result.questions == []


def test_factory_uses_fake_by_default() -> None:
    provider = build_llm_provider(Settings())

    assert isinstance(provider, FakeLLMProvider)


def test_factory_rejects_gemini_without_api_key() -> None:
    with pytest.raises(AppError) as error:
        build_llm_provider(Settings(llm_provider="gemini"))

    assert error.value.code == "LLM_CONFIGURATION_ERROR"


@pytest.mark.asyncio
async def test_gemini_provider_parses_schema_and_preserves_server_ids() -> None:
    request = grounded_request()
    generated_run_id = uuid4()
    generated_project_id = uuid4()
    generated_source_id = uuid4()
    response_text = json.dumps(
        {
            "analysisRunId": str(generated_run_id),
            "projectId": str(generated_project_id),
            "inputSourceIds": [str(generated_source_id)],
            "referencedSourceIds": [str(generated_source_id)],
            "summary": "프로젝트 자료를 분석했습니다.",
            "candidates": [],
            "questions": [],
        }
    )
    generate_content = AsyncMock(
        return_value=SimpleNamespace(
            text=response_text,
            usage_metadata=SimpleNamespace(
                prompt_token_count=120,
                cached_content_token_count=20,
                candidates_token_count=30,
                thoughts_token_count=4,
            ),
        )
    )
    client = SimpleNamespace(
        aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
    )
    provider = GeminiLLMProvider(
        api_key="test-key",
        model="test-model",
        timeout_seconds=30,
        client=client,
    )

    result = await provider.analyze_grounded(request)

    assert result.analysis_run_id == request.analysis_run_id
    assert result.project_id == request.project_id
    assert result.summary == "프로젝트 자료를 분석했습니다."
    assert result.input_source_ids == []
    assert result.referenced_source_ids == []
    assert provider.last_call_metrics.provider == "gemini"
    assert provider.last_call_metrics.model == "test-model"
    assert provider.last_call_metrics.input_tokens == 120
    assert provider.last_call_metrics.cached_input_tokens == 20
    assert provider.last_call_metrics.output_tokens == 30
    assert provider.last_call_metrics.reasoning_tokens == 4
    assert provider.last_call_metrics.retry_count == 0
    call = generate_content.await_args.kwargs
    assert call["model"] == "test-model"
    assert "팀은 인터뷰를 진행했다." in call["contents"]
    assert "Analyze only the retrieved chunks" in call["contents"]
    assert SYSTEM_POLICY.strip() not in call["contents"]
    assert call["config"].system_instruction == SYSTEM_POLICY.strip()
    assert call["config"].response_json_schema == AnalysisResponse.model_json_schema(
        by_alias=True
    )


@pytest.mark.asyncio
async def test_gemini_provider_accepts_additional_source_outcome() -> None:
    request = grounded_request()
    response_text = json.dumps(
        {
            "analysisRunId": str(uuid4()),
            "projectId": str(uuid4()),
            "summary": "경험을 특정하기에는 자료가 부족합니다.",
            "candidates": [],
            "questions": [],
            "informationNeed": "ADDITIONAL_SOURCE",
            "informationNeedReason": "구체적인 행동이나 결정 기록이 필요합니다.",
        }
    )
    generate_content = AsyncMock(return_value=SimpleNamespace(text=response_text))
    client = SimpleNamespace(
        aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
    )

    result = await GeminiLLMProvider(
        "test-key", "test-model", 30, client=client
    ).analyze_grounded(request)

    assert result.information_need == InformationNeedType.ADDITIONAL_SOURCE
    assert result.result_types == [AnalysisResultType.NEEDS_CONTEXT]
    assert result.questions == []


@pytest.mark.asyncio
async def test_gemini_provider_maps_timeout_to_app_error() -> None:
    generate_content = AsyncMock(side_effect=asyncio.TimeoutError)
    client = SimpleNamespace(
        aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
    )
    provider = GeminiLLMProvider("test-key", "test-model", 30, client=client)

    with pytest.raises(AppError) as error:
        await provider.analyze_grounded(grounded_request())

    assert error.value.code == "LLM_TIMEOUT"
    assert error.value.status_code == 504
    assert generate_content.await_count == 2


@pytest.mark.asyncio
async def test_gemini_provider_rejects_invalid_structured_output() -> None:
    generate_content = AsyncMock(return_value=SimpleNamespace(text="not-json"))
    client = SimpleNamespace(
        aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
    )
    provider = GeminiLLMProvider("test-key", "test-model", 30, client=client)

    with pytest.raises(AppError) as error:
        await provider.analyze_grounded(grounded_request())

    assert error.value.code == "LLM_INVALID_RESPONSE"
    assert generate_content.await_count == 2


@pytest.mark.asyncio
async def test_gemini_provider_retries_invalid_output_and_accepts_second_response() -> None:
    request = grounded_request()
    valid_response = json.dumps(
        {
            "analysisRunId": str(uuid4()),
            "projectId": str(uuid4()),
            "summary": "재시도 후 정상 응답",
            "candidates": [],
            "questions": [],
        }
    )
    generate_content = AsyncMock(
        side_effect=[
            SimpleNamespace(text="not-json"),
            SimpleNamespace(text=valid_response),
        ]
    )
    client = SimpleNamespace(
        aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
    )

    provider = GeminiLLMProvider("test-key", "test-model", 14, client=client)

    result = await provider.analyze_grounded(request)

    assert result.summary == "재시도 후 정상 응답"
    assert generate_content.await_count == 2
    assert provider.last_call_metrics.retry_count == 1


@pytest.mark.asyncio
async def test_gemini_provider_does_not_retry_non_transient_4xx() -> None:
    class InvalidRequestError(Exception):
        status_code = 400

    generate_content = AsyncMock(side_effect=InvalidRequestError("invalid key"))
    client = SimpleNamespace(
        aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
    )
    provider = GeminiLLMProvider("test-key", "test-model", 14, client=client)

    with pytest.raises(AppError) as error:
        await provider.analyze_grounded(grounded_request())

    assert error.value.code == "LLM_REQUEST_ERROR"
    assert generate_content.await_count == 1


def test_gemini_timeout_budget_allows_two_attempts() -> None:
    settings = Settings(
        llm_provider="gemini",
        gemini_api_key="test-key",
        llm_timeout_seconds=14,
        analysis_timeout_seconds=30,
    )

    assert settings.llm_timeout_seconds * 2 < settings.analysis_timeout_seconds
