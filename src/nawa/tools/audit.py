"""Append-only, tamper-evident audit log for tool calls (ROADMAP P6-02, SECURITY.md §4, ADR-0008).

Every tool call, including refused ones, is one record. Records form a hash chain: each record stores the SHA-256 of
the previous record, and its own hash covers every field. :func:`verify_chain` detects an edited, removed, inserted or
reordered record. Inputs and outputs are stored as SHA-256 hashes, plus a short preview, so the log does not become a
copy of user data. The chain detects tampering; it does not prevent it (a writer can rewrite the whole file), so the log
is evidence, not access control.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

GENESIS = "0" * 64
OUTCOMES = ("ok", "error", "denied", "timeout")
PREVIEW_CHARS = 80


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)


@dataclass(frozen=True)
class AuditRecord:
    seq: int
    time: float
    tool: str
    permission: str | None
    caller: str
    outcome: str
    reason: str
    input_sha256: str
    input_preview: str
    output_sha256: str | None
    prev_hash: str
    hash: str = ""

    def body(self) -> dict:
        d = asdict(self)
        d.pop("hash")
        return d

    def compute_hash(self) -> str:
        return hashlib.sha256(canonical(self.body()).encode("utf-8")).hexdigest()


def _preview(text: str) -> str:
    return text if len(text) <= PREVIEW_CHARS else text[:PREVIEW_CHARS] + "…"


class AuditLog:
    """In-memory chain, optionally mirrored to a JSONL file opened in append mode."""

    def __init__(self, path: Path | None = None, clock: Callable[[], float] = time.time) -> None:
        self.records: list[AuditRecord] = []
        self.path = Path(path) if path is not None else None
        self.clock = clock
        if self.path is not None and self.path.exists():
            self.records = load(self.path)
            errs = verify_chain(self.records)
            if errs:
                raise ValueError(f"existing audit log fails verification: {errs[0]}")

    @property
    def head(self) -> str:
        return self.records[-1].hash if self.records else GENESIS

    def append(self, *, tool: str, permission: str | None, caller: str, outcome: str, reason: str, payload: object,
               output: object | None) -> AuditRecord:
        if outcome not in OUTCOMES:
            raise ValueError(f"outcome must be one of {OUTCOMES}")
        text = canonical(payload)
        rec = AuditRecord(seq=len(self.records), time=float(self.clock()), tool=tool, permission=permission,
                          caller=caller, outcome=outcome, reason=reason, input_sha256=sha256_text(text),
                          input_preview=_preview(text),
                          output_sha256=None if output is None else sha256_text(canonical(output)),
                          prev_hash=self.head)
        rec = AuditRecord(**{**rec.body(), "hash": rec.compute_hash()})
        self.records.append(rec)
        if self.path is not None:
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(canonical(asdict(rec)) + "\n")
        return rec


def load(path: Path) -> list[AuditRecord]:
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return [AuditRecord(**json.loads(line)) for line in lines if line.strip()]


def verify_chain(records: list[AuditRecord]) -> list[str]:
    """Return a list of problems; empty means the chain is intact."""
    errs, prev = [], GENESIS
    for i, r in enumerate(records):
        if r.seq != i:
            errs.append(f"record {i}: seq {r.seq} != {i}")
        if r.prev_hash != prev:
            errs.append(f"record {i}: prev_hash does not match the previous record")
        if r.hash != r.compute_hash():
            errs.append(f"record {i}: hash does not match its content")
        if r.outcome not in OUTCOMES:
            errs.append(f"record {i}: unknown outcome {r.outcome!r}")
        prev = r.hash
    return errs
