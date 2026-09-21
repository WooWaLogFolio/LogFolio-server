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
from logfolio_ai.rag import AnalysisPurpose


def grounded_request() -> GroundedAnalysisInput:
    return GroundedAnalysisInput(
        analysis_run_id=uuid4(),
        project_id=uuid4(),
        chunks=[
            GroundedChunk(
                chunk_id=uuid4(),
                source_id=uuid4(),
                file_name="project.pdf",
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
    response_text = json.dumps(
        {
            "analysisRunId": str(generated_run_id),
            "projectId": str(generated_project_id),
            "summary": "프로젝트 자료를 분석했습니다.",
            "candidates": [],
            "questions": [],
        }
    )
    generate_content = AsyncMock(return_value=SimpleNamespace(text=response_text))
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
    call = generate_content.await_args.kwargs
    assert call["model"] == "test-model"
    assert "팀은 인터뷰를 진행했다." in call["contents"]
    assert "Analyze only the retrieved chunks" in call["contents"]


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
