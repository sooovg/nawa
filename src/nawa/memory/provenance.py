"""Provenance and confidence for every memory item (ROADMAP P7-05, ADR-0009).

Every item records where it came from (source type and reference), who wrote it, when (logical tick), the evidence it
rests on and, for consolidated items, which items it was derived from. Until OD-12 (and OD-03 for documents) every
source reference must be synthetic: it must start with ``synthetic:``. A real source is refused, not stored.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum

SYNTHETIC_PREFIX = "synthetic:"
_REF = re.compile(r"^synthetic:[a-z0-9_\-./#]+$")


class SourceType(str, Enum):
    USER_STATED = "user_stated"            # a synthetic user said it in a synthetic dialogue
    SYSTEM_OBSERVED = "system_observed"    # observed by the system during a synthetic session
    SENSOR = "sensor"                      # a synthetic sensory input
    TOOL_OUTPUT = "tool_output"            # output of a NAWA tool (P6-02) on synthetic input
    SYNTHETIC_DOCUMENT = "synthetic_document"
    TASK_EXECUTION = "task_execution"
    CONSOLIDATION = "consolidation"        # derived by a consolidation rule from other items


class ProvenanceError(ValueError):
    pass


@dataclass(frozen=True)
class Provenance:
    source_type: SourceType
    source_ref: str
    author: str
    recorded_at: int
    evidence_ref: str | None = None
    derived_from: tuple[str, ...] = ()

    def to_record(self) -> dict:
        return {"source_type": self.source_type.value, "source_ref": self.source_ref, "author": self.author,
                "recorded_at": self.recorded_at, "evidence_ref": self.evidence_ref,
                "derived_from": list(self.derived_from)}

    @classmethod
    def from_record(cls, r: dict) -> "Provenance":
        return cls(SourceType(r["source_type"]), r["source_ref"], r["author"], int(r["recorded_at"]),
                   r["evidence_ref"], tuple(r["derived_from"]))


def problems(p: object) -> list[str]:
    """Reasons a provenance record is unacceptable; empty when it is valid."""
    if not isinstance(p, Provenance):
        return ["provenance_missing"]
    out = []
    if not isinstance(p.source_type, SourceType):
        out.append("source_type_invalid")
    if not isinstance(p.source_ref, str) or not _REF.match(p.source_ref):
        out.append("source_ref_not_synthetic")
    if not isinstance(p.author, str) or not p.author.strip():
        out.append("author_missing")
    if not isinstance(p.recorded_at, int) or isinstance(p.recorded_at, bool) or p.recorded_at < 0:
        out.append("recorded_at_invalid")
    if p.evidence_ref is not None and not _REF.match(str(p.evidence_ref)):
        out.append("evidence_ref_not_synthetic")
    if p.source_type is SourceType.CONSOLIDATION and not p.derived_from:
        out.append("consolidation_without_sources")
    if p.source_type is not SourceType.CONSOLIDATION and p.derived_from:
        out.append("derived_from_without_consolidation")
    return out


def validate(p: object) -> Provenance:
    errs = problems(p)
    if errs:
        raise ProvenanceError(",".join(errs))
    return p  # type: ignore[return-value]


def check_confidence(value: object) -> float:
    """Confidence is a finite number in [0, 1]. Booleans and strings are refused."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) \
            or not 0.0 <= float(value) <= 1.0:
        raise ProvenanceError("confidence_out_of_range")
    return round(float(value), 6)


def combine_confidence(values: Iterable[float]) -> float:
    """Confidence of an item derived from several items: the minimum (conservative, order-independent)."""
    vals = [check_confidence(v) for v in values]
    if not vals:
        raise ProvenanceError("no_sources")
    return min(vals)


def derived(source_ids: Iterable[str], author: str, recorded_at: int, rule: str) -> Provenance:
    ids = tuple(sorted(set(source_ids)))
    return Provenance(SourceType.CONSOLIDATION, f"synthetic:consolidation/{rule}", author, recorded_at, None, ids)
