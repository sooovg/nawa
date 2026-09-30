"""Evaluation item schema (P1-02). One JSON object per item."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any

SUITES = ("faithfulness", "abstention", "factual", "reasoning_math", "code",
          "tool_use", "robustness", "arabic", "regression_general")
BLOCKED_SUITES = {"domain": "OD-01 first domain not decided"}
SPLITS = ("dev", "calib", "frozen")
LICENSE = "NAWA-authored evaluation data (synthetic/authored 2026-09-30); license per OD-03"


@dataclass
class Item:
    suite: str
    split: str
    messages: list[dict[str, str]]
    gold: dict[str, Any]
    meta: dict[str, Any] = field(default_factory=dict)
    max_new_tokens: int = 64
    id: str = ""

    def __post_init__(self) -> None:
        if self.suite not in SUITES:
            raise ValueError(f"unknown suite {self.suite}")
        if self.split not in SPLITS:
            raise ValueError(f"unknown split {self.split}")
        if not self.messages or self.messages[-1]["role"] != "user":
            raise ValueError("messages must end with a user turn")
        self.meta.setdefault("license", LICENSE)
        if not self.id:
            self.id = f"{self.suite}-{self.content_hash()[:12]}"

    def content_hash(self) -> str:
        """Hash of what the model sees: used for de-duplication and leakage checks."""
        payload = json.dumps(self.messages, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, sort_keys=True)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Item":
        return cls(**d)
