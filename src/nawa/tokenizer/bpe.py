"""Byte-level BPE (P3-01), trained from scratch.

Base symbols are the 256 bytes, so any text encodes with no unknown token. Merges are learned inside
pre-tokenizer chunks with a lazy max-heap of pair counts; ties break on the smaller pair, so training is
deterministic. Encoding applies merges by rank, as in GPT-2.
"""

from __future__ import annotations

import heapq
from collections import Counter, defaultdict
from typing import Any

from nawa.tokenizer.pretok import PRETOKENIZERS


class BPETokenizer:
    def __init__(self, merges: list[tuple[int, int]], pretok: str = "default", name: str = "bpe") -> None:
        self.merges = merges
        self.pretok = pretok
        self.name = name
        self._split = PRETOKENIZERS[pretok]
        self.rank = {p: i for i, p in enumerate(merges)}
        self.token_bytes: list[bytes] = [bytes([i]) for i in range(256)]
        for a, b in merges:
            self.token_bytes.append(self.token_bytes[a] + self.token_bytes[b])
        self._cache: dict[str, list[int]] = {}

    @property
    def vocab_size(self) -> int:
        return 256 + len(self.merges)

    @classmethod
    def train(cls, texts: list[str], vocab_size: int, pretok: str = "default", name: str = "bpe",
              min_frequency: int = 2) -> "BPETokenizer":
        split = PRETOKENIZERS[pretok]
        freq: Counter[str] = Counter()
        for t in texts:
            freq.update(split(t))
        words = [list(w.encode("utf-8")) for w in freq]
        counts = list(freq.values())
        pairs: Counter[tuple[int, int]] = Counter()
        where: dict[tuple[int, int], set[int]] = defaultdict(set)
        for i, w in enumerate(words):
            for p in zip(w, w[1:]):
                pairs[p] += counts[i]
                where[p].add(i)
        heap = [(-c, p) for p, c in pairs.items()]
        heapq.heapify(heap)
        merges: list[tuple[int, int]] = []
        while 256 + len(merges) < vocab_size and heap:
            negc, best = heapq.heappop(heap)
            if pairs.get(best, 0) != -negc:
                continue  # stale heap entry
            if -negc < min_frequency:
                break
            new = 256 + len(merges)
            merges.append(best)
            changed: Counter[tuple[int, int]] = Counter()
            for i in list(where[best]):
                w, c = words[i], counts[i]
                j, out = 0, []
                while j < len(w):
                    if j + 1 < len(w) and (w[j], w[j + 1]) == best:
                        out.append(new)
                        j += 2
                    else:
                        out.append(w[j])
                        j += 1
                for p in zip(w, w[1:]):
                    changed[p] -= c
                for p in zip(out, out[1:]):
                    changed[p] += c
                    where[p].add(i)
                words[i] = out
            for p, d in changed.items():
                if d:
                    pairs[p] += d
                    if pairs[p] <= 0:
                        pairs.pop(p)
                    else:
                        heapq.heappush(heap, (-pairs[p], p))
            pairs.pop(best, None)
            where.pop(best, None)
        return cls(merges, pretok, name)

    def _encode_chunk(self, chunk: str) -> list[int]:
        hit = self._cache.get(chunk)
        if hit is not None:
            return hit
        w = list(chunk.encode("utf-8"))
        while len(w) > 1:
            best_rank, best_j = None, -1
            for j in range(len(w) - 1):
                r = self.rank.get((w[j], w[j + 1]))
                if r is not None and (best_rank is None or r < best_rank):
                    best_rank, best_j = r, j
            if best_rank is None:
                break
            w = w[:best_j] + [256 + best_rank] + w[best_j + 2:]
        if len(self._cache) < 200_000:
            self._cache[chunk] = w
        return w

    def encode(self, text: str) -> list[int]:
        out: list[int] = []
        for c in self._split(text):
            out.extend(self._encode_chunk(c))
        return out

    def decode(self, ids: list[int]) -> str:
        return b"".join(self.token_bytes[i] for i in ids).decode("utf-8")

    def to_dict(self) -> dict[str, Any]:
        return {"type": "bpe", "name": self.name, "pretok": self.pretok, "merges": [list(m) for m in self.merges]}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "BPETokenizer":
        return cls([tuple(m) for m in d["merges"]], d["pretok"], d["name"])  # type: ignore[misc]
