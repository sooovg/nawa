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
