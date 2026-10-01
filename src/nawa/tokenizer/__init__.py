"""NAWA tokenizer candidates (ROADMAP P3-01) and their measurement (P3-02). Track S: written from
scratch, no external tokenizer library and no external vocabulary.

Every candidate is lossless: ``decode(encode(text)) == text`` for any Unicode string, through byte
fallback. Candidates are compared by `nawa.tokenizer.metrics`; choosing one is P3-03, which waits for
a licensed real corpus (ADR-0006), so nothing here selects a tokenizer.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Protocol


class Tokenizer(Protocol):
    name: str

    @property
    def vocab_size(self) -> int: ...

    def encode(self, text: str) -> list[int]: ...

    def decode(self, ids: list[int]) -> str: ...

    def to_dict(self) -> dict[str, Any]: ...


def fingerprint(tok: Tokenizer) -> str:
    return hashlib.sha256(json.dumps(tok.to_dict(), ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def save(tok: Tokenizer, path: Path) -> None:
    if path.exists():
        raise FileExistsError(f"{path} exists; tokenizers are written to a new file, never overwritten")
    path.write_text(json.dumps(tok.to_dict(), ensure_ascii=False, sort_keys=True), encoding="utf-8")


def from_dict(d: dict[str, Any]) -> Tokenizer:
    from nawa.tokenizer.bpe import BPETokenizer
    from nawa.tokenizer.byte import ByteTokenizer
    from nawa.tokenizer.unigram import UnigramTokenizer

    kind = d.get("type")
    if kind == "byte":
        return ByteTokenizer()
    if kind == "bpe":
        return BPETokenizer.from_dict(d)
    if kind == "unigram":
        return UnigramTokenizer.from_dict(d)
    raise ValueError(f"unknown tokenizer type {kind!r}")


def load(path: Path) -> Tokenizer:
    return from_dict(json.loads(path.read_text(encoding="utf-8")))
