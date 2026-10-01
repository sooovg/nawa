"""Exact and near de-duplication (P2-05).

Exact: sha256 of the Arabic-aware normalised text (`nawa.evaluation.normalize.normalize`).
Near: MinHash over word shingles with LSH banding to find candidate pairs, then the *exact* shingle
Jaccard confirms each pair, so LSH only affects recall, never precision. The first record in input
order is kept; later ones point to it with `duplicate_of`. Pure Python, deterministic for a seed.
"""

from __future__ import annotations

import hashlib
import random
from collections import defaultdict
from dataclasses import dataclass

from nawa.evaluation.normalize import normalize

_MERSENNE = (1 << 61) - 1


def norm_hash(text: str) -> str:
    return hashlib.sha256(normalize(text).encode("utf-8")).hexdigest()


def shingles(text: str, k: int = 5) -> set[str]:
    words = normalize(text).split()
    if len(words) < k:
        return {" ".join(words)} if words else set()
    return {" ".join(words[i:i + k]) for i in range(len(words) - k + 1)}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def _h64(s: str) -> int:
    return int.from_bytes(hashlib.blake2b(s.encode("utf-8"), digest_size=8).digest(), "big")


class MinHasher:
    def __init__(self, num_perm: int = 128, seed: int = 1234) -> None:
        rng = random.Random(seed)
        self.params = [(rng.randrange(1, _MERSENNE), rng.randrange(0, _MERSENNE)) for _ in range(num_perm)]

    def signature(self, sh: set[str]) -> tuple[int, ...]:
        hs = [_h64(s) for s in sh] or [0]
        return tuple(min((a * h + b) % _MERSENNE for h in hs) for a, b in self.params)


@dataclass
class DedupResult:
    duplicate_of: dict[str, str]      # record id -> kept record id
    kind: dict[str, str]              # record id -> "exact" | "near"
    similarity: dict[str, float]


def dedup(records: list[tuple[str, str]], k: int = 5, num_perm: int = 128, bands: int = 32,
          threshold: float = 0.8, seed: int = 1234) -> DedupResult:
    """`records` is [(id, text)] in priority order (earlier is kept)."""
    if num_perm % bands:
        raise ValueError("num_perm must be divisible by bands")
    rows = num_perm // bands
    dup: dict[str, str] = {}
    kind: dict[str, str] = {}
    sim: dict[str, float] = {}
    seen_exact: dict[str, str] = {}
    kept: list[str] = []
    order: dict[str, int] = {}
    for rid, text in records:
        h = norm_hash(text)
        if h in seen_exact:
            dup[rid], kind[rid], sim[rid] = seen_exact[h], "exact", 1.0
        else:
            seen_exact[h] = rid
            order[rid] = len(kept)
            kept.append(rid)
    texts = dict(records)
    sh = {rid: shingles(texts[rid], k) for rid in kept}
    mh = MinHasher(num_perm, seed)
    buckets: dict[tuple[int, tuple[int, ...]], list[str]] = defaultdict(list)
    for rid in kept:
        sig = mh.signature(sh[rid])
        cands = set()
        for b in range(bands):
            key = (b, sig[b * rows:(b + 1) * rows])
            cands.update(buckets[key])
            buckets[key].append(rid)
        best, best_j = None, 0.0
        for c in cands:
            if c in dup:
                continue
            j = jaccard(sh[rid], sh[c])
            if j >= threshold and (best is None or j > best_j or (j == best_j and order[c] < order[best])):
                best, best_j = c, j
        if best is not None:
            dup[rid], kind[rid], sim[rid] = best, "near", round(best_j, 4)
    return DedupResult(dup, kind, sim)
