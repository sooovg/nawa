"""Self-consistency: how much do candidates agree? (ROADMAP P6-03, ADR-0008).

:func:`agreement` groups candidates by their normalised text (``nawa.evaluation.normalize.normalize``, reused) and
puts every abstention (``normalize.is_abstention``, reused) in one ``ABSTAIN`` group. It reports each group's exact share
(:class:`fractions.Fraction`) and the **plurality** answer: the group strictly larger than every other one, or ``None``
on a tie.

What it is not:

* **Not verification.** Agreement is never a P6-08 state, never makes a claim ``SUPPORTED``, and is marked
  ``is_verification: False``. Several candidates can agree on a wrong answer (tested with :class:`WrongStub`); the
  verifier (P6-04) and the decision (P6-05) still decide.
* **Not calibrated.** The share is a count, not a probability (``calibrated: False``); calibration is P6-05a.
* **No threshold.** Nothing here accepts or rejects; there is no numeric cut-off to tune (ADR-0008 D2).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from fractions import Fraction

from nawa.evaluation.normalize import is_abstention, normalize
from nawa.reasoning.generator import Candidate

ABSTAIN_KEY = "\u0000ABSTAIN"


def answer_key(text: str) -> str:
    return ABSTAIN_KEY if is_abstention(text) else normalize(text)


@dataclass(frozen=True)
class Agreement:
    n: int
    groups: tuple[tuple[str, tuple[int, ...]], ...]     # (key, candidate indexes), largest first, then by key
    plurality: str | None                                # key of the strictly largest group, None on a tie or n == 0
    representative: str | None                           # original text of the first candidate in that group

    calibrated: bool = False
    is_verification: bool = False

    def __post_init__(self) -> None:
        if self.calibrated is not False or self.is_verification is not False:
            raise ValueError("agreement is never calibrated and never verification (P6-05a, P6-04)")

    def share(self, key: str) -> Fraction:
        for k, idx in self.groups:
            if k == key:
                return Fraction(len(idx), self.n)
        return Fraction(0)

    @property
    def plurality_share(self) -> Fraction | None:
        return None if self.plurality is None else self.share(self.plurality)

    @property
    def abstained(self) -> bool:
        return self.plurality == ABSTAIN_KEY

    def to_dict(self) -> dict:
        return {"n": self.n,
                "groups": [{"key": "ABSTAIN" if k == ABSTAIN_KEY else k, "indexes": list(i),
                            "share": str(Fraction(len(i), self.n))} for k, i in self.groups],
                "plurality": "ABSTAIN" if self.plurality == ABSTAIN_KEY else self.plurality,
                "plurality_share": None if self.plurality_share is None else str(self.plurality_share),
                "representative": self.representative, "calibrated": False, "is_verification": False}


def agreement(candidates: Iterable[Candidate]) -> Agreement:
    cands = list(candidates)
    for c in cands:
        if not isinstance(c, Candidate):
            raise ValueError(f"not a Candidate: {c!r}")
    if len({c.index for c in cands}) != len(cands):
        raise ValueError("candidate indexes must be unique")
    by: dict[str, list[int]] = {}
    first: dict[str, str] = {}
    for c in sorted(cands, key=lambda c: c.index):
        k = answer_key(c.text)
        by.setdefault(k, []).append(c.index)
        first.setdefault(k, c.text)
    groups = tuple(sorted(((k, tuple(v)) for k, v in by.items()), key=lambda g: (-len(g[1]), g[0])))
    top = None
    if groups and (len(groups) == 1 or len(groups[0][1]) > len(groups[1][1])):
        top = groups[0][0]
    return Agreement(len(cands), groups, top, None if top is None else first[top])
