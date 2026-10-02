"""Claim verifier: claims + provided evidence → checker findings → P6-08 verdict (ROADMAP P6-04, ADR-0008).

:func:`check` runs every checker that handles a claim's kind:
- each checker runs separately, on a read-only view of the evidence;
- the findings are collected, sorted and passed to :func:`nawa.verification.states.verify` (the P6-08 rules).

The report also lists:
- evidence conflicts and the answer's own conflicting claims;
- citations to unknown evidence;
- claims that no checker handles. They stay ``INSUFFICIENT_EVIDENCE`` (rule C1) and are flagged.

Correctness only: this proves that the checks are implemented as written. It says nothing about NAWA's hallucination
rate or answer quality (P6-04a, P6-09).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType

from nawa.verification.checkers import default_checkers
from nawa.verification.claims import CLAIM_TYPES
from nawa.verification.consistency import Conflict, claim_conflicts, evidence_conflicts, uncertainty
from nawa.verification.evidence import COMPUTED_PREFIXES, Evidence, evidence_map
from nawa.verification.states import AnswerVerdict, Finding, flagged_claims, passes_strict, verify


@dataclass(frozen=True)
class Report:
    verdict: AnswerVerdict
    findings: tuple[Finding, ...]
    evidence_conflicts: tuple[Conflict, ...]
    claim_conflicts: tuple[Conflict, ...]
    unknown_citations: tuple[tuple[str, str], ...]     # (claim_id, evidence_id)
    unchecked: tuple[str, ...]                          # claims no checker handles

    @property
    def strict_ok(self) -> bool:
        """G6 strict mode. A self-contradicting answer never passes, even if each claim found support."""
        return passes_strict(self.verdict) and not self.claim_conflicts

    @property
    def flagged(self) -> tuple[str, ...]:
        conflicted = {i for c in self.claim_conflicts for _, ids in c.values for i in ids}
        return tuple(sorted(set(flagged_claims(self.verdict)) | conflicted))

    def to_dict(self) -> dict:
        return {"verdict": self.verdict.to_dict(), "findings": [f.to_dict() for f in self.findings],
                "evidence_conflicts": [c.to_dict() for c in self.evidence_conflicts],
                "claim_conflicts": [c.to_dict() for c in self.claim_conflicts],
                "unknown_citations": [list(x) for x in self.unknown_citations], "unchecked": list(self.unchecked),
                "strict_ok": self.strict_ok, "flagged": list(self.flagged),
                "uncertainty": {**uncertainty(self.verdict),
                                "supported_fraction": str(uncertainty(self.verdict)["supported_fraction"])}}


def _key(f: Finding) -> tuple:
    return f.claim_id, f.checker, f.relation.value, f.evidence_id or "", f.detail


def check(claims: Iterable[object], evidence: Iterable[Evidence] | Mapping[str, Evidence] = (),
          checkers: Iterable[object] | None = None) -> Report:
    cl = list(claims)
    for c in cl:
        if not isinstance(c, CLAIM_TYPES):
            raise ValueError(f"not a claim: {c!r}")
    ev = MappingProxyType(evidence_map(evidence))
    cks = tuple(default_checkers() if checkers is None else checkers)
    names = [k.name for k in cks]
    if len(set(names)) != len(names):
        raise ValueError("checker names must be unique")
    findings: list[Finding] = []
    unchecked = []
    for c in cl:
        handlers = [k for k in cks if isinstance(c, k.kind)]
        if not handlers:
            unchecked.append(c.claim_id)
        for k in handlers:
            for f in k.check(c, ev):
                if not isinstance(f, Finding) or f.claim_id != c.claim_id or f.checker != k.name:
                    raise ValueError(f"checker {k.name!r} returned an invalid finding {f!r}")
                if f.evidence_id is not None and not f.evidence_id.startswith(COMPUTED_PREFIXES) \
                        and f.evidence_id not in ev:
                    raise ValueError(f"checker {k.name!r} cited evidence that was not provided: {f.evidence_id!r}")
                findings.append(f)
    findings.sort(key=_key)
    verdict = verify([c.claim_id for c in cl], findings)
    unknown = tuple(sorted({(c.claim_id, e) for c in cl for e in getattr(c, "citations", ()) if e not in ev}))
    return Report(verdict, tuple(findings), tuple(evidence_conflicts(ev)), tuple(claim_conflicts(cl)), unknown,
                  tuple(sorted(unchecked)))
