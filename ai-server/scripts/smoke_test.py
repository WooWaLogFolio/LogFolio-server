import json
import os
import urllib.request


def request_json(
    base_url: str,
    path: str,
    api_key: str,
    *,
    method: str = "POST",
    payload: dict = None,
):
    data = (
        json.dumps(payload, ensure_ascii=False).encode("utf-8")
        if payload is not None
        else None
    )
    request = urllib.request.Request(
        f"{base_url}{path}",
        data=data,
        headers={
            "Content-Type": "application/json",
            "X-Internal-API-Key": api_key,
        },
        method=method,
    )
    with urllib.request.urlopen(request, timeout=35) as response:
        if response.status == 204:
            return None
        return json.loads(response.read().decode("utf-8"))


def main() -> None:
    base_url = os.environ.get("LOGFOLIO_SMOKE_BASE_URL", "http://127.0.0.1:8000")
    api_key = os.environ.get("LOGFOLIO_SMOKE_INTERNAL_API_KEY", "")
    project_id = "20000000-0000-0000-0000-000000000001"
    source_id = "30000000-0000-0000-0000-000000000001"
    source = {
        "sourceId": source_id,
        "sourceType": "PROJECT_FILE",
        "sourceName": "smoke-test.txt",
        "mimeType": "text/plain",
        "pages": [
            {
                "pageNumber": 1,
                "text": "프로젝트 팀은 사용자 인터뷰를 진행했다.",
            }
        ],
    }
    index_body = request_json(
        base_url,
        "/api/v1/sources/index",
        api_key,
        payload={"projectId": project_id, "sources": [source]},
    )
    if index_body.get("indexedCount") != 1:
        raise RuntimeError("Source indexing did not complete")

    payload = {
        "analysisRunId": "10000000-0000-0000-0000-000000000001",
        "projectId": project_id,
        "sourceIds": [source_id],
    }
    body = request_json(
        base_url,
        "/api/v1/analyses",
        api_key,
        payload=payload,
    )

    if body.get("analysisRunId") != payload["analysisRunId"]:
        raise RuntimeError("analysisRunId was not preserved")
    if body.get("projectId") != payload["projectId"]:
        raise RuntimeError("projectId was not preserved")
    if "candidates" not in body or "questions" not in body:
        raise RuntimeError("analysis response contract is incomplete")
    if body.get("inputSourceIds") != [source_id]:
        raise RuntimeError("inputSourceIds did not preserve the analysis snapshot")
    if body.get("aiUsage", {}).get("provider") != "fake":
        raise RuntimeError("offline smoke test must use the Fake Provider")

    request_json(
        base_url,
        f"/api/v1/projects/{project_id}/sources/{source_id}/index",
        api_key,
        method="DELETE",
    )
    print("LogFolio AI offline contract smoke test passed")


if __name__ == "__main__":
    main()
