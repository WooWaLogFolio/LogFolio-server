import asyncio
import json
import os
import time
import urllib.request


ANALYSIS_RUN_ID = "40000000-0000-0000-0000-000000000001"
PROJECT_ID = "50000000-0000-0000-0000-000000000001"
SOURCE_ID = "60000000-0000-0000-0000-000000000001"
MODEL_NAME = "intfloat/multilingual-e5-base"


def call_analysis() -> tuple[dict, float]:
    base_url = os.environ["LOGFOLIO_SMOKE_BASE_URL"]
    api_key = os.environ["LOGFOLIO_SMOKE_INTERNAL_API_KEY"]
    max_seconds = float(os.environ.get("LOGFOLIO_SMOKE_MAX_SECONDS", "30"))
    payload = {
        "analysisRunId": ANALYSIS_RUN_ID,
        "projectId": PROJECT_ID,
        "documents": [
            {
                "sourceId": SOURCE_ID,
                "sourceName": "e5-rag-smoke.txt",
                "mimeType": "text/plain",
                "pages": [
                    {
                        "pageNumber": 1,
                        "text": (
                            "JWT 액세스 토큰과 리프레시 토큰을 사용한 로그인 인증 기능을 구현했다. "
                            "사용자 인터뷰 다섯 건을 진행하고 요구사항을 정리했다. "
                            "데이터베이스 인덱스를 추가해 조회 응답 시간을 줄였다."
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
            f"analysis exceeded {max_seconds:.0f}s: {elapsed_seconds:.3f}s"
        )
    if body.get("analysisRunId") != ANALYSIS_RUN_ID:
        raise RuntimeError("analysisRunId was not preserved")
    if body.get("projectId") != PROJECT_ID:
        raise RuntimeError("projectId was not preserved")
    return body, elapsed_seconds


async def verify_pgvector() -> dict:
    import asyncpg

    connection = await asyncpg.connect(os.environ["LOGFOLIO_SMOKE_DATABASE_URL"])
    try:
        row = await connection.fetchrow(
            """
            SELECT
                COUNT(*) AS chunk_count,
                MIN(vector_dims(embedding)) AS min_dimension,
                MAX(vector_dims(embedding)) AS max_dimension,
                ARRAY_AGG(DISTINCT embedding_model) AS models
            FROM ai_document_chunks
            WHERE project_id = $1::uuid AND source_id = $2::uuid
            """,
            PROJECT_ID,
            SOURCE_ID,
        )
        other_project_count = await connection.fetchval(
            """
            SELECT COUNT(*)
            FROM ai_document_chunks
            WHERE project_id = $1::uuid AND source_id = $2::uuid
            """,
            "50000000-0000-0000-0000-000000000099",
            SOURCE_ID,
        )
    finally:
        await connection.close()

    result = dict(row)
    if result["chunk_count"] < 1:
        raise RuntimeError("no document chunks were stored")
    if result["min_dimension"] != 768 or result["max_dimension"] != 768:
        raise RuntimeError("stored embedding dimension is not 768")
    if result["models"] != [MODEL_NAME]:
        raise RuntimeError("stored embedding model does not match E5")
    if other_project_count != 0:
        raise RuntimeError("source data leaked into another project scope")
    result["otherProjectCount"] = other_project_count
    return result


def main() -> None:
    response, elapsed_seconds = call_analysis()
    database = asyncio.run(verify_pgvector())
    print(
        json.dumps(
            {
                "success": True,
                "elapsedSeconds": round(elapsed_seconds, 3),
                "summary": response["summary"],
                "database": database,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
