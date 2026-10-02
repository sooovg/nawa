"""Provided evidence for claim checking (ROADMAP P6-04, ADR-0008).

Checkers read only the evidence passed to them: no retrieval, no network, no model, and no built-in world knowledge.
Evidence is a passage of text, optionally with structured fact records ``(subject, attribute, value, unit)``. It is
"structured context" in the ROADMAP sense. Open-text entailment is P6-04a.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from fractions import Fraction

from nawa.evaluation.normalize import normalize, normalize_digits

COMPUTED_PREFIXES = ("calc:", "exec:")     # ids of computations made by a checker, never of provided evidence
_NUMBER = re.compile(r"[+-]?(\d+(\.\d*)?|\.\d+)(/\d+)?\Z")


def norm_text(value: str) -> str:
    """Arabic-aware normalisation, reused from the evaluation code (not copied)."""
    return normalize(value)


def norm_value(value: object) -> object:
    """A number (Arabic digits, ``٫``, thousands separators and fractions allowed) becomes an exact Fraction; anything
    else becomes normalised text. ``"٣٫٥"``, ``"3.50"`` and ``"7/2"`` are the same value."""
    if isinstance(value, bool):
        return norm_text(str(value))
    if isinstance(value, int):
        return Fraction(value)
    if isinstance(value, Fraction):
        return value
    if isinstance(value, float):
        raise ValueError("float values are not accepted; pass a string or an int so the value stays exact")
    if not isinstance(value, str):
        raise ValueError(f"unsupported value type {type(value).__name__}")
    s = normalize_digits(value).strip().replace("٫", ".").replace("٬", ",").replace("−", "-")
    s = re.sub(r"(?<=\d),(?=\d{3}\b)", "", s)
    if _NUMBER.match(s):
        try:
            return Fraction(s)
        except (ValueError, ZeroDivisionError):
            pass
    return norm_text(value)


def norm_unit(unit: str | None) -> str | None:
    return None if unit is None or not unit.strip() else norm_text(unit)


@dataclass(frozen=True)
class FactRecord:
    subject: str
    attribute: str
    value: str | int
    unit: str | None = None

    def __post_init__(self) -> None:
        for name in ("subject", "attribute"):
            v = getattr(self, name)
            if not isinstance(v, str) or not norm_text(v):
                raise ValueError(f"{name} must be a non-empty string")
        norm_value(self.value)

    @property
    def key(self) -> tuple[str, str]:
        return norm_text(self.subject), norm_text(self.attribute)


@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    text: str = ""
    records: tuple[FactRecord, ...] = field(default_factory=tuple)
    source: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.evidence_id, str) or not self.evidence_id.strip():
            raise ValueError("evidence_id must be a non-empty string")
        if self.evidence_id.startswith(COMPUTED_PREFIXES):
            raise ValueError(f"evidence ids may not start with {COMPUTED_PREFIXES} (reserved for computations)")
        if not isinstance(self.text, str):
            raise ValueError("text must be a string")
        object.__setattr__(self, "records", tuple(self.records))
        for r in self.records:
            if not isinstance(r, FactRecord):
                raise ValueError("records must be FactRecord objects")


def evidence_map(evidence: Iterable[Evidence] | Mapping[str, Evidence]) -> dict[str, Evidence]:
    items = list(evidence.values()) if isinstance(evidence, Mapping) else list(evidence)
    out: dict[str, Evidence] = {}
    for e in items:
        if not isinstance(e, Evidence):
            raise ValueError(f"not Evidence: {e!r}")
        if e.evidence_id in out:
            raise ValueError(f"duplicate evidence_id {e.evidence_id!r}")
        out[e.evidence_id] = e
    return out


def evidence_from_files(inspector, paths: Iterable[str]) -> list[Evidence]:
    """Text evidence from files read with the read-only :class:`nawa.tools.files.FileInspector` (P6-02).

    The id pins the content: ``file:<path>@<sha256[:12]>``. A truncated file is refused, so that a check never runs on
    part of a document without saying so."""
    out = []
    for p in paths:
        t = inspector.read_text(p)
        if t.truncated:
            raise ValueError(f"{p!r} is larger than the inspector limit; evidence must be read whole")
        out.append(Evidence(f"file:{t.path}@{t.sha256[:12]}", t.text, source=t.path))
    return out


def sha12(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
