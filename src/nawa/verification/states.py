"""The five verification states and their rules (ROADMAP P6-08, ADR-0008).

This module decides a state from findings that checkers produce. It does not check anything itself: the checkers
(calculator, sandbox, evidence match, contradiction detection) are P6-02 and P6-04. It proves nothing about NAWA's
answers, and makes no claim about hallucination; it only fixes what each state means, so that every later part uses
the same vocabulary, and nothing unsupported can be reported as ``SUPPORTED``.

Vocabulary
----------
* A **claim** is one atomic statement, with a unique ``claim_id``. Composite answers are lists of claims.
* A **finding** is one checker's judgement of one claim against one piece of evidence:
  ``ENTAILS`` (the evidence supports the claim), ``CONTRADICTS`` (it refutes the claim), ``NEUTRAL`` (it does not
  address the claim) or ``UNDECIDED`` (the checker ran but could not decide, e.g. a tool error or a timeout).
  ``ENTAILS`` and ``CONTRADICTS`` must name the evidence (``evidence_id``): support without a citation is not
  support.

Claim rules (first matching rule wins)
--------------------------------------
====  ==============================================  ======================  ========================
rule  findings for the claim                          state                   reason
====  ==============================================  ======================  ========================
C1    none                                            INSUFFICIENT_EVIDENCE   ``no_evidence``
C2    only NEUTRAL                                    INSUFFICIENT_EVIDENCE   ``no_relevant_evidence``
C3    at least one ENTAILS and one CONTRADICTS        UNCERTAIN               ``conflicting_evidence``
C4    CONTRADICTS (no ENTAILS)                        CONTRADICTED            ``contradicted``
C5    UNDECIDED (no CONTRADICTS)                      UNCERTAIN               ``checker_undecided``
C6    ENTAILS only (NEUTRAL allowed)                  SUPPORTED               ``supported``
====  ==============================================  ======================  ========================

C3 is conservative on purpose: conflicting evidence is not resolved by counting votes here (source quality and
recency are P6-01/P6-04 inputs). C5 is conservative too: a checker that failed blocks ``SUPPORTED`` even when another
checker entails the claim, so a tool failure can never be hidden. A claim is never ``PARTIALLY_SUPPORTED``: claims
are atomic, so partial support exists only for an answer.

Answer rules (first matching rule wins)
---------------------------------------
====  ==============================================  ======================  ========================
rule  claim states                                    state                   reason
====  ==============================================  ======================  ========================
A1    no claims                                       INSUFFICIENT_EVIDENCE   ``no_checkable_claims``
A2    any CONTRADICTED                                CONTRADICTED            ``contains_contradicted_claim``
A3    all SUPPORTED                                   SUPPORTED               ``all_claims_supported``
A4    some SUPPORTED                                  PARTIALLY_SUPPORTED     ``some_claims_unsupported``
A5    none SUPPORTED, any UNCERTAIN                   UNCERTAIN               ``no_claim_supported``
A6    none SUPPORTED, all INSUFFICIENT_EVIDENCE       INSUFFICIENT_EVIDENCE   ``no_claim_supported``
====  ==============================================  ======================  ========================

Strict mode (G6: "no unsupported claim passes silently in strict mode"): an answer passes strict mode only when its
state is ``SUPPORTED``. In every mode, every claim that is not ``SUPPORTED`` is listed by :func:`flagged_claims`, so
a caller can disclose, revise, retrieve or abstain (P6-05) but cannot drop it silently.

Properties (tested): results do not depend on the order of claims or findings; adding a ``CONTRADICTS`` finding
never makes a claim ``SUPPORTED``; adding an ``UNDECIDED`` finding never makes a claim ``SUPPORTED``; adding
``NEUTRAL`` findings never changes a state, except C1 → C2; verdicts round-trip through ``to_dict``/``from_dict``.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from enum import Enum


class VerificationState(str, Enum):
    SUPPORTED = "SUPPORTED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    UNCERTAIN = "UNCERTAIN"
    CONTRADICTED = "CONTRADICTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class Relation(str, Enum):
    ENTAILS = "ENTAILS"
    CONTRADICTS = "CONTRADICTS"
    NEUTRAL = "NEUTRAL"
    UNDECIDED = "UNDECIDED"


S = VerificationState
CLAIM_STATES = frozenset({S.SUPPORTED, S.UNCERTAIN, S.CONTRADICTED, S.INSUFFICIENT_EVIDENCE})
CLAIM_REASONS = ("no_evidence", "no_relevant_evidence", "conflicting_evidence", "contradicted", "checker_undecided",
                 "supported")
ANSWER_REASONS = ("no_checkable_claims", "contains_contradicted_claim", "all_claims_supported",
                  "some_claims_unsupported", "no_claim_supported")


def _nonempty_str(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


@dataclass(frozen=True)
class Finding:
    """One checker's judgement of one claim against one piece of evidence."""

    claim_id: str
    relation: Relation
    checker: str
    evidence_id: str | None = None
    detail: str = ""

    def __post_init__(self) -> None:
        _nonempty_str(self.claim_id, "claim_id")
        _nonempty_str(self.checker, "checker")
        if not isinstance(self.relation, Relation):
            raise ValueError(f"relation must be a Relation, got {self.relation!r}")
        if self.relation in (Relation.ENTAILS, Relation.CONTRADICTS):
            _nonempty_str(self.evidence_id, f"evidence_id (required for {self.relation.value})")
        elif self.evidence_id is not None:
            _nonempty_str(self.evidence_id, "evidence_id")
        if not isinstance(self.detail, str):
            raise ValueError("detail must be a string")

    def to_dict(self) -> dict:
        return {"claim_id": self.claim_id, "relation": self.relation.value, "checker": self.checker,
                "evidence_id": self.evidence_id, "detail": self.detail}

    @classmethod
    def from_dict(cls, d: dict) -> Finding:
        return cls(d["claim_id"], Relation(d["relation"]), d["checker"], d.get("evidence_id"), d.get("detail", ""))


