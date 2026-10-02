"""Contradiction, consensus and uncertainty over provided evidence (ROADMAP P6-04, ADR-0008).

* :func:`evidence_conflicts`: two or more records with the same (subject, attribute, unit) and different values.
* :func:`claim_conflicts`: two fact claims in one answer that give the same (subject, attribute, unit) different values.
  The answer contradicts itself, whatever the evidence says.
* :func:`consensus`: which sources give which value. A value is adopted only when every source that speaks agrees
  (``unanimous``). There is no majority vote, consistent with P6-08 rule C3. Weighting sources by quality or recency
  needs P6-01 metadata.
* :func:`uncertainty`: counts per state and the fraction supported, as an exact :class:`~fractions.Fraction`. It is
  a description of this verdict, **not** a calibrated probability: calibration is P6-05a (BLOCKED until G5).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from fractions import Fraction

from nawa.verification.claims import FactClaim
from nawa.verification.evidence import Evidence, norm_text, norm_unit, norm_value
from nawa.verification.states import AnswerVerdict, VerificationState


def _vkey(v: object) -> str:
    return f"n:{v}" if isinstance(v, Fraction) else f"t:{v}"


@dataclass(frozen=True)
class Conflict:
    subject: str
    attribute: str
    unit: str | None
    values: tuple[tuple[str, tuple[str, ...]], ...]    # (normalised value, sorted ids), sorted by value

    def to_dict(self) -> dict:
        return {"subject": self.subject, "attribute": self.attribute, "unit": self.unit,
                "values": [[v, list(ids)] for v, ids in self.values]}


def _group(items: Iterable[tuple[tuple[str, str, str | None], object, str]]) -> list[Conflict]:
    by: dict[tuple, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for key, value, owner in items:
        by[key][_vkey(value)].add(owner)
    out = []
    for key in sorted(by, key=lambda k: (k[0], k[1], k[2] or "")):
        vals = by[key]
        if len(vals) > 1:
            out.append(Conflict(key[0], key[1], key[2], tuple((v, tuple(sorted(vals[v]))) for v in sorted(vals))))
    return out


def evidence_conflicts(evidence: Mapping[str, Evidence]) -> list[Conflict]:
    return _group(((*r.key, norm_unit(r.unit)), norm_value(r.value), e.evidence_id)
                  for e in evidence.values() for r in e.records)


def claim_conflicts(claims: Iterable[object]) -> list[Conflict]:
    return _group(((norm_text(c.subject), norm_text(c.attribute), norm_unit(c.unit)), norm_value(c.value), c.claim_id)
                  for c in claims if isinstance(c, FactClaim))


@dataclass(frozen=True)
class Consensus:
    subject: str
    attribute: str
    values: tuple[tuple[str, tuple[str, ...]], ...]
    unanimous: bool
    value: str | None          # the agreed value, only when unanimous

    @property
    def n_sources(self) -> int:
        return len({i for _, ids in self.values for i in ids})


def consensus(evidence: Mapping[str, Evidence], subject: str, attribute: str, unit: str | None = None) -> Consensus:
    key = (norm_text(subject), norm_text(attribute))
    vals: dict[str, set[str]] = defaultdict(set)
    for e in evidence.values():
        for r in e.records:
            if r.key == key and norm_unit(r.unit) == norm_unit(unit):
                vals[_vkey(norm_value(r.value))].add(e.evidence_id)
    values = tuple((v, tuple(sorted(vals[v]))) for v in sorted(vals))
    unanimous = len(values) == 1
    return Consensus(key[0], key[1], values, unanimous, values[0][0] if unanimous else None)


def uncertainty(verdict: AnswerVerdict) -> dict:
    counts = {s.value: 0 for s in VerificationState if s is not VerificationState.PARTIALLY_SUPPORTED}
    for c in verdict.claims:
        counts[c.state.value] += 1
    n = len(verdict.claims)
    sup = counts[VerificationState.SUPPORTED.value]
    return {"n_claims": n, "counts": counts,
            "supported_fraction": None if n == 0 else Fraction(sup, n),
            "undecided_checkers": sorted({u for c in verdict.claims for u in c.undecided_checkers}),
            "calibrated": False}
