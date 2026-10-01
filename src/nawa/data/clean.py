"""Text cleaning that keeps meaning (P2-05).

Kept on purpose: Arabic diacritics (tashkeel), ZWNJ (U+200C, needed in Persian/Urdu words), newlines.
Removed: control characters, zero-width spaces and BOM, bidi override/isolate controls (they can hide
text, "Trojan Source"), tatweel (typographic, configurable). Arabic presentation forms are mapped to
their base letters (NFKC on those ranges only), the rest of the text is NFC.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

BIDI_CONTROLS = "\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069\u200e\u200f\u061c"
ZERO_WIDTH = "\u200b\u2060\ufeff\u200d"  # ZWSP, word joiner, BOM, ZWJ (ZWNJ U+200C is kept)
TATWEEL = "\u0640"
_PRESENTATION = re.compile(r"[\ufb50-\ufdff\ufe70-\ufeff]")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")
# UTF-8 Arabic read as Latin-1/CP1252 gives runs like "Ø§Ù„" (mojibake).
_MOJIBAKE = re.compile(r"(?:[ØÙÚÛ][\x80-\xbf\u0152\u0153\u0160\u0161\u0178\u017d\u017e\u0192\u02c6\u02dc\u2013-\u203a\u20ac\u2122\xa0-\xbf]){3,}")


@dataclass
class CleanResult:
    text: str
    changes: dict[str, int] = field(default_factory=dict)
    flags: list[str] = field(default_factory=list)


def looks_mojibake(text: str) -> bool:
    return bool(_MOJIBAKE.search(text))


def clean_text(text: str, remove_tatweel: bool = True) -> CleanResult:
    changes: dict[str, int] = {}

    def count(name: str, n: int) -> None:
        if n:
            changes[name] = changes.get(name, 0) + n

    flags = ["mojibake"] if looks_mojibake(text) else []
    t = _PRESENTATION.sub(lambda m: unicodedata.normalize("NFKC", m.group(0)), text)
    count("presentation_forms", len(_PRESENTATION.findall(text)))
    t = unicodedata.normalize("NFC", t)
    for name, chars in (("bidi_controls", BIDI_CONTROLS), ("zero_width", ZERO_WIDTH)):
        n = sum(t.count(c) for c in chars)
        if n:
            t = t.translate({ord(c): None for c in chars})
        count(name, n)
    if remove_tatweel:
        count("tatweel", t.count(TATWEEL))
        t = t.replace(TATWEEL, "")
    count("control_chars", len(_CONTROL.findall(t)))
    t = _CONTROL.sub("", t)
    t = t.replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"[ \t\u00a0\u2000-\u200a\u3000]+", " ", ln).strip() for ln in t.split("\n")]
    t2 = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
    if t2 != t:
        count("whitespace", 1)
    return CleanResult(t2, changes, flags)