@dataclass(frozen=True)
class ClaimVerdict:
    claim_id: str
    state: VerificationState
    reason: str
    supporting: tuple[str, ...] = ()        # evidence ids with ENTAILS, sorted, unique
    contradicting: tuple[str, ...] = ()     # evidence ids with CONTRADICTS, sorted, unique
    undecided_checkers: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {"claim_id": self.claim_id, "state": self.state.value, "reason": self.reason,
                "supporting": list(self.supporting), "contradicting": list(self.contradicting),
                "undecided_checkers": list(self.undecided_checkers)}

    @classmethod
    def from_dict(cls, d: dict) -> ClaimVerdict:
        return cls(d["claim_id"], S(d["state"]), d["reason"], tuple(d["supporting"]), tuple(d["contradicting"]),
                   tuple(d["undecided_checkers"]))


@dataclass(frozen=True)
class AnswerVerdict:
    state: VerificationState
    reason: str
    claims: tuple[ClaimVerdict, ...] = field(default_factory=tuple)   # sorted by claim_id

    def to_dict(self) -> dict:
        return {"state": self.state.value, "reason": self.reason, "claims": [c.to_dict() for c in self.claims]}

    @classmethod
    def from_dict(cls, d: dict) -> AnswerVerdict:
        return cls(S(d["state"]), d["reason"], tuple(ClaimVerdict.from_dict(c) for c in d["claims"]))


