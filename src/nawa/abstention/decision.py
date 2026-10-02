"""Abstention decision function (ROADMAP P6-05, ADR-0008).

The function maps a P6-04 verification :class:`~nawa.verification.verifier.Report`, plus a few caller facts, to
exactly one of five actions:

* ``ANSWER_WITH_CITATIONS``: answer, citing the supporting evidence for every claim.
* ``SEARCH``: look for more evidence.
* ``RUN_TOOL``: run a tool that can check a claim no checker has checked yet.
* ``ASK_CLARIFICATION``: the question itself is ambiguous.
* ``ABSTAIN``.

Rules, applied in order (first match wins). There are no numeric thresholds: the rules read only the P6-08 states and
the report's flags, so nothing is tuned on synthetic data (ADR-0008: thresholds are P6-05a, on NAWA, on ``calib``).

====  ==========================================================  ===================  ===============================
rule  condition                                                   action               reason
====  ==========================================================  ===================  ===============================
D1    the caller marks the question ambiguous                     ASK_CLARIFICATION    ``ambiguous_question``
D2    the answer contradicts itself (report.claim_conflicts)      ABSTAIN              ``self_contradiction``
D3    verdict CONTRADICTED                                        ABSTAIN              ``contradicted_by_evidence``
D4    some claim is unchecked, a granted tool can check its kind  RUN_TOOL             ``tool_can_check``
      and the tool budget is not used up
D5    verdict SUPPORTED (and strict_ok)                           ANSWER_WITH_CITATIONS ``all_claims_supported``
D6    lenient mode, verdict PARTIALLY_SUPPORTED                   ANSWER_WITH_CITATIONS ``partial_with_disclosure``
D7    search allowed and the search budget not used up            SEARCH               ``need_more_evidence``
D8    otherwise                                                   ABSTAIN              ``insufficient_evidence`` /
                                                                                       ``uncertain_evidence`` /
                                                                                       ``not_fully_supported``
====  ==========================================================  ===================  ===============================

Invariants (tested exhaustively):
- **No contradicted or self-contradicting answer.** An answer never contains a CONTRADICTED claim and never
  contradicts itself.
- **Strict mode answers only fully supported answers.**
- **Lenient mode discloses.** It may answer a partially supported answer, but every claim that is not SUPPORTED is
  listed in ``disclosed`` and none is dropped silently (G6). Its supported claims carry their citations.
- **No search without permission.** ``SEARCH`` is returned only when the caller allows it. The default is ``False``:
  P6-02a (external search) is BLOCKED until OD-11, and local retrieval is P6-01. ``SEARCH`` is a decision only; this
  module performs nothing.
- **Uncertainty is marked uncalibrated.** Every decision carries the P6-04 uncertainty summary (counts per state and
  the supported fraction) with ``calibrated: False``, and ``performed: False``. The summary is a description, not a
  probability, and no decision rule reads it as one.
- **Abstention text is recognised.** The abstention message is recognised by the evaluation's own
  ``normalize.is_abstention`` (reused, not changed), so an abstention is scored as one.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import Enum

from nawa.verification.claims import ArithmeticClaim, CodeClaim, FactClaim, TextClaim
from nawa.verification.consistency import uncertainty
from nawa.verification.states import VerificationState
from nawa.verification.verifier import Report

S = VerificationState


class Action(str, Enum):
    ANSWER_WITH_CITATIONS = "ANSWER_WITH_CITATIONS"
    SEARCH = "SEARCH"
    RUN_TOOL = "RUN_TOOL"
    ASK_CLARIFICATION = "ASK_CLARIFICATION"
    ABSTAIN = "ABSTAIN"


class Mode(str, Enum):
    STRICT = "STRICT"
    LENIENT = "LENIENT"


# Which tool permission can check which claim kind (P6-02 permissions; the P6-04 checkers use these tools).
TOOL_FOR_KIND = {ArithmeticClaim: "CALCULATE", CodeClaim: "EXECUTE_CODE"}
KNOWN_KINDS = (ArithmeticClaim, CodeClaim, FactClaim, TextClaim)
ABSTAIN_TEXT = {"ar": "لا يمكنني تحديد الإجابة من الأدلة المتاحة.",
                "en": "I don't know: this cannot be determined from the provided evidence."}


@dataclass(frozen=True)
class Context:
    """Caller facts the report does not hold. Every default is the conservative choice."""

    mode: Mode = Mode.STRICT
    ambiguous: bool = False
    search_allowed: bool = False           # P6-02a BLOCKED (OD-11); P6-01 local retrieval not built yet
    searches_left: int = 0
    granted_tools: frozenset[str] = frozenset()
    tool_calls_left: int = 0
    claim_kinds: dict[str, type] = field(default_factory=dict)   # claim_id -> claim class, for D4

    def __post_init__(self) -> None:
        if not isinstance(self.mode, Mode):
            raise ValueError("mode must be a Mode")
        for name in ("searches_left", "tool_calls_left"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int) or v < 0:
                raise ValueError(f"{name} must be a non-negative int")
        for name in ("ambiguous", "search_allowed"):
            if not isinstance(getattr(self, name), bool):
                raise ValueError(f"{name} must be a bool")
        object.__setattr__(self, "granted_tools", frozenset(self.granted_tools))
        unknown = sorted(t for t in self.granted_tools if t not in TOOL_FOR_KIND.values())
        if unknown:
            raise ValueError(f"unknown tool permissions {unknown}; NETWORK is never a tool here (OD-11)")


@dataclass(frozen=True)
class Decision:
    action: Action
    rule: str
    reason: str
    citations: tuple[tuple[str, tuple[str, ...]], ...] = ()   # (claim_id, supporting evidence ids), answered claims
    disclosed: tuple[str, ...] = ()                            # claims answered without full support (lenient only)
    targets: tuple[str, ...] = ()                              # claims to search for / to check with a tool
    uncertainty: dict = field(default_factory=dict)            # P6-04 summary; always ``calibrated: False``

    performed: bool = False    # this module records a decision; it never searches, calls an API or runs a tool

    def __post_init__(self) -> None:
        if self.performed is not False:
            raise ValueError("decide() only records a decision; nothing is performed here")
        if self.uncertainty and self.uncertainty.get("calibrated") is not False:
            raise ValueError("uncertainty here is never calibrated (calibration is P6-05a)")

    def to_dict(self) -> dict:
        u = dict(self.uncertainty)
        if u.get("supported_fraction") is not None:
            u["supported_fraction"] = str(u["supported_fraction"])
        return {"action": self.action.value, "rule": self.rule, "reason": self.reason,
                "citations": [[c, list(e)] for c, e in self.citations], "disclosed": list(self.disclosed),
                "targets": list(self.targets), "uncertainty": u, "calibrated": False, "performed": False}


def claim_kinds(claims: Iterable[object]) -> dict[str, type]:
    """Helper: the ``claim_kinds`` map of a claim list."""
    out = {}
    for c in claims:
        if not isinstance(c, KNOWN_KINDS):
            raise ValueError(f"not a claim: {c!r}")
        out[c.claim_id] = type(c)
    return out


def decide(report: Report, ctx: Context | None = None) -> Decision:
    d = _decide(report, ctx)
    return Decision(d.action, d.rule, d.reason, d.citations, d.disclosed, d.targets, uncertainty(report.verdict))


def _decide(report: Report, ctx: Context | None) -> Decision:
    if not isinstance(report, Report):
        raise ValueError("report must be a P6-04 Report")
    ctx = ctx or Context()
    v = report.verdict
    claims = v.claims
    flagged = report.flagged

    if ctx.ambiguous:
        return Decision(Action.ASK_CLARIFICATION, "D1", "ambiguous_question")
    if report.claim_conflicts:
        return Decision(Action.ABSTAIN, "D2", "self_contradiction", targets=flagged)
    if v.state is S.CONTRADICTED:
        bad = tuple(c.claim_id for c in claims if c.state is S.CONTRADICTED)
        return Decision(Action.ABSTAIN, "D3", "contradicted_by_evidence", targets=bad)

    tool_targets = tuple(cid for cid in report.unchecked
                         if TOOL_FOR_KIND.get(ctx.claim_kinds.get(cid)) in ctx.granted_tools)
    if tool_targets and ctx.tool_calls_left > 0:
        return Decision(Action.RUN_TOOL, "D4", "tool_can_check", targets=tool_targets)

    supported = tuple((c.claim_id, c.supporting) for c in claims if c.state is S.SUPPORTED)
    if v.state is S.SUPPORTED and report.strict_ok:
        return Decision(Action.ANSWER_WITH_CITATIONS, "D5", "all_claims_supported", citations=supported)
    if ctx.mode is Mode.LENIENT and v.state is S.PARTIALLY_SUPPORTED:
        return Decision(Action.ANSWER_WITH_CITATIONS, "D6", "partial_with_disclosure", citations=supported,
                        disclosed=flagged)
    if ctx.search_allowed and ctx.searches_left > 0:
        return Decision(Action.SEARCH, "D7", "need_more_evidence", targets=flagged)
    reason = {S.INSUFFICIENT_EVIDENCE: "insufficient_evidence", S.UNCERTAIN: "uncertain_evidence"}.get(
        v.state, "not_fully_supported")
    return Decision(Action.ABSTAIN, "D8", reason, targets=flagged)


def abstention_text(lang: str = "ar") -> str:
    if lang not in ABSTAIN_TEXT:
        raise ValueError(f"lang must be one of {sorted(ABSTAIN_TEXT)}")
    return ABSTAIN_TEXT[lang]
