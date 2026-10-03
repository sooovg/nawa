"""Unified memory store (ROADMAP P7-05, ADR-0009).

Interface: ``write``, ``read``, ``search``, ``update``, ``forget``, ``expire``, ``provenance``, ``confidence``, ``acl``,
``version`` — plus ``versions``, ``scan``, ``associate``, ``summarize``, ``due_tasks``, ``introspect``,
``dump_state`` and ``state_digest``.

Design:
- **Isolation by construction.** One partition per (user, project). Every call takes a ``Principal`` and touches only
  that partition; every returned item is checked again with ``isolation.can_access``. Reading another user's id
  behaves exactly like reading an id that does not exist, so ids cannot be probed.
- **Determinism.** Time is a ``LogicalClock`` the caller advances; ids are SHA-256 of (owner, project, kind,
  per-partition sequence, tick) and never of content; every listing has a total order; serialisation is canonical.
  The same operations on a fresh store give the same ``state_digest``.
- **Real forgetting.** ``forget`` removes an item and all its versions from every structure: items, version history,
  token index, association index, read cache and summary cache, and, when the store is persisted, rewrites the data
  file atomically. A user deletion cascades through the item's consolidation lineage (its sources and every item
  derived from it), because consolidation copies content. Each removal is written to
  the hash-chained ``ForgettingLog``. ``forgetting.trace_scan`` verifies that nothing remains.

Limits (stated, not hidden): Python may keep freed strings in process memory until garbage collection, and a filesystem
may keep old blocks after a file is replaced; this store does not claim secure erasure of RAM or disk blocks. Search is
lexical token overlap, not semantic. Synthetic users only: OD-12 must be decided before any real memory.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field, replace
from pathlib import Path

from nawa.memory import policy
from nawa.memory import provenance as prov
from nawa.memory.forgetting import ForgetEntry, ForgettingLog, valid_reason
from nawa.memory.isolation import Principal, acl as _acl, can_access
from nawa.memory.types import MemoryItem, MemoryKind, TaskStatus, iso
from nawa.retrieval.index import analyze
from nawa.verification.states import VerificationState

SCHEMA = 1
DATA_FILE = "memory_items.json"
LOG_FILE = "forget_log.jsonl"


class LogicalClock:
    """Deterministic time in integer seconds from ``types.EPOCH``. Never reads the wall clock."""

    def __init__(self, start: int = 0):
        self._t = int(start)

    def now(self) -> int:
        return self._t

    def advance(self, seconds: int = 1) -> int:
        if not isinstance(seconds, int) or seconds < 0:
            raise ValueError("clock_cannot_go_back")
        self._t += seconds
        return self._t


@dataclass(frozen=True)
class Hit:
    item: MemoryItem
    score: int


@dataclass
class _Partition:
    seq: int = 0
    items: dict[str, MemoryItem] = field(default_factory=dict)
    history: dict[str, list[MemoryItem]] = field(default_factory=dict)   # earlier versions, oldest first
    tokens: dict[str, set[str]] = field(default_factory=dict)            # token -> item ids
    subjects: dict[str, set[str]] = field(default_factory=dict)          # fact_key subject -> item ids
    cache: dict[str, object] = field(default_factory=dict)               # read/search/associate results
    summaries: dict[str, str] = field(default_factory=dict)

    def invalidate(self) -> None:
        self.cache.clear()
        self.summaries.clear()


def _order(it: MemoryItem) -> tuple:
    return (it.created_at, it.item_id)


class MemoryStore:
    def __init__(self, clock: LogicalClock | None = None, directory: Path | str | None = None):
        self.clock = clock or LogicalClock()
        self.directory = Path(directory) if directory is not None else None
        self.log = ForgettingLog(self.directory / LOG_FILE if self.directory else None)
        self._parts: dict[tuple[str, str], _Partition] = {}
        if self.directory is not None and (self.directory / DATA_FILE).exists():
            self._load()

    # ------------------------------------------------------------------ internals
    def _part(self, principal: Principal, create: bool = False) -> _Partition | None:
        if not isinstance(principal, Principal):
            raise TypeError("principal_required")
        p = self._parts.get(principal.partition)
        if p is None and create:
            p = self._parts[principal.partition] = _Partition()
        return p

    def _index(self, p: _Partition, it: MemoryItem) -> None:
        for t in set(analyze(it.content)) | {x for s in it.steps for x in analyze(s)}:
            p.tokens.setdefault(t, set()).add(it.item_id)
        if it.fact_key:
            p.subjects.setdefault(it.fact_key[0], set()).add(it.item_id)

    def _unindex(self, p: _Partition, item_id: str) -> None:
        for d in (p.tokens, p.subjects):
            for key in [k for k, ids in d.items() if item_id in ids]:
                d[key].discard(item_id)
                if not d[key]:
                    del d[key]

    def _new_id(self, principal: Principal, p: _Partition, kind: MemoryKind) -> str:
        p.seq += 1
        raw = f"{principal.user_id}|{principal.project_id}|{kind.value}|{p.seq}|{self.clock.now()}"
        return "mem-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def _get(self, principal: Principal, item_id: str) -> tuple[_Partition, MemoryItem]:
        p = self._part(principal)
        it = p.items.get(item_id) if p else None
        if it is None or not can_access(principal, it):
            raise KeyError("not_found")      # same answer for "absent" and "not yours"
        return p, it

    def _persist(self) -> None:
        if self.directory is None:
            return
        self.directory.mkdir(parents=True, exist_ok=True)
        tmp = self.directory / (DATA_FILE + ".tmp")
        tmp.write_text(json.dumps(self._data_record(), sort_keys=True, ensure_ascii=False), encoding="utf-8")
        with tmp.open("rb") as f:
            os.fsync(f.fileno())
        os.replace(tmp, self.directory / DATA_FILE)

    def _data_record(self) -> dict:
        parts = {}
        for key in sorted(self._parts):
            p = self._parts[key]
            parts["|".join(key)] = {
                "seq": p.seq,
                "items": [p.items[i].to_record() for i in sorted(p.items)],
                "history": {i: [v.to_record() for v in p.history[i]] for i in sorted(p.history)},
            }
        return {"schema": SCHEMA, "clock": self.clock.now(), "partitions": parts}

    def _load(self) -> None:
        rec = json.loads((self.directory / DATA_FILE).read_text(encoding="utf-8"))
        if rec.get("schema") != SCHEMA:
            raise ValueError("schema_mismatch")
        if rec["clock"] > self.clock.now():
            self.clock.advance(rec["clock"] - self.clock.now())
        for key, pr in rec["partitions"].items():
            user, project = key.split("|")
            p = self._parts[(user, project)] = _Partition(seq=pr["seq"])
            for r in pr["items"]:
                it = MemoryItem.from_record(r)
                p.items[it.item_id] = it
                self._index(p, it)
            p.history = {i: [MemoryItem.from_record(v) for v in vs] for i, vs in pr["history"].items()}

    # ------------------------------------------------------------------ write / update
    def write(self, principal: Principal, kind: MemoryKind, content: str, *, provenance: prov.Provenance,
              confidence: float, consent: bool = False, verification_state: VerificationState | None = None,
              modality=None, tags: tuple[str, ...] = (), fact_key: tuple[str, ...] | None = None,
              task_status: TaskStatus | None = None, steps: tuple[str, ...] = (), due_at: int | None = None,
              read_only: bool = False, ttl: int | None = None,
              mutability=None) -> MemoryItem:
        req = policy.WriteRequest(kind, content, provenance, confidence, consent, verification_state, modality,
                                  tuple(tags), tuple(fact_key) if fact_key else None, task_status, tuple(steps),
                                  due_at, read_only, ttl)
        if not isinstance(principal, Principal):
            raise TypeError("principal_required")
        reasons = policy.check_write(req)
        if reasons:
            raise policy.PolicyViolation(reasons)
        p = self._part(principal, create=True)
        now = self.clock.now()
        it = MemoryItem(
            item_id=self._new_id(principal, p, kind), kind=kind, owner=principal.user_id,
            project=principal.project_id, content=content, provenance=provenance,
            confidence=prov.check_confidence(confidence), created_at=now, updated_at=now,
            expires_at=policy.expiry(req, now), modality=modality, tags=tuple(sorted(set(tags))), consent=consent,
            verification_state=verification_state, fact_key=req.fact_key, task_status=task_status,
            steps=tuple(steps), due_at=due_at, read_only=read_only,
            mutability=mutability if kind is MemoryKind.KNOWLEDGE else None)
        p.items[it.item_id] = it
        self._index(p, it)
        p.invalidate()
        self._persist()
        return it

    def update(self, principal: Principal, item_id: str, content: str, *, provenance: prov.Provenance,
               confidence: float | None = None, verification_state: VerificationState | None = None,
               task_status: TaskStatus | None = None, steps: tuple[str, ...] | None = None) -> MemoryItem:
        p, old = self._get(principal, item_id)
        reasons = policy.check_update(old, content, provenance, confidence, verification_state)
        if task_status is not None and old.kind is not MemoryKind.TASK:
            reasons.append("task_fields_only_for_task")
        if reasons:
            raise policy.PolicyViolation(sorted(set(reasons)))
        new = replace(old, content=content, provenance=provenance, updated_at=self.clock.now(),
                      version=old.version + 1,
                      confidence=prov.check_confidence(confidence) if confidence is not None else old.confidence,
                      verification_state=verification_state or old.verification_state,
                      task_status=task_status or old.task_status,
                      steps=tuple(steps) if steps is not None else old.steps)
        p.history.setdefault(item_id, []).append(old)
        self._unindex(p, item_id)
        p.items[item_id] = new
        self._index(p, new)
        p.invalidate()
        self._persist()
        return new

    # ------------------------------------------------------------------ forget / expire
    def _remove(self, p: _Partition, it: MemoryItem, reason: str) -> ForgetEntry:
        # log first: if the log refuses the entry nothing is removed, so no deletion ever goes unrecorded
        entry = self.log.append(it.item_id, it.kind.value, it.owner, reason, iso(self.clock.now()))
        del p.items[it.item_id]
        p.history.pop(it.item_id, None)
        self._unindex(p, it.item_id)
        p.invalidate()
        return entry

    def _lineage(self, p: _Partition, item_id: str) -> list[MemoryItem]:
        """Every other item in the same partition connected to ``item_id`` through consolidation lineage, in both
        directions: items derived from it and the items it was derived from, transitively, in a fixed order.
        Consolidation copies content, so a user deletion must remove every copy to leave no trace."""
        out, frontier, seen = [], [item_id], {item_id}
        while frontier:
            cur = frontier.pop(0)
            cur_item = p.items.get(cur)
            parents = set(cur_item.provenance.derived_from) if cur_item else set()
            for it in sorted(p.items.values(), key=_order):
                if it.item_id in seen:
                    continue
                if cur in it.provenance.derived_from or it.item_id in parents:
                    seen.add(it.item_id)
                    out.append(it)
                    frontier.append(it.item_id)
        return out

    def forget(self, principal: Principal, item_id: str, reason: str = "user_request") -> list[ForgetEntry]:
        """Remove an item. ``user_request`` and ``policy`` also remove its whole consolidation lineage (cascade)."""
        if not valid_reason(reason) or reason.startswith("cascade:"):
            raise ValueError("reason_not_in_vocabulary")
        p, it = self._get(principal, item_id)
        linked = self._lineage(p, item_id) if reason in {"user_request", "policy"} else []
        entries = [self._remove(p, it, reason)]
        for d in linked:
            if d.item_id in p.items:
                entries.append(self._remove(p, d, f"cascade:{item_id}"))
        self._persist()
        return entries

    def expire(self, now: int | None = None) -> list[ForgetEntry]:
        """System operation: forget every item whose ``expires_at`` has passed, in every partition, logged."""
        now = self.clock.now() if now is None else now
        entries = []
        for key in sorted(self._parts):
            p = self._parts[key]
            for it in sorted(p.items.values(), key=_order):
                if it.expires_at is not None and now >= it.expires_at:
                    entries.append(self._remove(p, it, "expired_ttl"))
        if entries:
            self._persist()
        return entries

    # ------------------------------------------------------------------ read side
    def read(self, principal: Principal, item_id: str) -> MemoryItem | None:
        p = self._part(principal)
        if p is None:
            return None
        key = f"read:{item_id}:{self.clock.now()}"
        if key in p.cache:
            return MemoryItem.from_record(p.cache[key])
        it = p.items.get(item_id)
        if it is None or not can_access(principal, it) or not policy.visible(it, self.clock.now()):
            return None       # misses are not cached, so a probed id never enters any cache
        p.cache[key] = it.to_record()
        return it

    def scan(self, principal: Principal, kinds: tuple[MemoryKind, ...] | None = None) -> list[MemoryItem]:
        p = self._part(principal)
        if p is None:
            return []
        now = self.clock.now()
        return [it for it in sorted(p.items.values(), key=_order)
                if can_access(principal, it) and policy.visible(it, now) and (kinds is None or it.kind in kinds)]

    def search(self, principal: Principal, query: str, *, kinds: tuple[MemoryKind, ...] | None = None,
               tags: tuple[str, ...] = (), min_confidence: float = 0.0, facts_only: bool = False,
               since: int | None = None, until: int | None = None, limit: int = 10) -> list[Hit]:
        p = self._part(principal)
        if p is None:
            return []
        now = self.clock.now()
        params = json.dumps([query, [k.value for k in kinds] if kinds else None, sorted(tags), min_confidence,
                             facts_only, since, until, limit, now], ensure_ascii=False)
        key = "search:" + hashlib.sha256(params.encode("utf-8")).hexdigest()   # no raw query text in the cache
        if key in p.cache:
            return [Hit(MemoryItem.from_record(r), s) for r, s in p.cache[key]]
        q = sorted(set(analyze(query)))
        scores: dict[str, int] = {}
        for t in q:
            for i in p.tokens.get(t, ()):
                scores[i] = scores.get(i, 0) + 1
        hits = []
        for i, s in scores.items():
            it = p.items[i]
            if not (can_access(principal, it) and policy.visible(it, now, min_confidence=min_confidence,
                                                                facts_only=facts_only)):
                continue
            if kinds is not None and it.kind not in kinds:
                continue
            if any(t not in it.tags for t in tags):
                continue
            if (since is not None and it.created_at < since) or (until is not None and it.created_at > until):
                continue
            hits.append(Hit(it, s))
        hits.sort(key=lambda h: (-h.score, -h.item.confidence, h.item.created_at, h.item.item_id))
        hits = hits[:limit]
        p.cache[key] = [(h.item.to_record(), h.score) for h in hits]
        return hits

    def associate(self, principal: Principal, item_id: str, limit: int = 10) -> list[Hit]:
        """Associative recall: items sharing the fact subject (score +2) or content tokens (+1 per token)."""
        p, it = self._get(principal, item_id)
        key = f"assoc:{item_id}:{limit}:{self.clock.now()}"
        if key in p.cache:
            return [Hit(MemoryItem.from_record(r), s) for r, s in p.cache[key]]
        scores: dict[str, int] = {}
        if it.fact_key:
            for i in p.subjects.get(it.fact_key[0], ()):
                scores[i] = scores.get(i, 0) + 2
        for t in set(analyze(it.content)):
            for i in p.tokens.get(t, ()):
                scores[i] = scores.get(i, 0) + 1
        scores.pop(item_id, None)
        now = self.clock.now()
        hits = [Hit(p.items[i], s) for i, s in scores.items()
                if can_access(principal, p.items[i]) and policy.visible(p.items[i], now)]
        hits.sort(key=lambda h: (-h.score, h.item.created_at, h.item.item_id))
        hits = hits[:limit]
        p.cache[key] = [(h.item.to_record(), h.score) for h in hits]
        return hits

    def summarize(self, principal: Principal, kind: MemoryKind | None = None) -> str:
        """Deterministic extractive summary of visible items (no model): one line per item, in a fixed order."""
        p = self._part(principal)
        if p is None:
            return ""
        key = f"{kind.value if kind else '*'}:{self.clock.now()}"
        if key not in p.summaries:
            items = [it for it in self.scan(principal) if kind is None or it.kind is kind]
            items.sort(key=lambda it: (it.kind.value, it.created_at, it.item_id))
            p.summaries[key] = "\n".join(f"[{it.kind.value}] {it.content[:120]}" for it in items)
        return p.summaries[key]

    def due_tasks(self, principal: Principal, now: int | None = None) -> list[MemoryItem]:
        """Prospective memory: open tasks whose ``due_at`` has come."""
        now = self.clock.now() if now is None else now
        return [it for it in self.scan(principal, (MemoryKind.TASK,))
                if it.due_at is not None and it.due_at <= now
                and it.task_status not in (TaskStatus.DONE, TaskStatus.FAILED)]

    def introspect(self, principal: Principal) -> dict:
        """Metamemory: what the store holds for this principal, without content."""
        items = self.scan(principal)
        by_kind = {k.value: sum(1 for it in items if it.kind is k) for k in MemoryKind}
        know = [it for it in items if it.kind is MemoryKind.KNOWLEDGE]
        return {
            "items": len(items), "by_kind": by_kind,
            "facts": sum(1 for it in know if it.epistemic == "fact"),
            "beliefs": sum(1 for it in know if it.epistemic == "belief"),
            "min_confidence": min((it.confidence for it in items), default=None),
            "with_provenance": sum(1 for it in items if not prov.problems(it.provenance)),
            "forgotten": sum(1 for e in self.log.entries if e.owner == principal.user_id),
        }

    # ------------------------------------------------------------------ item metadata
    def provenance(self, principal: Principal, item_id: str) -> prov.Provenance:
        return self._get(principal, item_id)[1].provenance

    def confidence(self, principal: Principal, item_id: str) -> float:
        return self._get(principal, item_id)[1].confidence

    def acl(self, principal: Principal, item_id: str) -> dict:
        return _acl(self._get(principal, item_id)[1])

    def version(self, principal: Principal, item_id: str) -> int:
        return self._get(principal, item_id)[1].version

    def versions(self, principal: Principal, item_id: str) -> list[MemoryItem]:
        p, it = self._get(principal, item_id)
        return list(p.history.get(item_id, [])) + [it]

    # ------------------------------------------------------------------ state
    def partitions(self) -> list[tuple[str, str]]:
        return sorted(self._parts)

    def dump_state(self, include_log: bool = True) -> dict:
        """Every structure the store holds, canonically ordered (used by ``trace_scan`` and ``state_digest``)."""
        def part_dump(p: _Partition, what: str):
            if what == "items":
                return [p.items[i].to_record() for i in sorted(p.items)]
            if what == "history":
                return {i: [v.to_record() for v in p.history[i]] for i in sorted(p.history)}
            if what in ("tokens", "subjects"):
                d = getattr(p, what)
                return {k: sorted(d[k]) for k in sorted(d)}
            if what == "cache":
                return {k: p.cache[k] for k in sorted(p.cache)}
            if what == "summaries":
                return {k: p.summaries[k] for k in sorted(p.summaries)}
            return p.seq
        out = {what: {"|".join(k): part_dump(self._parts[k], what) for k in sorted(self._parts)}
               for what in ("seq", "items", "history", "tokens", "subjects", "cache", "summaries")}
        out["clock"] = self.clock.now()
        if include_log:
            out["log"] = [e.__dict__ for e in self.log.entries]
        return out

    def state_digest(self) -> str:
        """SHA-256 of the durable state (items, history, indexes, sequence, clock, log); caches are excluded
        because they depend on which reads were made, not on what is stored."""
        state = self.dump_state()
        state.pop("cache")
        state.pop("summaries")
        blob = json.dumps(state, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()