def claim_state(claim_id: str, findings: Iterable[Finding]) -> ClaimVerdict:
    """Apply rules C1..C6 to the findings of one claim."""
    _nonempty_str(claim_id, "claim_id")
    fs = list(findings)
    for f in fs:
        if not isinstance(f, Finding):
            raise ValueError(f"not a Finding: {f!r}")
        if f.claim_id != claim_id:
            raise ValueError(f"finding for claim {f.claim_id!r} passed to claim {claim_id!r}")
    rel = {f.relation for f in fs}
    sup = tuple(sorted({f.evidence_id for f in fs if f.relation is Relation.ENTAILS}))
    con = tuple(sorted({f.evidence_id for f in fs if f.relation is Relation.CONTRADICTS}))
    und = tuple(sorted({f.checker for f in fs if f.relation is Relation.UNDECIDED}))

    def verdict(state: VerificationState, reason: str) -> ClaimVerdict:
        return ClaimVerdict(claim_id, state, reason, sup, con, und)

    if not fs:
        return verdict(S.INSUFFICIENT_EVIDENCE, "no_evidence")                       # C1
    if rel == {Relation.NEUTRAL}:
        return verdict(S.INSUFFICIENT_EVIDENCE, "no_relevant_evidence")              # C2
    if Relation.ENTAILS in rel and Relation.CONTRADICTS in rel:
        return verdict(S.UNCERTAIN, "conflicting_evidence")                          # C3
    if Relation.CONTRADICTS in rel:
        return verdict(S.CONTRADICTED, "contradicted")                               # C4
    if Relation.UNDECIDED in rel:
        return verdict(S.UNCERTAIN, "checker_undecided")                             # C5
    return verdict(S.SUPPORTED, "supported")                                         # C6


def answer_state(claims: Sequence[ClaimVerdict]) -> tuple[VerificationState, str]:
    """Apply rules A1..A6 to the claim verdicts of one answer."""
    states = [c.state for c in claims]
    for st in states:
        if st not in CLAIM_STATES:
            raise ValueError(f"{st!r} is not a claim state (PARTIALLY_SUPPORTED exists only for answers)")
    if not states:
        return S.INSUFFICIENT_EVIDENCE, "no_checkable_claims"                      # A1
    if S.CONTRADICTED in states:
        return S.CONTRADICTED, "contains_contradicted_claim"                       # A2
    if all(st is S.SUPPORTED for st in states):
        return S.SUPPORTED, "all_claims_supported"                                 # A3
    if S.SUPPORTED in states:
        return S.PARTIALLY_SUPPORTED, "some_claims_unsupported"                    # A4
    if S.UNCERTAIN in states:
        return S.UNCERTAIN, "no_claim_supported"                                   # A5
    return S.INSUFFICIENT_EVIDENCE, "no_claim_supported"                           # A6


def verify(claim_ids: Iterable[str], findings: Iterable[Finding]) -> AnswerVerdict:
    """Group findings by claim, apply the claim rules, then the answer rules."""
    ids = list(claim_ids)
    for cid in ids:
        _nonempty_str(cid, "claim_id")
    if len(set(ids)) != len(ids):
        raise ValueError("claim ids must be unique")
    by_claim: dict[str, list[Finding]] = {cid: [] for cid in ids}
    for f in findings:
        if not isinstance(f, Finding):
            raise ValueError(f"not a Finding: {f!r}")
        if f.claim_id not in by_claim:
            raise ValueError(f"finding for unknown claim {f.claim_id!r}")
        by_claim[f.claim_id].append(f)
    verdicts = tuple(claim_state(cid, by_claim[cid]) for cid in sorted(ids))
    state, reason = answer_state(verdicts)
    return AnswerVerdict(state, reason, verdicts)


def passes_strict(verdict: AnswerVerdict) -> bool:
    """G6 strict mode: only a fully supported answer passes without a flag."""
    return verdict.state is S.SUPPORTED


def flagged_claims(verdict: AnswerVerdict) -> tuple[str, ...]:
    """Every claim that is not SUPPORTED, in every mode, so none can be dropped silently."""
    return tuple(c.claim_id for c in verdict.claims if c.state is not S.SUPPORTED)
