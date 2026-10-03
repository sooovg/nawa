"""Real forgetting with a permanent, hash-chained log (ROADMAP P7-05, ADR-0009).

Each deletion or expiry appends ``{id, type, owner, reason, timestamp, hash, prev_hash}``:
- ``hash`` is SHA-256 over the canonical JSON of the other six fields, so ``hash`` chains every entry to the one before
  it (``prev_hash`` of the first entry is 64 zeros). Editing, removing or reordering any entry breaks ``verify``.
- The log never contains the forgotten content or a hash of it (a content hash of short text can be reversed by
  guessing). ``reason`` is a code from a closed vocabulary, so free text cannot leak through it.

``trace_scan`` is the check that deletion is not cosmetic: it serialises every structure of the store (items, version
history, token index, association index, read cache, summary cache) and, optionally, every file of a persisted store,
and reports where a forgotten id or content string still appears. The forgetting log is the only place an id may
remain.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path

GENESIS = "0" * 64
_REASON = re.compile(r"^(user_request|expired_ttl|consolidated|session_end|policy|cascade:mem-[0-9a-f]{16})$")


class LogIntegrityError(RuntimeError):
    pass


@dataclass(frozen=True)
class ForgetEntry:
    id: str
    type: str
    owner: str
    reason: str
    timestamp: str
    prev_hash: str
    hash: str


def _canonical(d: dict) -> bytes:
    return json.dumps(d, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def entry_hash(id: str, type: str, owner: str, reason: str, timestamp: str, prev_hash: str) -> str:
    return hashlib.sha256(_canonical({"id": id, "type": type, "owner": owner, "reason": reason,
                                      "timestamp": timestamp, "prev_hash": prev_hash})).hexdigest()


def valid_reason(reason: str) -> bool:
    return isinstance(reason, str) and bool(_REASON.match(reason))


class ForgettingLog:
    """Append-only log. With a ``path`` every entry is appended to a JSONL file and fsynced; an existing file is
    loaded and verified first, and a broken chain raises ``LogIntegrityError``."""

    def __init__(self, path: Path | str | None = None):
        self.path = Path(path) if path is not None else None
        self._entries: list[ForgetEntry] = []
        if self.path is not None and self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    self._entries.append(ForgetEntry(**json.loads(line)))
            errs = self.verify()
            if errs:
                raise LogIntegrityError("; ".join(errs))

    @property
    def entries(self) -> tuple[ForgetEntry, ...]:
        return tuple(self._entries)

    @property
    def head(self) -> str:
        return self._entries[-1].hash if self._entries else GENESIS

    def append(self, item_id: str, kind: str, owner: str, reason: str, timestamp: str) -> ForgetEntry:
        if not valid_reason(reason):
            raise ValueError("reason_not_in_vocabulary")
        prev = self.head
        e = ForgetEntry(item_id, kind, owner, reason, timestamp, prev,
                        entry_hash(item_id, kind, owner, reason, timestamp, prev))
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(e), sort_keys=True, ensure_ascii=False) + "\n")
                f.flush()
                os.fsync(f.fileno())
        self._entries.append(e)
        return e

    def verify(self) -> list[str]:
        errs, prev = [], GENESIS
        for i, e in enumerate(self._entries):
            if e.prev_hash != prev:
                errs.append(f"entry {i}: prev_hash mismatch")
            if e.hash != entry_hash(e.id, e.type, e.owner, e.reason, e.timestamp, e.prev_hash):
                errs.append(f"entry {i}: hash mismatch")
            if not valid_reason(e.reason):
                errs.append(f"entry {i}: reason not in vocabulary")
            prev = e.hash
        return errs

    def forgotten_ids(self) -> frozenset[str]:
        return frozenset(e.id for e in self._entries)


def trace_scan(store, *, needles: list[str], directory: Path | str | None = None) -> list[str]:
    """Locations where any needle (a forgotten id or content string) still appears. Empty means no trace.

    Looks in every in-process structure of ``store`` (``store.dump_state(include_log=False)``) and in every file under
    ``directory`` except the forgetting log, where an id is expected to remain (content never is)."""
    found: list[str] = []
    state = store.dump_state(include_log=False)
    for section, value in state.items():
        text = json.dumps(value, sort_keys=True, ensure_ascii=False)
        for n in needles:
            if n and n in text:
                found.append(f"state:{section}")
    if directory is not None:
        for p in sorted(Path(directory).rglob("*")):
            if not p.is_file():
                continue
            data = p.read_bytes()
            for n in needles:
                if not n:
                    continue
                if p.name == "forget_log.jsonl" and n.startswith("mem-"):
                    continue
                if n.encode("utf-8") in data:
                    found.append(f"file:{p.name}")
    return sorted(set(found))
