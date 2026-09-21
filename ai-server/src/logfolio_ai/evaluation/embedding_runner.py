import asyncio
import json
import math
import os
from dataclasses import dataclass
from typing import List, Sequence

from logfolio_ai.embedding.e5 import E5EmbeddingProvider


@dataclass(frozen=True)
class RetrievalCase:
    query: str
    expected_passage: str
    distractors: Sequence[str]


CASES = (
    RetrievalCase(
        query="로그인 보안을 위해 어떤 인증 방식을 구현했나요?",
        expected_passage="JWT 액세스 토큰과 리프레시 토큰을 사용한 로그인 인증 기능을 구현했다.",
        distractors=(
            "사용자 인터뷰 다섯 건을 진행하고 요구사항을 정리했다.",
            "데이터베이스 인덱스를 추가해 조회 응답 시간을 줄였다.",
        ),
    ),
    RetrievalCase(
        query="사용자 요구를 파악하기 위해 어떤 조사를 했나요?",
        expected_passage="사용자 인터뷰 다섯 건을 진행하고 요구사항을 정리했다.",
        distractors=(
            "JWT 액세스 토큰과 리프레시 토큰을 사용한 로그인 인증 기능을 구현했다.",
            "발표 자료의 색상과 글꼴을 새로운 디자인으로 변경했다.",
        ),
    ),
    RetrievalCase(
        query="서비스의 조회 성능을 어떻게 개선했나요?",
        expected_passage="데이터베이스 인덱스를 추가하고 쿼리를 최적화해 조회 응답 시간을 줄였다.",
        distractors=(
            "프로젝트 결과 발표를 위해 데모 영상을 제작했다.",
            "사용자 인터뷰 질문지를 작성하고 참여자를 모집했다.",
        ),
    ),
)


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return numerator / (left_norm * right_norm)


async def evaluate() -> dict:
    model_name = os.environ.get(
        "LOGFOLIO_AI_EMBEDDING_MODEL",
        "intfloat/multilingual-e5-base",
    )
    expected_dimension = int(os.environ.get("LOGFOLIO_AI_VECTOR_DIMENSION", "768"))
    provider = E5EmbeddingProvider(model_name=model_name, batch_size=8)

    results: List[dict] = []
    vectors_normalized = True
    vector_dimensions_match = True
    for case in CASES:
        passages = [case.expected_passage, *case.distractors]
        passage_vectors = await provider.embed_documents(passages)
        query_vector = await provider.embed_query(case.query)
        all_vectors = [query_vector, *passage_vectors]
        vectors_normalized = vectors_normalized and all(
            math.isclose(
                math.sqrt(sum(value * value for value in vector)),
                1.0,
                rel_tol=1e-5,
                abs_tol=1e-5,
            )
            for vector in all_vectors
        )
        vector_dimensions_match = vector_dimensions_match and all(
            len(vector) == expected_dimension for vector in all_vectors
        )
        scores = [cosine_similarity(query_vector, vector) for vector in passage_vectors]
        top_index = max(range(len(scores)), key=scores.__getitem__)
        results.append(
            {
                "query": case.query,
                "passed": top_index == 0,
                "topPassage": passages[top_index],
                "scores": [round(score, 6) for score in scores],
            }
        )

    dimensions_match = provider.dimension == expected_dimension and vector_dimensions_match
    passed = (
        dimensions_match
        and vectors_normalized
        and all(result["passed"] for result in results)
    )
    return {
        "model": model_name,
        "dimension": provider.dimension,
        "expectedDimension": expected_dimension,
        "dimensionsMatch": dimensions_match,
        "vectorsNormalized": vectors_normalized,
        "total": len(results),
        "passed": sum(result["passed"] for result in results),
        "success": passed,
        "cases": results,
    }


def main() -> None:
    report = asyncio.run(evaluate())
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["success"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
