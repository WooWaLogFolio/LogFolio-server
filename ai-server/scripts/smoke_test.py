import json
import os
import urllib.request


def main() -> None:
    base_url = os.environ.get("LOGFOLIO_SMOKE_BASE_URL", "http://127.0.0.1:8000")
    api_key = os.environ.get("LOGFOLIO_SMOKE_INTERNAL_API_KEY", "")
    payload = {
        "analysisRunId": "10000000-0000-0000-0000-000000000001",
        "projectId": "20000000-0000-0000-0000-000000000001",
        "documents": [
            {
                "projectFileId": "30000000-0000-0000-0000-000000000001",
                "originalName": "smoke-test.txt",
                "mimeType": "text/plain",
                "pages": [
                    {
                        "pageNumber": 1,
                        "text": "프로젝트 팀은 사용자 인터뷰를 진행했다.",
                    }
                ],
            }
        ],
    }
    request = urllib.request.Request(
        f"{base_url}/api/v1/analyses",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-Internal-API-Key": api_key,
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=35) as response:
        body = json.loads(response.read().decode("utf-8"))

    if body.get("analysisRunId") != payload["analysisRunId"]:
        raise RuntimeError("analysisRunId was not preserved")
    if body.get("projectId") != payload["projectId"]:
        raise RuntimeError("projectId was not preserved")
    if "candidates" not in body or "questions" not in body:
        raise RuntimeError("analysis response contract is incomplete")
    print("LogFolio AI smoke test passed")


if __name__ == "__main__":
    main()
