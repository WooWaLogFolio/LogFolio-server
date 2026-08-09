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


def test_structure_project() -> None:
    response = client.post(
        "/api/v1/ai/structure-project",
        json={
            "project": {
                "id": "project-1",
                "name": "LogFolio",
                "period": {
                    "startDate": "2026-07-01",
                    "endDate": "2026-08-31",
                },
                "category": "팀 프로젝트",
                "description": "개발 경험을 정리하는 포트폴리오 서비스",
            },
            "documents": [
                {
                    "id": "document-1",
                    "fileName": "프로젝트기획서.pdf",
                    "extractedText": "FastAPI를 이용해 AI 서버를 개발한다.",
                }
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["structuredProject"]["summary"] == "개발 경험을 정리하는 포트폴리오 서비스"
    assert body["structuredProject"]["results"] == []
    assert "result" in body["missingContexts"]
    assert "프로젝트기획서.pdf" in body["structuredProject"]["evidence"]


def test_structure_project_rejects_empty_description() -> None:
    response = client.post(
        "/api/v1/ai/structure-project",
        json={
            "project": {
                "name": "LogFolio",
                "description": "",
            },
            "documents": [],
        },
    )

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
