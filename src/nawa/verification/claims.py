"""Claims and rule-based claim extraction (ROADMAP P6-04, ADR-0008).

Claim kinds, all atomic:

* :class:`ArithmeticClaim`: ``expression = value``. Checked by the exact calculator (P6-02).
* :class:`CodeClaim`: running ``code`` prints ``expected_stdout``. Checked in the network-free sandbox (P6-02).
* :class:`FactClaim`: ``(subject, attribute) = value [unit]``. Checked against structured records in the evidence.
* :class:`TextClaim`: a sentence with citations ``[e1]``. Checked as an exact quote, after normalisation, in the
  cited evidence.

:func:`extract_claims` is a deterministic splitter for *structured* answers: one claim per sentence, citations in
square brackets, and ``a = b`` sentences become arithmetic claims. It does not understand free text. Open claim
extraction and learned entailment are P6-04a (BLOCKED until G5; any external model also waits for OD-10).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from nawa.evaluation.normalize import normalize_digits


def _id(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("claim_id must be a non-empty string")
    return value


def _cites(value: object) -> tuple[str, ...]:
    t = tuple(value)  # type: ignore[arg-type]
    if any(not isinstance(c, str) or not c.strip() for c in t):
        raise ValueError("citations must be non-empty strings")
    return tuple(dict.fromkeys(t))


@dataclass(frozen=True)
class ArithmeticClaim:
    claim_id: str
    expression: str
    value: str

    def __post_init__(self) -> None:
        _id(self.claim_id)
        if not isinstance(self.expression, str) or not isinstance(self.value, str):
            raise ValueError("expression and value must be strings")


@dataclass(frozen=True)
class CodeClaim:
    claim_id: str
    code: str
    expected_stdout: str

    def __post_init__(self) -> None:
        _id(self.claim_id)
        if not isinstance(self.code, str) or not isinstance(self.expected_stdout, str):
            raise ValueError("code and expected_stdout must be strings")


@dataclass(frozen=True)
class FactClaim:
    claim_id: str
    subject: str
    attribute: str
    value: str | int
    unit: str | None = None
    citations: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        _id(self.claim_id)
        for name in ("subject", "attribute"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name).strip():
                raise ValueError(f"{name} must be a non-empty string")
        object.__setattr__(self, "citations", _cites(self.citations))


@dataclass(frozen=True)
class TextClaim:
    claim_id: str
    text: str
    citations: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        _id(self.claim_id)
        if not isinstance(self.text, str) or not self.text.strip():
            raise ValueError("text must be a non-empty string")
        object.__setattr__(self, "citations", _cites(self.citations))


Claim = ArithmeticClaim | CodeClaim | FactClaim | TextClaim
CLAIM_TYPES = (ArithmeticClaim, CodeClaim, FactClaim, TextClaim)

_CITE = re.compile(r"\[@?([A-Za-z0-9_:.\-@]+)\]")
_SPLIT = re.compile(r"(?<!\d)\.|\.(?!\d)|[!?؟؛]|\n+")    # a dot between two digits is a decimal point
_ARITH = re.compile(r"\s*([0-9\s+\-*/×÷−().٫^]+?)\s*=\s*(-?[0-9]+(?:[.٫][0-9]+)?(?:/[0-9]+)?)\s*\Z")


def extract_claims(answer: str, prefix: str = "c") -> list[ArithmeticClaim | TextClaim]:
    """Split a structured answer into atomic claims, in order, with ids ``c1``, ``c2``, ..."""
    if not isinstance(answer, str):
        raise ValueError("answer must be a string")
    out: list[ArithmeticClaim | TextClaim] = []
    for part in _SPLIT.split(answer):
        if part is None:
            continue
        cites = tuple(dict.fromkeys(_CITE.findall(part)))
        body = re.sub(r"\s+", " ", _CITE.sub(" ", part)).strip()
        if not body:
            continue
        cid = f"{prefix}{len(out) + 1}"
        m = _ARITH.match(normalize_digits(body))
        if m and re.search(r"[+\-*/×÷−^]", m.group(1)):
            out.append(ArithmeticClaim(cid, m.group(1).replace("^", "**").strip(), m.group(2)))
        else:
            out.append(TextClaim(cid, body, cites))
    return out
