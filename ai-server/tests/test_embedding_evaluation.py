import pytest

from logfolio_ai.evaluation.embedding_runner import CASES, cosine_similarity


def test_embedding_evaluation_cases_keep_expected_passage_first() -> None:
    assert CASES
    assert all(case.expected_passage not in case.distractors for case in CASES)


def test_cosine_similarity_compares_vector_direction() -> None:
    assert cosine_similarity([1.0, 0.0], [2.0, 0.0]) == pytest.approx(1.0)
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)
    assert cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(-1.0)
