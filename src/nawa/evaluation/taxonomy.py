"""Parse docs/failure_taxonomy.md into a machine-usable registry (P1-01)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

TAXONOMY_PATH = Path(__file__).resolve().parents[3] / "docs" / "failure_taxonomy.md"
_ROW = re.compile(r"^\| (FT-\d{2}) \|([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|$", re.M)


@dataclass(frozen=True)
class FailureCategory:
    id: str
    name_ar: str
    name_en: str
    definition: str
    detection: str
    suites: tuple[str, ...]


@lru_cache(maxsize=1)
def load_taxonomy(path: Path = TAXONOMY_PATH) -> dict[str, FailureCategory]:
    text = path.read_text(encoding="utf-8")
    out: dict[str, FailureCategory] = {}
    for m in _ROW.finditer(text):
        fid, ar, en, d, det, suites = (g.strip() for g in m.groups())
        if fid in out:
            raise ValueError(f"duplicate taxonomy id {fid}")
        out[fid] = FailureCategory(fid, ar, en, d, det, tuple(s.strip() for s in suites.split(",")))
    return out


def by_name(name_en: str) -> FailureCategory:
    for c in load_taxonomy().values():
        if c.name_en == name_en:
            return c
    raise KeyError(name_en)
