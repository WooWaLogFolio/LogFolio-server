from pathlib import Path
from typing import Iterable, List, Optional

from logfolio_ai.evaluation.models import EvaluationCase, EvaluationReport


def load_cases(path: Optional[Path] = None) -> List[EvaluationCase]:
    from logfolio_ai.evaluation.runner import DEFAULT_DATASET, load_cases as load

    return load(path or DEFAULT_DATASET)


def evaluate_cases(cases: Iterable[EvaluationCase]) -> EvaluationReport:
    from logfolio_ai.evaluation.runner import evaluate_cases as evaluate

    return evaluate(cases)


__all__ = ["evaluate_cases", "load_cases"]
