import asyncio
import json
import os
import time
import urllib.request


ANALYSIS_RUN_ID = "a0000000-0000-0000-0000-000000000001"
PROJECT_ID = "b0000000-0000-0000-0000-000000000001"
SOURCE_ID = "c0000000-0000-0000-0000-000000000001"
OTHER_PROJECT_ID = "b0000000-0000-0000-0000-000000000099"
OTHER_SOURCE_ID = "c0000000-0000-0000-0000-000000000099"
OTHER_CHUNK_ID = "d0000000-0000-0000-0000-000000000099"
MODEL_NAME = "intfloat/multilingual-e5-base"
SOURCE_TEXT = (
    "프로젝트 팀은 사용자 인터뷰를 5회 진행했다. "
    "인터뷰 결과를 바탕으로 로그인 절차를 간소화했다. "
    "로그인 완료까지 필요한 화면 수가 5개에서 3개로 줄었다. "
    "이 문서에는 특정 팀원의 개인 기여가 기록되어 있지 않다."
)
DECOY_TEXT = "격리 실패 표시: 사용자가 매출을 999배 높였고 모든 업무를 혼자 수행했다."


async def seed_other_project() -> None:
    import asyncpg

    vector = "[" + ",".join(["0.001"] * 768) + "]"
    connection = await asyncpg.connect(os.environ["LOGFOLIO_SMOKE_DATABASE_URL"])
    try:
        await connection.execute(
            """
            INSERT INTO ai_document_chunks (
                chunk_id, project_id, source_id, source_name, sequence, page_number,
                section_title, char_start, char_end, token_count, content, embedding,
                embedding_model
            ) VALUES (
                $1::uuid, $2::uuid, $3::uuid, 'other-project.txt', 0, 1,
                NULL, 0, $4, 20, $5, $6::vector, $7
            )
            ON CONFLICT (chunk_id) DO UPDATE SET
                project_id = EXCLUDED.project_id,
                source_id = EXCLUDED.source_id,
                content = EXCLUDED.content,
                embedding = EXCLUDED.embedding,
                embedding_model = EXCLUDED.embedding_model
            """,
            OTHER_CHUNK_ID,
            OTHER_PROJECT_ID,
            OTHER_SOURCE_ID,
            len(DECOY_TEXT),
            DECOY_TEXT,
            vector,
            MODEL_NAME,
        )
    finally:
        await connection.close()


async def remove_other_project() -> None:
    import asyncpg

    connection = await asyncpg.connect(os.environ["LOGFOLIO_SMOKE_DATABASE_URL"])
    try:
        await connection.execute(
            "DELETE FROM ai_document_chunks WHERE chunk_id = $1::uuid",
            OTHER_CHUNK_ID,
        )
    finally:
        await connection.close()


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
                "sourceName": "synthetic-full-pipeline.txt",
                "mimeType": "text/plain",
                "pages": [{"pageNumber": 1, "text": SOURCE_TEXT}],
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
            f"full pipeline exceeded {max_seconds:.0f}s: {elapsed_seconds:.3f}s"
        )
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
        decoy_count = await connection.fetchval(
            """
            SELECT COUNT(*) FROM ai_document_chunks
            WHERE project_id = $1::uuid AND source_id = $2::uuid
            """,
            OTHER_PROJECT_ID,
            OTHER_SOURCE_ID,
        )
    finally:
        await connection.close()

    result = dict(row)
    if result["chunk_count"] < 1:
        raise RuntimeError("no E5 document chunks were stored")
    if result["min_dimension"] != 768 or result["max_dimension"] != 768:
        raise RuntimeError("stored E5 embedding dimension is not 768")
    if result["models"] != [MODEL_NAME]:
        raise RuntimeError("stored embedding model does not match E5")
    if decoy_count != 1:
        raise RuntimeError("other-project isolation fixture was not preserved")
    result["otherProjectFixtureCount"] = decoy_count
    return result


def verify_response(body: dict) -> dict:
    if body.get("analysisRunId") != ANALYSIS_RUN_ID:
        raise RuntimeError("analysisRunId was not preserved")
    if body.get("projectId") != PROJECT_ID:
        raise RuntimeError("projectId was not preserved")
    candidates = body.get("candidates", [])
    questions = body.get("questions", [])
    if not candidates or len(candidates) > 3:
        raise RuntimeError("candidate count must be between one and three")
    if len(questions) > 2:
        raise RuntimeError("Gemini returned more than two questions")
    if DECOY_TEXT in body.get("summary", ""):
        raise RuntimeError("another project's content leaked into the summary")

    evidence_count = 0
    forbidden_provenance = {"USER_INPUT", "USER_CONFIRMED", "USER_EDITED"}
    for candidate in candidates:
        for claim in candidate.get("claims", []):
            if claim.get("provenanceType") in forbidden_provenance:
                raise RuntimeError("Gemini forged a user-owned provenance state")
            for evidence in claim.get("evidences", []):
                evidence_count += 1
                if evidence.get("sourceId") != SOURCE_ID:
                    raise RuntimeError("evidence leaked from another project or source")
                if evidence.get("excerpt") not in SOURCE_TEXT:
                    raise RuntimeError("evidence excerpt does not match the source text")
    if evidence_count < 1:
        raise RuntimeError("full pipeline returned no grounded evidence")
    return {
        "candidateCount": len(candidates),
        "questionCount": len(questions),
        "evidenceCount": evidence_count,
    }


def main() -> None:
    asyncio.run(seed_other_project())
    try:
        response, elapsed_seconds = call_analysis()
        response_result = verify_response(response)
        database_result = asyncio.run(verify_pgvector())
    finally:
        asyncio.run(remove_other_project())

    print(
        json.dumps(
            {
                "success": True,
                "elapsedSeconds": round(elapsed_seconds, 3),
                "summary": response["summary"],
                **response_result,
                "database": database_result,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
