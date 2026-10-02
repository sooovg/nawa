"""Lexical index with BM25, from scratch, rebuildable and verifiable (ROADMAP P6-01, ADR-0008).

**Analyzer.** Text is normalised with ``nawa.evaluation.normalize.normalize`` (reused, unchanged): NFKC,
Arabic-Indic digits, harakat and tatweel removed, alef/ya/ta-marbuta unified, lower case, punctuation removed. It is
then split on whitespace. With ``strip_al`` (default on), a token that starts with ``ال`` and has more than four
letters is indexed without it, so that ``المدينة`` and ``مدينة`` match. There is no other stemming, no stop words and no
synonyms.

**Scoring.** BM25 with the textbook constants ``k1 = 1.2`` and ``b = 0.75``. They are formula constants, not tuned
on any data, and are recorded in the manifest.
- ``idf = ln(1 + (N − df + 0.5) / (df + 0.5))``;
- ``score = Σ_t idf_t · tf · (k1 + 1) / (tf + k1 · (1 − b + b · len / avglen))``, over the distinct query terms
  in sorted order.
- Ranking is by score descending, then ``chunk_id``, so equal scores have one fixed order.
- A chunk that shares no term with the query is never returned.

**Rebuild and verify.** :meth:`LexicalIndex.manifest` records:
- the schema, the analyzer and BM25 settings, and the chunker settings;
- every chunk (id, offsets, SHA-256);
- the corpus hash (documents and metadata) and the postings hash.

:func:`verify` rebuilds the index from the documents and reports every difference. :meth:`LexicalIndex.from_json`
refuses a file whose stored hashes do not match its content.

**Duplicates.** With ``dedupe`` (default on), a chunk whose normalised text equals an earlier chunk's is not indexed
twice. The earlier chunk is the first in ``(doc_id, n)`` order. It is listed in ``duplicates``, so nothing is dropped
silently. If a filter rejects the kept chunk's document, search returns the first duplicate whose document passes.
It has the same normalised text, so the same score.

**Not a RAG system.** This is a lexical retriever over a synthetic corpus. There is no dense embedding, no learned
reranker, no generation and no real corpus; those are P6-01a (BLOCKED until OD-03 and a trained core). No retrieval
quality is claimed.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass

from nawa.evaluation.normalize import normalize
from nawa.retrieval.chunker import Chunk, chunk_document
from nawa.retrieval.metadata import Document, Filter

SCHEMA = 1
K1, B = 1.2, 0.75


def analyze(text: str, strip_al: bool = True) -> list[str]:
    toks = normalize(text).split()
    if strip_al:
        toks = [t[2:] if t.startswith("ال") and len(t) > 4 else t for t in toks]
    return toks


def _sha(obj: object) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
                          .encode("utf-8")).hexdigest()


def _doc_record(d: Document) -> dict:
    return {"doc_id": d.doc_id, "sha256": hashlib.sha256(d.text.encode("utf-8")).hexdigest(), "source": d.source,
            "published": d.published, "quality": d.quality.value}


@dataclass(frozen=True)
class Hit:
    chunk_id: str
    doc_id: str
    score: float
    matched: tuple[str, ...]       # query terms found in the chunk, sorted
    text: str


class LexicalIndex:
    def __init__(self, documents: Iterable[Document], max_chars: int = 400, overlap: int = 0, strip_al: bool = True,
                 dedupe: bool = True) -> None:
        docs = sorted(documents, key=lambda d: d.doc_id)
        ids = [d.doc_id for d in docs]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate doc_id")
        for d in docs:
            if not isinstance(d, Document):
                raise ValueError(f"not a Document: {d!r}")
        self.settings = {"schema": SCHEMA, "k1": K1, "b": B, "max_chars": max_chars, "overlap": overlap,
                         "strip_al": strip_al, "dedupe": dedupe, "analyzer": "nawa.evaluation.normalize+whitespace"}
        self.docs = {d.doc_id: d for d in docs}
        self.chunks: list[Chunk] = []
        self.duplicates: list[tuple[str, str]] = []        # (dropped chunk, kept chunk)
        self.copies: dict[int, list[Chunk]] = {}           # kept chunk index -> its dropped duplicates, in order
        self.tf: list[Counter] = []
        seen: dict[str, int] = {}
        for d in docs:
            for c in chunk_document(d, max_chars, overlap):
                toks = analyze(c.text, strip_al)
                if not toks:
                    continue
                key = " ".join(toks)
                if dedupe and key in seen:
                    self.duplicates.append((c.chunk_id, self.chunks[seen[key]].chunk_id))
                    self.copies.setdefault(seen[key], []).append(c)
                    continue
                seen[key] = len(self.chunks)
                self.chunks.append(c)
                self.tf.append(Counter(toks))
        self.lengths = [sum(t.values()) for t in self.tf]
        self.avglen = (sum(self.lengths) / len(self.lengths)) if self.lengths else 0.0
        self.postings: dict[str, list[tuple[int, int]]] = {}
        for i, t in enumerate(self.tf):
            for term, n in sorted(t.items()):
                self.postings.setdefault(term, []).append((i, n))

    # ---- scoring ------------------------------------------------------------------------------------------------
    def idf(self, term: str) -> float:
        n, df = len(self.chunks), len(self.postings.get(term, ()))
        return math.log(1 + (n - df + 0.5) / (df + 0.5))

    def search(self, query: str, k: int = 10, flt: Filter | None = None) -> list[Hit]:
        if isinstance(k, bool) or not isinstance(k, int) or k < 1:
            raise ValueError("k must be a positive int")
        terms = sorted(set(analyze(query, self.settings["strip_al"])))
        scores: dict[int, float] = {}
        matched: dict[int, list[str]] = {}
        for term in terms:
            idf = self.idf(term)
            for i, tf in self.postings.get(term, ()):
                norm = K1 * (1 - B + B * self.lengths[i] / self.avglen)
                scores[i] = scores.get(i, 0.0) + idf * tf * (K1 + 1) / (tf + norm)
                matched.setdefault(i, []).append(term)
        out = []
        for i, s in scores.items():
            # a filtered-out chunk is replaced by its first duplicate that passes (same normalised text, same score)
            c = next((x for x in [self.chunks[i], *self.copies.get(i, [])]
                      if flt is None or flt.keeps(self.docs[x.doc_id])), None)
            if c is None:
                continue
            out.append(Hit(c.chunk_id, c.doc_id, s, tuple(matched[i]), c.text))
        out.sort(key=lambda h: (-h.score, h.chunk_id))
        return out[:k]

    # ---- rebuild and verification -------------------------------------------------------------------------------
    def postings_json(self) -> dict:
        return {t: [[self.chunks[i].chunk_id, n] for i, n in p] for t, p in sorted(self.postings.items())}

    def manifest(self) -> dict:
        corpus = [_doc_record(self.docs[i]) for i in sorted(self.docs)]
        chunks = [{"chunk_id": c.chunk_id, "doc_id": c.doc_id, "start": c.start, "end": c.end, "sha256": c.sha256}
                  for c in self.chunks]
        return {"settings": self.settings, "corpus_sha256": _sha(corpus), "documents": corpus, "chunks": chunks,
                "duplicates": [list(x) for x in self.duplicates], "postings_sha256": _sha(self.postings_json()),
                "n_chunks": len(self.chunks), "n_terms": len(self.postings)}

    def to_json(self) -> str:
        body = {"manifest": self.manifest(), "postings": self.postings_json()}
        return json.dumps({**body, "file_sha256": _sha(body)}, sort_keys=True, ensure_ascii=False)

    @staticmethod
    def check_json(data: str) -> list[str]:
        """Integrity of a saved index without the documents: the stored hashes match the stored content."""
        d = json.loads(data)
        errs = []
        body = {"manifest": d.get("manifest"), "postings": d.get("postings")}
        if d.get("file_sha256") != _sha(body):
            errs.append("file_sha256 does not match the content")
        if body["manifest"] and body["manifest"].get("postings_sha256") != _sha(body["postings"]):
            errs.append("postings_sha256 does not match the postings")
        return errs

    @classmethod
    def from_json(cls, data: str, documents: Iterable[Document]) -> LexicalIndex:
        """Rebuild from the documents and the saved settings; refuse if anything differs."""
        errs = cls.check_json(data)
        if errs:
            raise ValueError("saved index is corrupt: " + "; ".join(errs))
        s = json.loads(data)["manifest"]["settings"]
        idx = cls(documents, s["max_chars"], s["overlap"], s["strip_al"], s["dedupe"])
        problems = verify(data, idx)
        if problems:
            raise ValueError("saved index does not match the documents: " + "; ".join(problems))
        return idx


def verify(saved: str, rebuilt: LexicalIndex) -> list[str]:
    """Every difference between a saved index and one rebuilt from the documents (empty list: identical)."""
    errs = LexicalIndex.check_json(saved)
    m, r = json.loads(saved)["manifest"], rebuilt.manifest()
    for key in ("settings", "corpus_sha256", "postings_sha256", "n_chunks", "n_terms", "duplicates"):
        if m.get(key) != r.get(key):
            errs.append(f"{key} differs")
    old = {c["chunk_id"]: c for c in m.get("chunks", [])}
    new = {c["chunk_id"]: c for c in r["chunks"]}
    for cid in sorted(set(old) | set(new)):
        if old.get(cid) != new.get(cid):
            errs.append(f"chunk {cid} differs")
    return errs


def build(documents: Iterable[Document], **kw) -> LexicalIndex:
    return LexicalIndex(documents, **kw)


__all__ = ["Hit", "LexicalIndex", "analyze", "build", "verify"]
