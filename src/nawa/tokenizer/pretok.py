"""Lossless pre-tokenizers: they only choose split points, so joining the chunks gives back the text.

* ``default``: optional leading space + a letter run (combining marks and tashkeel stay attached), a run of up to 3 digits, a punctuation/symbol run,
  or a whitespace run (GPT-2 style, Unicode-aware).
* ``arabic``: the default, then Arabic letter runs are split into proclitics + stem + enclitics with a
  fixed affix list, only when the stem keeps at least 3 letters. EXPERIMENTAL: rule-based, no lexicon,
  so it also splits words whose first letters merely look like a clitic (measured by P3-02).
"""

from __future__ import annotations

import re

_MARKS = "\u0300-\u036f\u064b-\u065f\u0670\u06d6-\u06ed\u200c"  # combining marks, tashkeel, ZWNJ stay in words
_CHUNK = re.compile(rf" ?(?:[^\W\d_]|[{_MARKS}])+| ?\d{{1,3}}| ?[^\s\w{_MARKS}]+|\s+(?!\S)|\s+|_+", re.UNICODE)
_AR_WORD = re.compile(r"^( ?)([\u0621-\u064a]+)$")
PREFIXES = ("وبال", "وال", "بال", "فال", "كال", "لل", "و", "ف", "ب", "ل", "ك", "س")
SUFFIXES = ("هما", "كما", "تهم", "هم", "هن", "كم", "كن", "نا", "ها", "ه", "ك", "ي")
_MIN_STEM = 3


def default(text: str) -> list[str]:
    chunks = _CHUNK.findall(text)
    if "".join(chunks) != text:  # every character is matched by some branch; guard against regressions
        raise AssertionError("pre-tokenizer lost characters")
    return chunks


def split_arabic_word(word: str) -> list[str]:
    m = _AR_WORD.match(word)
    if not m:
        return [word]
    space, w = m.groups()
    pre = ""
    for p in PREFIXES:
        if w.startswith(p) and len(w) - len(p) >= _MIN_STEM:
            pre, w = p, w[len(p):]
            break
    suf = ""
    for s in SUFFIXES:
        if w.endswith(s) and len(w) - len(s) >= _MIN_STEM:
            suf, w = s, w[: -len(s)]
            break
    parts = [space + pre] if pre else []
    parts.append(w if pre else space + w)
    if suf:
        parts.append(suf)
    return [x for x in parts if x]


def arabic(text: str) -> list[str]:
    out: list[str] = []
    for c in default(text):
        out.extend(split_arabic_word(c))
    return out


PRETOKENIZERS = {"default": default, "arabic": arabic}
