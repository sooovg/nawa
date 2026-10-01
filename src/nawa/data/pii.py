"""Deterministic PII and secret redaction (P2-05, RISK-10).

Each match is replaced by a typed placeholder such as ``[EMAIL]``. Reported spans carry the type and
offsets only, never the value, so logs and reports do not re-leak PII. Checksums cut false positives:
IBAN uses ISO 13616 mod-97, payment cards use Luhn, Saudi national/iqama IDs use their Luhn variant.

Limitation: person names, addresses, and free-text identifiers are not detectable by rules; they
need a reviewed model or human review later (not in this task).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from nawa.evaluation.normalize import normalize_digits

_D = r"[0-9\u0660-\u0669\u06f0-\u06f9]"


def _digits(s: str) -> str:
    return re.sub(r"\D", "", normalize_digits(s))


def luhn_ok(number: str) -> bool:
    ds = [int(c) for c in _digits(number)]
    if len(ds) < 2:
        return False
    total = 0
    for i, d in enumerate(reversed(ds)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def iban_ok(iban: str) -> bool:
    s = re.sub(r"\s", "", normalize_digits(iban)).upper()
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{10,30}", s):
        return False
    r = s[4:] + s[:4]
    return int("".join(str(int(c, 36)) for c in r)) % 97 == 1


def saudi_id_ok(number: str) -> bool:
    d = _digits(number)
    if len(d) != 10 or d[0] not in "12":
        return False
    total = 0
    for i, c in enumerate(d[:9]):
        v = int(c)
        if i % 2 == 0:
            v *= 2
            v = v // 10 + v % 10
        total += v
    return (10 - total % 10) % 10 == int(d[9])


PATTERNS: dict[str, tuple[re.Pattern[str], object]] = {
    "secret": (re.compile(r"\b(?:hf_[A-Za-z0-9]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}"
                          r"|sk-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16})\b"), None),
    "email": (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), None),
    "iban": (re.compile(r"\b[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]{4}){2,7}(?:[ ]?[A-Z0-9]{1,4})?\b"), iban_ok),
    "card": (re.compile(rf"(?<!{_D})(?:{_D}[ -]?){{12,18}}{_D}(?!{_D})"), luhn_ok),
    "national_id": (re.compile(rf"(?<!{_D})[12١٢]{_D}{{9}}(?!{_D})"), saudi_id_ok),
    "phone": (re.compile(rf"(?<![\w+])(?:\+|00)?(?:{_D}[ -]?){{8,14}}{_D}(?![\w])"), None),
    "ipv4": (re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b"), None),
}
ORDER = ("secret", "email", "iban", "card", "national_id", "phone", "ipv4")


@dataclass(frozen=True)
class Span:
    type: str
    start: int
    end: int


def find_pii(text: str, types: tuple[str, ...] | list[str] = ORDER) -> list[Span]:
    """Non-overlapping spans; earlier types in ORDER win (a card is not also reported as a phone)."""
    taken: list[Span] = []
    for t in ORDER:
        if t not in types:
            continue
        pat, check = PATTERNS[t]
        for m in pat.finditer(text):
            if check is not None and not check(m.group(0)):  # type: ignore[operator]
                continue
            if t == "phone" and len(_digits(m.group(0))) < 9:
                continue
            if any(m.start() < s.end and s.start < m.end() for s in taken):
                continue
            taken.append(Span(t, m.start(), m.end()))
    return sorted(taken, key=lambda s: s.start)


def redact(text: str, types: tuple[str, ...] | list[str] = ORDER) -> tuple[str, list[Span]]:
    spans = find_pii(text, types)
    out, last = [], 0
    for s in spans:
        out.append(text[last:s.start])
        out.append(f"[{s.type.upper()}]")
        last = s.end
    out.append(text[last:])
    return "".join(out), spans
