"""Rule-based quality score and script-based language tag (P2-05).

Not a learned classifier: every component is a measurable text statistic, so the score is
reproducible and explainable. Thresholds are in configs/data_pipeline.yaml.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_AR = re.compile(r"[\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff]")
_LAT = re.compile(r"[A-Za-z]")
_LETTER = re.compile(r"\w", re.UNICODE)


def language(text: str) -> str:
    ar, lat = len(_AR.findall(text)), len(_LAT.findall(text))
    letters = ar + lat
    if letters < 10:
        return "unknown"
    if ar / letters >= 0.8:
        return "ar"
    if lat / letters >= 0.8:
        return "en"
    return "mixed"


@dataclass
class Quality:
    score: float
    flags: list[str] = field(default_factory=list)
    stats: dict[str, float] = field(default_factory=dict)


def quality(text: str, max_repeated_line_ratio: float = 0.3, max_symbol_ratio: float = 0.25,
            max_char_run: int = 12, extra_flags: list[str] | None = None) -> Quality:
    flags = list(extra_flags or [])
    chars = [c for c in text if not c.isspace()]
    n = len(chars) or 1
    symbol_ratio = sum(1 for c in chars if not _LETTER.match(c)) / n
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    rep = 1 - len(set(lines)) / len(lines) if lines else 0.0
    run = max((len(m.group(0)) for m in re.finditer(r"(.)\1*", text)), default=0)
    words = text.split()
    uniq = len(set(words)) / len(words) if words else 0.0
    # Each component scores in [0, 1] and scales with how far it is past its threshold, so an extreme
    # value cannot pass on a fixed penalty (EXP-0017). The score is the product of the components.
    comp: dict[str, float] = {}
    if symbol_ratio > max_symbol_ratio:
        flags.append("symbols")
        comp["symbols"] = max(0.0, 1 - (symbol_ratio - max_symbol_ratio) / (1 - max_symbol_ratio))
    if rep > max_repeated_line_ratio:
        flags.append("repeated_lines")
        comp["repeated_lines"] = 1 - rep
    if run > max_char_run:
        flags.append("char_run")
        comp["char_run"] = max(0.0, 1 - (run - max_char_run) / (2 * max_char_run))
    if words and uniq < 0.3:
        flags.append("low_word_diversity")
        comp["low_word_diversity"] = uniq / 0.3
    if "mojibake" in flags:
        comp["mojibake"] = 0.4
    score = 1.0
    for v in comp.values():
        score *= v
    stats = {"symbol_ratio": round(symbol_ratio, 4), "repeated_line_ratio": round(rep, 4), "max_char_run": run,
             "word_diversity": round(uniq, 4)}
    return Quality(round(max(0.0, score), 4), sorted(set(flags)), stats)
