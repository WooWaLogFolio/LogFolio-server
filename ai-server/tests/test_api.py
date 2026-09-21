import asyncio
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from logfolio_ai.analysis.dependencies import get_analysis_orchestrator
from logfolio_ai.core.config import Settings, get_settings
from logfolio_ai.main import app, prepare_runtime

client = TestClient(app)


def valid_analysis_payload() -> dict:
    return {
        "analysisRunId": str(uuid4()),
        "projectId": str(uuid4()),
        "documents": [
            {
                "sourceId": str(uuid4()),
                "fileName": "project.pdf",
                "mimeType": "application/pdf",
                "pages": [
                    {
                        "pageNumber": 1,
                        "text": "JWT 인증 API를 구현했다.",
                    }
                ],
            }
        ],
    }


def test_health_check() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "LogFolio AI Server",
        "version": "0.1.0",
        "environment": "local",
    }


@pytest.mark.asyncio
async def test_prepare_runtime_skips_fake_embedding(monkeypatch) -> None:
    def fail_if_called():
        raise AssertionError("fake embedding should not be preloaded")

    monkeypatch.setattr("logfolio_ai.main.get_embedding_provider", fail_if_called)

    await prepare_runtime(Settings(embedding_provider="fake"))


@pytest.mark.asyncio
async def test_prepare_runtime_validates_e5_dimension(monkeypatch) -> None:
    class Provider:
        dimension = 768

    monkeypatch.setattr(
        "logfolio_ai.main.get_embedding_provider",
        lambda: Provider(),
    )

    await prepare_runtime(Settings(embedding_provider="e5", vector_dimension=768))


@pytest.mark.asyncio
async def test_prepare_runtime_rejects_e5_dimension_mismatch(monkeypatch) -> None:
    class Provider:
        dimension = 384

    monkeypatch.setattr(
        "logfolio_ai.main.get_embedding_provider",
        lambda: Provider(),
    )

    with pytest.raises(RuntimeError, match="dimension"):
        await prepare_runtime(Settings(embedding_provider="e5", vector_dimension=768))


@pytest.mark.asyncio
async def test_prepare_runtime_preloads_gemini_provider(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(
        "logfolio_ai.main.get_llm_provider",
        lambda: calls.append("gemini"),
    )

    await prepare_runtime(
        Settings(llm_provider="gemini", gemini_api_key="test-key")
    )

    assert calls == ["gemini"]


def test_fake_analysis_preserves_tracking_ids() -> None:
    payload = valid_analysis_payload()

    response = client.post("/api/v1/analyses", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["analysisRunId"] == payload["analysisRunId"]
    assert body["projectId"] == payload["projectId"]
    assert body["summary"] == "Fake LLM 근거 기반 분석 결과입니다."
    assert body["candidates"] == []
    assert body["questions"] == []


def test_validation_error_uses_shared_error_shape() -> None:
    payload = valid_analysis_payload()
    payload["analysisRunId"] = "not-a-uuid"

    response = client.post("/api/v1/analyses", json=payload)

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert body["message"] == "요청 값이 API 계약과 일치하지 않습니다."
    assert body["details"][0]["field"] == "analysisRunId"


def test_not_found_uses_shared_error_shape() -> None:
    response = client.get("/not-found")

    assert response.status_code == 404
    assert response.json() == {
        "code": "NOT_FOUND",
        "message": "요청한 API를 찾을 수 없습니다.",
        "details": [],
    }


def test_analysis_requires_matching_internal_api_key_when_configured() -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(
        internal_auth_required=True,
        internal_api_key="spring-secret",
    )
    try:
        missing = client.post("/api/v1/analyses", json=valid_analysis_payload())
        invalid = client.post(
            "/api/v1/analyses",
            json=valid_analysis_payload(),
            headers={"X-Internal-API-Key": "wrong-secret"},
        )
        valid = client.post(
            "/api/v1/analyses",
            json=valid_analysis_payload(),
            headers={"X-Internal-API-Key": "spring-secret"},
        )
    finally:
        app.dependency_overrides.clear()

    assert missing.status_code == 401
    assert missing.json()["code"] == "INTERNAL_AUTH_FAILED"
    assert invalid.status_code == 401
    assert "spring-secret" not in invalid.text
    assert valid.status_code == 200


def test_required_internal_auth_fails_closed_without_server_key() -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(
        internal_auth_required=True,
    )
    try:
        response = client.post("/api/v1/analyses", json=valid_analysis_payload())
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 500
    assert response.json()["code"] == "INTERNAL_AUTH_NOT_CONFIGURED"


def test_non_local_environment_fails_closed_without_server_key() -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(
        environment="production",
        internal_auth_required=False,
    )
    try:
        response = client.post("/api/v1/analyses", json=valid_analysis_payload())
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 500
    assert response.json()["code"] == "INTERNAL_AUTH_NOT_CONFIGURED"


def test_analysis_timeout_uses_shared_error_shape() -> None:
    class SlowOrchestrator:
        async def analyze(self, request):
            del request
            await asyncio.sleep(0.05)

    app.dependency_overrides[get_settings] = lambda: Settings(
        analysis_timeout_seconds=0.001,
    )
    app.dependency_overrides[get_analysis_orchestrator] = lambda: SlowOrchestrator()
    try:
        response = client.post("/api/v1/analyses", json=valid_analysis_payload())
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 504
    assert response.json() == {
        "code": "ANALYSIS_TIMEOUT",
        "message": "AI 분석 제한 시간을 초과했습니다.",
        "details": [],
    }
