"""Documents with freshness and source-quality metadata (ROADMAP P6-01, ADR-0008).

Both values are given by the caller; nothing is inferred:
- ``published`` is an ISO date (``YYYY-MM-DD``) or ``None`` (unknown);
- ``quality`` is a :class:`SourceQuality` tier.

Freshness is always computed against an explicit ``as_of`` date, never the wall clock, so results replay
deterministically. The metadata is used **only to filter**, never to change a score. Weighting scores by quality or
age would need tuned numbers, which are not set here (ADR-0008: no thresholds from synthetic data).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from enum import Enum


class SourceQuality(str, Enum):
    PRIMARY = "PRIMARY"          # the original source of the fact
    SECONDARY = "SECONDARY"      # reports a primary source
    UNVERIFIED = "UNVERIFIED"
    UNKNOWN = "UNKNOWN"


QUALITY_RANK = {SourceQuality.PRIMARY: 3, SourceQuality.SECONDARY: 2, SourceQuality.UNVERIFIED: 1,
                SourceQuality.UNKNOWN: 0}


def parse_date(value: str | None) -> dt.date | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("dates must be ISO strings YYYY-MM-DD")
    try:
        d = dt.date.fromisoformat(value)
    except ValueError as e:
        raise ValueError(f"bad date {value!r}: {e}") from None
    if d.isoformat() != value:
        raise ValueError(f"date must be exactly YYYY-MM-DD, got {value!r}")
    return d


@dataclass(frozen=True)
class Document:
    doc_id: str
    text: str
    source: str = ""
    published: str | None = None
    quality: SourceQuality = SourceQuality.UNKNOWN

    def __post_init__(self) -> None:
        if not isinstance(self.doc_id, str) or not self.doc_id.strip() or any(c in self.doc_id for c in "#\n\t "):
            raise ValueError("doc_id must be a non-empty string without '#' or whitespace")
        if not isinstance(self.text, str):
            raise ValueError("text must be a string")
        if not isinstance(self.quality, SourceQuality):
            raise ValueError("quality must be a SourceQuality")
        parse_date(self.published)

    def age_days(self, as_of: str) -> int | None:
        p, a = parse_date(self.published), parse_date(as_of)
        if a is None:
            raise ValueError("as_of is required")
        return None if p is None else (a - p).days


@dataclass(frozen=True)
class Filter:
    """Keep a document only if it meets every given condition. Unknown dates fail a freshness condition."""

    min_quality: SourceQuality | None = None
    max_age_days: int | None = None
    as_of: str | None = None
    exclude_future: bool = True

    def __post_init__(self) -> None:
        if self.max_age_days is not None:
            if isinstance(self.max_age_days, bool) or not isinstance(self.max_age_days, int) or self.max_age_days < 0:
                raise ValueError("max_age_days must be a non-negative int")
            if self.as_of is None:
                raise ValueError("max_age_days needs an explicit as_of date (no wall clock)")
        parse_date(self.as_of)
        if self.min_quality is not None and not isinstance(self.min_quality, SourceQuality):
            raise ValueError("min_quality must be a SourceQuality")

    def keeps(self, doc: Document) -> bool:
        if self.min_quality is not None and QUALITY_RANK[doc.quality] < QUALITY_RANK[self.min_quality]:
            return False
        if self.as_of is not None:
            age = doc.age_days(self.as_of)
            if self.max_age_days is not None and (age is None or age > self.max_age_days):
                return False
            if self.exclude_future and age is not None and age < 0:
                return False
        return True
