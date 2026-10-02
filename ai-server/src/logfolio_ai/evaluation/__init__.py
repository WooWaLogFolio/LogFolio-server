from pathlib import Path
from typing import Iterable, List, Optional

from logfolio_ai.evaluation.models import EvaluationCase, EvaluationReport


def load_cases(path: Optional[Path] = None) -> List[EvaluationCase]:
    from logfolio_ai.evaluation.runner import DEFAULT_DATASET, load_cases as load

    return load(path or DEFAULT_DATASET)


def evaluate_cases(cases: Iterable[EvaluationCase]) -> EvaluationReport:
    from logfolio_ai.evaluation.runner import evaluate_cases as evaluate

    return evaluate(cases)


def load_product_cases(path=None, case_id=None):
    from logfolio_ai.evaluation.product_runner import (
        DEFAULT_DATASET,
        load_product_cases as load,
    )

    return load(path or DEFAULT_DATASET, case_id)


async def run_product_eval(*args, **kwargs):
    from logfolio_ai.evaluation.product_runner import run_product_eval as run

    return await run(*args, **kwargs)


__all__ = ["evaluate_cases", "load_cases", "load_product_cases", "run_product_eval"]
