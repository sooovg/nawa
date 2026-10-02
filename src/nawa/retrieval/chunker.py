"""Deterministic text chunker (ROADMAP P6-01, ADR-0008).

A document is split into sentences, and sentences are packed into chunks of at most ``max_chars`` characters (code
points). A sentence ends at ``. ! ? ؟ ؛ …`` or at a blank line. A dot between two digits is a decimal point, not an
end; Python's ``\\d`` also matches Arabic-Indic digits, so ``٣.٥`` is kept whole.

* A sentence longer than ``max_chars`` is split at whitespace.
* A word longer than ``max_chars`` is cut. The cut never falls before a combining mark (Arabic harakat included), a
  zero-width joiner or a variation selector, or right after a joiner. So a letter is never separated from its marks.
* A blank line ends a paragraph, and a chunk never spans two paragraphs.
* ``overlap`` repeats the last ``overlap`` sentences of a chunk at the start of the next one, when they fit, within
  the same paragraph.

Invariants (tested):
- every chunk is ``text[start:end]`` of the original, not normalised;
- no chunk is empty or longer than ``max_chars``;
- with ``overlap=0``, every non-space character belongs to exactly one chunk, in order;
- the output depends only on the input.

Chunk ids are ``<doc_id>#<n>``.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass

from nawa.retrieval.metadata import Document

_END = re.compile(r"(?<!\d)\.|\.(?!\d)|[!?؟؛…]|\n\s*\n")
_JOINERS = {"\u200d", "\u200c", "\u2060"}


def _breakable(text: str, i: int) -> bool:
    """May a hard cut fall between text[i-1] and text[i]?"""
    if i <= 0 or i >= len(text):
        return True
    nxt, prev = text[i], text[i - 1]
    if unicodedata.combining(nxt) or unicodedata.category(nxt) == "Mn" or nxt in _JOINERS:
        return False
    if "\ufe00" <= nxt <= "\ufe0f" or prev in _JOINERS:
        return False
    if 0xD800 <= ord(nxt) <= 0xDFFF:
        return False
    return True


def _sentences(text: str) -> list[tuple[int, int, int]]:
    """(start, end, paragraph) of each sentence, trimmed of surrounding whitespace."""
    spans, pos, para = [], 0, 0
    for m in _END.finditer(text):
        blank = m.group().startswith("\n")
        spans.append((pos, m.start() if blank else m.end(), para))
        para += blank
        pos = m.end()
    spans.append((pos, len(text), para))
    out = []
    for s, e, p in spans:
        while s < e and text[s].isspace():
            s += 1
        while e > s and text[e - 1].isspace():
            e -= 1
        if s < e:
            out.append((s, e, p))
    return out


def _split_long(text: str, s: int, e: int, max_chars: int) -> list[tuple[int, int]]:
    """Split one span at whitespace, cutting words only when a single word is too long."""
    out = []
    while e - s > max_chars:
        cut = -1
        for i in range(s + max_chars, s, -1):
            if text[i - 1].isspace() or text[i].isspace():
                cut = i
                break
        if cut == -1:
            cut = s + max_chars
            while cut > s + 1 and not _breakable(text, cut):
                cut -= 1
            if cut == s + 1 and not _breakable(text, cut):   # pathological: one base with > max_chars marks
                cut = s + max_chars
        a, b = s, cut
        while b > a and text[b - 1].isspace():
            b -= 1
        if a < b:
            out.append((a, b))
        s = cut
        while s < e and text[s].isspace():
            s += 1
    if s < e:
        out.append((s, e))
    return out


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    doc_id: str
    start: int
    end: int
    text: str

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()


def chunk_document(doc: Document, max_chars: int = 400, overlap: int = 0) -> list[Chunk]:
    if isinstance(max_chars, bool) or not isinstance(max_chars, int) or not 8 <= max_chars <= 100_000:
        raise ValueError("max_chars must be an int in 8..100000")
    if isinstance(overlap, bool) or not isinstance(overlap, int) or not 0 <= overlap <= 8:
        raise ValueError("overlap must be an int in 0..8")
    text = doc.text
    units: list[tuple[int, int, int]] = []
    for s, e, p in _sentences(text):
        parts = _split_long(text, s, e, max_chars) if e - s > max_chars else [(s, e)]
        units.extend((a, b, p) for a, b in parts)
    groups: list[list[tuple[int, int, int]]] = []
    cur: list[tuple[int, int, int]] = []
    for u in units:
        new_para = bool(cur) and u[2] != cur[-1][2]
        if cur and (new_para or u[1] - cur[0][0] > max_chars):
            groups.append(cur)
            carry = [] if new_para or not overlap else cur[-overlap:]
            while carry and u[1] - carry[0][0] > max_chars:
                carry = carry[1:]
            cur = list(carry)
        cur.append(u)
    if cur:
        groups.append(cur)
    out = []
    for n, g in enumerate(groups):
        s, e = g[0][0], g[-1][1]
        out.append(Chunk(f"{doc.doc_id}#{n}", doc.doc_id, s, e, text[s:e]))
    return out
