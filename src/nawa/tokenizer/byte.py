"""Byte tokenizer: the 256-symbol baseline the reference core uses until P3-03 (vocab_size=256)."""

from __future__ import annotations

from typing import Any


class ByteTokenizer:
    name = "byte"

    @property
    def vocab_size(self) -> int:
        return 256

    def encode(self, text: str) -> list[int]:
        return list(text.encode("utf-8"))

    def decode(self, ids: list[int]) -> str:
        return bytes(ids).decode("utf-8")

    def to_dict(self) -> dict[str, Any]:
        return {"type": "byte", "name": self.name}
