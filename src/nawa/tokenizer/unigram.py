"""Unigram language-model tokenizer (P3-01), trained from scratch with byte fallback.

Training (hard-EM / Viterbi training, a simplification of SentencePiece's EM):
1. seed pieces: the most frequent substrings (length 2..max_piece_len) of pre-tokenizer chunks,
   plus every character seen at least `min_char_count` times;
2. repeat: Viterbi-segment every chunk, re-estimate piece log-probabilities from the counts, and drop
   the least-used multi-character pieces (shrink factor) until the target size is reached;
3. two final re-estimation passes.
Single characters are never pruned. A character with no piece is encoded as its UTF-8 bytes (ids 0..255),
so encoding is lossless. Deterministic: ties break on the piece string.
"""

from __future__ import annotations

import math
from collections import Counter
from typing import Any

from nawa.tokenizer.pretok import PRETOKENIZERS

_BYTE_COST = 20.0  # per byte; larger than any piece cost so fallback is the last resort


class UnigramTokenizer:
    def __init__(self, pieces: dict[str, float], pretok: str = "default", name: str = "unigram") -> None:
        self.pretok = pretok
        self.name = name
        self._split = PRETOKENIZERS[pretok]
        pieces = {p: round(lp, 6) for p, lp in pieces.items()}  # the saved precision, so save/load is identical
        ordered = sorted(pieces, key=lambda p: (-pieces[p], p))
        self.pieces = {p: pieces[p] for p in ordered}
        self.id_of = {p: 256 + i for i, p in enumerate(ordered)}
        self.piece_of = ordered
        self.max_len = max((len(p) for p in ordered), default=1)
        self._cache: dict[str, list[int]] = {}

    @property
    def vocab_size(self) -> int:
        return 256 + len(self.pieces)

    @staticmethod
    def _viterbi(chunk: str, logp: dict[str, float], max_len: int) -> list[str | bytes]:
        n = len(chunk)
        best = [math.inf] * (n + 1)
        back: list[tuple[int, bool]] = [(0, False)] * (n + 1)
        best[0] = 0.0
        for end in range(1, n + 1):
            for start in range(max(0, end - max_len), end):
                if best[start] == math.inf:
                    continue
                lp = logp.get(chunk[start:end])
                if lp is not None:
                    cost = best[start] - lp
                    if cost < best[end]:
                        best[end], back[end] = cost, (start, False)
            if best[end] == math.inf or chunk[end - 1:end] not in logp:
                cost = best[end - 1] + _BYTE_COST * len(chunk[end - 1].encode("utf-8"))
                if cost < best[end]:
                    best[end], back[end] = cost, (end - 1, True)
        out: list[str | bytes] = []
        end = n
        while end > 0:
            start, is_byte = back[end]
            out.append(chunk[start:end].encode("utf-8") if is_byte else chunk[start:end])
            end = start
        return out[::-1]

    @classmethod
    def train(cls, texts: list[str], vocab_size: int, pretok: str = "default", name: str = "unigram",
              max_piece_len: int = 10, seed_factor: int = 4, shrink: float = 0.75, min_char_count: int = 2,
              max_iters: int = 30) -> "UnigramTokenizer":
        split = PRETOKENIZERS[pretok]
        freq: Counter[str] = Counter()
        for t in texts:
            freq.update(split(t))
        target = vocab_size - 256
        chars: Counter[str] = Counter()
        subs: Counter[str] = Counter()
        for w, c in freq.items():
            for ch in w:
                chars[ch] += c
            for i in range(len(w)):
                for j in range(i + 2, min(len(w), i + max_piece_len) + 1):
                    subs[w[i:j]] += c
        keep_chars = {ch for ch, c in chars.items() if c >= min_char_count}
        if len(keep_chars) >= target:
            keep_chars = set(sorted(keep_chars, key=lambda ch: (-chars[ch], ch))[:target])
        n_multi = max(0, target * seed_factor - len(keep_chars))
        multi = sorted((s for s, c in subs.items() if c >= 2), key=lambda s: (-subs[s] * len(s), s))[:n_multi]
        pieces: set[str] = keep_chars | set(multi)

        def estimate(ps: set[str]) -> tuple[dict[str, float], Counter[str]]:
            total = sum(chars[ch] for ch in ps if len(ch) == 1) + sum(subs[s] for s in ps if len(s) > 1)
            logp = {p: math.log(((chars[p] if len(p) == 1 else subs[p]) + 1) / (total + len(ps))) for p in ps}
            for _ in range(2):
                ml = max(len(p) for p in logp)
                counts: Counter[str] = Counter()
                for w, c in freq.items():
                    for seg in cls._viterbi(w, logp, ml):
                        if isinstance(seg, str):
                            counts[seg] += c
                tot = sum(counts.values()) + len(ps)
                logp = {p: math.log((counts[p] + 1) / tot) for p in ps}
            return logp, counts

        logp, counts = estimate(pieces)
        for _ in range(max_iters):
            if len(pieces) <= target:
                break
            multis = sorted((p for p in pieces if len(p) > 1), key=lambda p: (counts[p], logp[p], p))
            n_keep = max(target, int(len(pieces) * shrink))
            drop = len(pieces) - n_keep
            pieces -= set(multis[:drop])
            logp, counts = estimate(pieces)
        return cls(logp, pretok, name)

    def _encode_chunk(self, chunk: str) -> list[int]:
        hit = self._cache.get(chunk)
        if hit is not None:
            return hit
        ids: list[int] = []
        for seg in self._viterbi(chunk, self.pieces, self.max_len):
            if isinstance(seg, bytes):
                ids.extend(seg)
            else:
                ids.append(self.id_of[seg])
        if len(self._cache) < 200_000:
            self._cache[chunk] = ids
        return ids

    def encode(self, text: str) -> list[int]:
        out: list[int] = []
        for c in self._split(text):
            out.extend(self._encode_chunk(c))
        return out

    def decode(self, ids: list[int]) -> str:
        buf = bytearray()
        for i in ids:
            buf.extend(bytes([i]) if i < 256 else self.piece_of[i - 256].encode("utf-8"))
        return buf.decode("utf-8")

    def to_dict(self) -> dict[str, Any]:
        return {"type": "unigram", "name": self.name, "pretok": self.pretok,
                "pieces": [[p, round(lp, 6)] for p, lp in self.pieces.items()]}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "UnigramTokenizer":
        return cls({p: lp for p, lp in d["pieces"]}, d["pretok"], d["name"])
