"""NAWA retrieval (ROADMAP P6-01; code-only scope, ADR-0008): chunker, lexical BM25 index (rebuildable and
verifiable), freshness and source-quality metadata used as filters, and a rule-based lexical reranker.

Not a final RAG system: no dense embeddings, learned reranker, real corpus or generation (P6-01a, BLOCKED until OD-03
and a trained core). Tested on synthetic text only.
"""

from nawa.retrieval.chunker import Chunk, chunk_document
from nawa.retrieval.index import Hit, LexicalIndex, analyze, build, verify
from nawa.retrieval.metadata import Document, Filter, SourceQuality, parse_date
from nawa.retrieval.rerank import LexicalReranker, Reranker, apply_reranker, to_evidence

__all__ = ["Chunk", "Document", "Filter", "Hit", "LexicalIndex", "LexicalReranker", "Reranker", "SourceQuality",
           "analyze", "apply_reranker", "build", "chunk_document", "parse_date", "to_evidence", "verify"]
