from uuid import uuid4

from fastapi.testclient import TestClient

from logfolio_ai.main import app

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


def test_fake_analysis_preserves_tracking_ids() -> None:
    payload = valid_analysis_payload()

    response = client.post("/api/v1/analyses", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["analysisRunId"] == payload["analysisRunId"]
    assert body["projectId"] == payload["projectId"]
    assert body["summary"] == "Fake LLM 분석 결과입니다."
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
