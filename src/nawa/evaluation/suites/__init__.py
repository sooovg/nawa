"""Evaluation suites (P1-02). Each module exposes generate(rng, n, split), score(item, output), oracle(item)."""

from __future__ import annotations

import importlib
from types import ModuleType

from nawa.evaluation.schema import SUITES


def get(name: str) -> ModuleType:
    if name not in SUITES:
        raise KeyError(name)
    return importlib.import_module(f"nawa.evaluation.suites.{name}")


def result(correct: bool, *, abstained: bool = False, failure: str | None = None, **extra) -> dict:
    """Standard per-item score. hallucinated = answered (did not abstain) and wrong."""
    hallucinated = (not correct) and (not abstained) and extra.pop("hallucination_applicable", True)
    return {"correct": bool(correct), "abstained": bool(abstained), "hallucinated": bool(hallucinated),
            "failure": None if correct else failure, **extra}


ABSTENTION_FAILURES = ("FT-13", "FT-14")


def attribute_abstention(score: dict, output: str, answerable: bool | None) -> dict:
    """P1-08: fix the failure category of a wrong answer that is an abstention on an answerable item.

    Suite scorers assign their own default category (e.g. FT-03 for reasoning_math, none for code). When the
    model abstained on an item that has enough evidence, the failure is over-abstention (FT-13), not the suite
    default. Only failure attribution changes: `correct` is untouched. `abstained`/`hallucinated` are set as the
    abstention suites already do. The original category is kept in `failure_suite_default` for traceability.
    """
    from nawa.evaluation.normalize import is_abstention
    if score["correct"] or answerable is False or score.get("failure") in ABSTENTION_FAILURES:
        return score
    if not is_abstention(output):
        return score
    out = dict(score)
    out["failure_suite_default"] = score.get("failure")
    out["failure"] = "FT-13"
    out["abstained"] = True
    out["hallucinated"] = False
    return out
