"""Decontamination against evaluation sets (P2-05, RISK-01, G2 "zero known leakage into frozen").

Three checks, none of which reads frozen content:

1. **Frozen item hash:** a record whose `content_hash` is in `eval/frozen_item_hashes.txt`.
2. **Public eval n-gram overlap:** any word n-gram (default 8) shared with a dev/calib item, rebuilt
   from code (P1-02). This also catches copies of the shared templates frozen is generated from.
3. **Hashed n-gram index (optional):** a file of hashed n-grams. The Eval role can build one for
   frozen in the private HF repo (P2-05a), so frozen text never enters Git or this process.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from nawa.evaluation.normalize import normalize

REPO = Path(__file__).resolve().parents[3]
FROZEN_HASHES = REPO / "eval" / "frozen_item_hashes.txt"


def ngram_hashes(text: str, n: int = 8) -> set[str]:
    words = normalize(text).split()
    grams = [" ".join(words[i:i + n]) for i in range(len(words) - n + 1)]
    return {hashlib.sha256(g.encode("utf-8")).hexdigest()[:16] for g in grams}


def eval_texts(splits: tuple[str, ...] | list[str] = ("dev", "calib")) -> list[str]:
    from nawa.evaluation.build import build_public
    if "frozen" in splits:
        raise ValueError("frozen is never read for decontamination; use its hashes (P2-05a)")
    pub = build_public()
    out = []
    for split in splits:
        for items in pub[split].values():
            for it in items:
                out.extend(m["content"] for m in it.messages)
    return out


@dataclass
class ContaminationIndex:
    ngram: set[str]
    item_hashes: set[str]
    n: int

    @classmethod
    def build(cls, n: int = 8, splits: tuple[str, ...] | list[str] = ("dev", "calib"),
              extra_index_files: list[Path] | None = None, frozen_hashes: Path = FROZEN_HASHES) -> "ContaminationIndex":
        grams: set[str] = set()
        for t in eval_texts(splits):
            grams |= ngram_hashes(t, n)
        for f in extra_index_files or []:
            grams |= {ln.strip() for ln in Path(f).read_text(encoding="utf-8").splitlines() if ln.strip()}
        items = {ln.strip() for ln in frozen_hashes.read_text(encoding="utf-8").splitlines() if ln.strip()}
        return cls(grams, items, n)

    def check(self, text: str, content_hash: str | None = None) -> tuple[bool, str]:
        if content_hash and content_hash in self.item_hashes:
            return True, "content hash matches a frozen item"
        hits = ngram_hashes(text, self.n) & self.ngram
        if hits:
            return True, f"{len(hits)} shared {self.n}-gram(s) with evaluation text"
        return False, ""
