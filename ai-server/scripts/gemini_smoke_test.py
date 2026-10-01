import json
import os
import time
import urllib.request


ANALYSIS_RUN_ID = "70000000-0000-0000-0000-000000000001"
PROJECT_ID = "80000000-0000-0000-0000-000000000001"


def main() -> None:
    base_url = os.environ["LOGFOLIO_SMOKE_BASE_URL"]
    api_key = os.environ["LOGFOLIO_SMOKE_INTERNAL_API_KEY"]
    max_seconds = float(os.environ.get("LOGFOLIO_SMOKE_MAX_SECONDS", "30"))
    payload = {
        "analysisRunId": ANALYSIS_RUN_ID,
        "projectId": PROJECT_ID,
        "documents": [
            {
                "projectFileId": "90000000-0000-0000-0000-000000000001",
                "originalName": "synthetic-team-project.txt",
                "mimeType": "text/plain",
                "pages": [
                    {
                        "pageNumber": 1,
                        "text": (
                            "프로젝트 팀은 사용자 인터뷰를 5회 진행했다. "
                            "인터뷰 결과를 바탕으로 로그인 절차를 간소화했다. "
                            "이 문서에는 특정 팀원의 개인 기여가 기록되어 있지 않다."
                        ),
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
    started_at = time.perf_counter()
    with urllib.request.urlopen(request, timeout=max_seconds + 5) as response:
        body = json.loads(response.read().decode("utf-8"))
    elapsed_seconds = time.perf_counter() - started_at

    if elapsed_seconds > max_seconds:
        raise RuntimeError(
            f"Gemini analysis exceeded {max_seconds:.0f}s: {elapsed_seconds:.3f}s"
        )
    if body.get("analysisRunId") != ANALYSIS_RUN_ID:
        raise RuntimeError("analysisRunId was not preserved")
    if body.get("projectId") != PROJECT_ID:
        raise RuntimeError("projectId was not preserved")
    if len(body.get("candidates", [])) > 3:
        raise RuntimeError("Gemini returned more than three candidates")
    if len(body.get("questions", [])) > 2:
        raise RuntimeError("Gemini returned more than two questions")

    forbidden_provenance = {"USER_INPUT", "USER_CONFIRMED", "USER_EDITED"}
    for candidate in body.get("candidates", []):
        for claim in candidate.get("claims", []):
            if claim.get("provenanceType") in forbidden_provenance:
                raise RuntimeError("Gemini forged a user-owned provenance state")

    print(
        json.dumps(
            {
                "success": True,
                "elapsedSeconds": round(elapsed_seconds, 3),
                "summary": body["summary"],
                "candidateCount": len(body.get("candidates", [])),
                "questionCount": len(body.get("questions", [])),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
