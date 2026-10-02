"""Risk–coverage computation for selective answering (ROADMAP P6-05, ADR-0008; G6: "risk and coverage are measured
with a risk–coverage curve").

Items are ``(score, correct)``: a confidence score, higher meaning more confident, and whether the answer was correct.
A threshold ``t`` answers every item with ``score >= t`` and abstains on the rest. Items with equal scores are
always answered or abstained on together. For each threshold:

* ``coverage = answered / n``;
* ``risk = wrong answered / answered``. Risk is undefined (``None``) when nothing is answered.

Both are exact :class:`~fractions.Fraction` values, computed from counts. The curve has one point per distinct score,
from the highest score down, plus the empty point (coverage 0). It is computed in O(n log n) and tested against a
brute-force O(n²) computation.

``aurc`` is the area under the risk–coverage step curve, ``Σ risk_k · (coverage_k − coverage_{k−1})`` over the
non-empty points. Lower is better. ``oracle_aurc`` is the same area for the best possible ordering of the same items.

This module measures; it adopts nothing. :func:`max_coverage_at_risk` reports which threshold *would* meet a risk
budget on the given items. Choosing an abstention threshold for NAWA is P6-05a (BLOCKED until G5, fitted on ``calib``
only), and no number here changes ``eval/targets.yaml``. The ``wilson`` interval is reused from
``nawa.evaluation.report``, not copied.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from fractions import Fraction

from nawa.evaluation.report import wilson


def _items(items: Iterable[tuple[object, bool]]) -> list[tuple[float | Fraction | int, bool]]:
    out = []
    for it in items:
        score, correct = it
        if isinstance(score, bool) or not isinstance(score, (int, float, Fraction)):
            raise ValueError(f"score must be a number, got {score!r}")
        if isinstance(score, float) and not math.isfinite(score):
            raise ValueError("score must be finite")
        if not isinstance(correct, bool):
            raise ValueError("correct must be a bool")
        out.append((score, correct))
    return out


@dataclass(frozen=True)
class Point:
    threshold: float | Fraction | int | None   # None: the empty point (abstain on everything)
    answered: int
    errors: int
    n: int

    @property
    def coverage(self) -> Fraction:
        return Fraction(self.answered, self.n) if self.n else Fraction(0)

    @property
    def risk(self) -> Fraction | None:
        return Fraction(self.errors, self.answered) if self.answered else None

    def risk_interval(self) -> list[float] | None:
        """95% Wilson interval of the risk (reused from the evaluation report)."""
        return wilson(self.errors, self.answered) if self.answered else None


def curve(items: Iterable[tuple[object, bool]]) -> list[Point]:
    its = _items(items)
    n = len(its)
    its.sort(key=lambda x: x[0], reverse=True)
    pts = [Point(None, 0, 0, n)]
    answered = errors = 0
    i = 0
    while i < n:
        s = its[i][0]
        while i < n and its[i][0] == s:
            answered += 1
            errors += 0 if its[i][1] else 1
            i += 1
        pts.append(Point(s, answered, errors, n))
    return pts


def aurc(items: Iterable[tuple[object, bool]]) -> Fraction | None:
    pts = curve(items)
    if len(pts) == 1:
        return None
    area = Fraction(0)
    for prev, p in zip(pts, pts[1:]):
        area += p.risk * (p.coverage - prev.coverage)
    return area


def oracle_aurc(items: Iterable[tuple[object, bool]]) -> Fraction | None:
    """AURC when every correct item scores above every wrong one, and each item has its own score."""
    its = _items(items)
    if not its:
        return None
    order = sorted((0 if c else 1 for _, c in its))
    return aurc([(len(order) - k, c == 0) for k, c in enumerate(order)])


def max_coverage_at_risk(items: Iterable[tuple[object, bool]], max_risk: Fraction | int) -> Point:
    """The point with the highest coverage whose risk is at most ``max_risk``, or the empty point. Evidence only:
    nothing is adopted."""
    if isinstance(max_risk, (bool, float)) or not isinstance(max_risk, (int, Fraction)) or not 0 <= max_risk <= 1:
        raise ValueError("max_risk must be an exact number (int or Fraction) in [0, 1]")
    best = None
    for p in curve(items):
        if p.risk is not None and p.risk <= max_risk and (best is None or p.coverage > best.coverage):
            best = p
    return best if best is not None else curve(items)[0]


def decision_point(decisions: Iterable[tuple[bool, bool]]) -> Point:
    """One risk–coverage point for a decision policy: ``(answered, correct)`` per item."""
    ds = list(decisions)
    for a, c in ds:
        if not isinstance(a, bool) or not isinstance(c, bool):
            raise ValueError("answered and correct must be bools")
    answered = sum(a for a, _ in ds)
    errors = sum(a and not c for a, c in ds)
    return Point(None, answered, errors, len(ds))
