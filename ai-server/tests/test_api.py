from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_check() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_generate_questions() -> None:
    response = client.post(
        "/api/v1/ai/generate-questions",
        json={
            "records": [
                {
                    "id": "1",
                    "content": "JWT 기반 로그인 기능을 구현했다.",
                    "category": "개발",
                    "tags": ["Spring Boot", "JWT"],
                }
            ]
        },
    )
    assert response.status_code == 200
    assert 1 <= len(response.json()["questions"]) <= 2
    assert response.json()["questions"][0]["contextType"] == "role"


def test_generate_questions_rejects_empty_records() -> None:
    response = client.post("/api/v1/ai/generate-questions", json={"records": []})
    assert response.status_code == 422


def test_generate_card() -> None:
    response = client.post(
        "/api/v1/ai/generate-card",
        json={
            "records": [
                {
                    "id": "1",
                    "content": "로그인 API를 구현했다.",
                    "category": "백엔드",
                    "tags": ["인증"],
                }
            ],
            "answers": [],
        },
    )
    assert response.status_code == 200
    assert response.json()["card"]["title"] == "백엔드 경험"
    assert "role" in response.json()["card"]["missingContexts"]
