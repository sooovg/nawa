"""Reranker interface and a rule-based lexical reranker; retrieved chunks as P6-04 evidence (ROADMAP P6-01, ADR-0008).

A reranker takes the query and the hits and returns the same hits in a new order. It may not add, drop or change
a hit (checked). :class:`LexicalReranker` orders by, in turn:
1. whether the normalised query occurs as a contiguous phrase;
2. how many distinct query terms the chunk contains;
3. BM25 score;
4. ``chunk_id``.

There are no weights to tune. A learned reranker is P6-01a (BLOCKED).

:func:`to_evidence` turns hits into :class:`nawa.verification.evidence.Evidence`, so that the P6-04 quote checker can
check a claim against a retrieved chunk. The evidence id is the chunk id, and the source is the document's source.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from nawa.retrieval.index import Hit, LexicalIndex, analyze
from nawa.verification.evidence import Evidence


class Reranker(Protocol):
    name: str

    def rerank(self, query: str, hits: Sequence[Hit]) -> list[Hit]: ...


def _has_phrase(q: list[str], t: list[str]) -> bool:
    return bool(q) and any(t[i:i + len(q)] == q for i in range(len(t) - len(q) + 1))


class LexicalReranker:
    name = "lexical_rules"

    def __init__(self, strip_al: bool = True) -> None:
        self.strip_al = strip_al

    def rerank(self, query: str, hits: Sequence[Hit]) -> list[Hit]:
        q = analyze(query, self.strip_al)
        qs = set(q)

        def key(h: Hit):
            t = analyze(h.text, self.strip_al)
            return (not _has_phrase(q, t), -len(qs & set(t)), -h.score, h.chunk_id)
        return sorted(hits, key=key)


def apply_reranker(reranker: Reranker, query: str, hits: Sequence[Hit]) -> list[Hit]:
    out = list(reranker.rerank(query, hits))
    if sorted(map(id, out)) != sorted(map(id, hits)) or len(out) != len(hits):
        raise ValueError(f"reranker {reranker.name!r} must return exactly the given hits, reordered")
    return out


def to_evidence(index: LexicalIndex, hits: Sequence[Hit]) -> list[Evidence]:
    return [Evidence(h.chunk_id, h.text, source=index.docs[h.doc_id].source) for h in hits]
