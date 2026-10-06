from logfolio_ai.evaluation.embedding_runner import (
    evaluate_retrieved_chunks,
    load_retrieval_cases,
)


def test_retrieval_dataset_covers_core_retrieval_behaviors() -> None:
    name, top_k, cases = load_retrieval_cases()

    assert name == "retrieval_core_v1"
    assert top_k == 3
    assert {case.category for case in cases} == {
        "NEW_SOURCE", "USER_CONTRIBUTION", "DECISION_REASON",
        "EXISTING_EXPERIENCE", "INDEX_REUSE",
    }


def test_retrieval_metrics_measure_recall_and_noise() -> None:
    _, _, cases = load_retrieval_cases()
    result = evaluate_retrieved_chunks(cases[0], ["auth-fix", "interview"])

    assert result.recall_at_k == 1
    assert result.irrelevant_chunk_ratio == 0.5
    assert result.cross_project_count == 0
    assert result.first_relevant_rank == 1
    assert result.reciprocal_rank == 1
    assert result.passed is True


def test_retrieval_metrics_reject_cross_project_leakage() -> None:
    _, _, cases = load_retrieval_cases()
    result = evaluate_retrieved_chunks(cases[0], ["auth-fix", "other-project"])

    assert result.cross_project_count == 1
    assert result.passed is False


def test_retrieval_metrics_fail_when_gold_evidence_is_missing() -> None:
    _, _, cases = load_retrieval_cases()
    result = evaluate_retrieved_chunks(cases[0], ["interview"])

    assert result.recall_at_k == 0
    assert result.first_relevant_rank is None
    assert result.reciprocal_rank == 0
    assert result.passed is False
