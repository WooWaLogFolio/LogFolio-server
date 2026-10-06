import pytest

from logfolio_ai.evaluation.embedding_runner import cosine_similarity, load_retrieval_cases


def test_embedding_evaluation_cases_reference_known_chunks() -> None:
    _, _, cases = load_retrieval_cases()

    assert cases
    assert all(
        set(case.expected_chunk_ids).issubset(
            {candidate.chunk_id for candidate in case.candidates}
        )
        for case in cases
    )


def test_cosine_similarity_compares_vector_direction() -> None:
    assert cosine_similarity([1.0, 0.0], [2.0, 0.0]) == pytest.approx(1.0)
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)
    assert cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(-1.0)
