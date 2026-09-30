"""Text normalisation and answer extraction shared by all scorers (P1-02)."""

from __future__ import annotations

import re
import unicodedata

_DIACRITICS = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]")
_TATWEEL = "\u0640"
_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)

ABSTAIN_MARKERS = (
    "غير موجود في السياق", "غير موجودة في السياق", "غير موجود", "غير موجودة", "لا يوجد في السياق", "غير مذكور", "لم يذكر", "لم يرد", "لا تتوفر", "غير متوفر",
    "لا اعرف", "لا يمكنني تحديد", "لا يمكن تحديد", "لا استطيع تحديد", "لا تحتوي", "لا يحتوي", "ليس في السياق",
    "معلومات كافيه", "not in the context", "not mentioned", "i don't know", "i do not know", "cannot be determined",
    "not provided", "no information",
)


def normalize_digits(text: str) -> str:
    return text.translate(_AR_DIGITS)


def normalize(text: str) -> str:
    """Arabic-aware normalisation for lenient matching."""
    t = unicodedata.normalize("NFKC", text)
    t = normalize_digits(t)
    t = _DIACRITICS.sub("", t).replace(_TATWEEL, "")
    t = re.sub("[إأآٱ]", "ا", t)
    t = t.replace("ى", "ي").replace("ة", "ه").replace("ؤ", "و").replace("ئ", "ي")
    t = t.lower()
    t = re.sub(r"(?<=\d)[,٬.](?=\d{3}\b)", "", t)  # thousands separators
    t = _PUNCT.sub(" ", t)
    return re.sub(r"\s+", " ", t).strip()


def contains(output: str, gold: str) -> bool:
    g = normalize(gold)
    if not g:
        return False
    o = normalize(output)
    if g.isdigit():
        return re.search(rf"(?<!\d){re.escape(g)}(?!\d)", o) is not None
    return re.search(rf"(?<!\w){re.escape(g)}(?!\w)", o) is not None or (len(g) > 3 and g in o)


def contains_any(output: str, golds: list[str]) -> bool:
    return any(contains(output, g) for g in golds)


def is_abstention(output: str) -> bool:
    o = normalize(output)
    return any(normalize(m) in o for m in ABSTAIN_MARKERS)


_NUM = re.compile(r"-?\d+(?:\.\d+)?")


def final_number(output: str) -> float | None:
    """Number after the last 'الجواب'/'answer' marker, else the last number in the text."""
    t = normalize_digits(output)
    t = re.sub(r"(?<=\d)[,٬](?=\d{3})", "", t)
    for marker in ("الجواب", "الإجابة", "الاجابة", "answer"):
        idx = t.lower().rfind(marker)
        if idx != -1:
            m = _NUM.search(t[idx:])
            if m:
                return float(m.group())
    nums = _NUM.findall(t)
    return float(nums[-1]) if nums else None


def first_label(output: str, labels: tuple[str, ...]) -> str | None:
    o = normalize(output)
    best: tuple[int, str] | None = None
    for lab in labels:
        m = re.search(rf"(?<!\w){re.escape(lab)}(?!\w)", o)
        if m and (best is None or m.start() < best[0]):
            best = (m.start(), lab)
    return best[1] if best else None
