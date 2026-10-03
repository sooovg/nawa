"""Deterministic replay and the memory self-check (ROADMAP P7-05, ADR-0009).

``synthetic_ops(seed, n)`` makes a reproducible operation script for the three synthetic users from a fixed seed and a
vocabulary of invented words (no real text). ``run(ops)`` applies it to a fresh store with a logical clock, and
``digest(ops)`` returns the store's ``state_digest``. The same script always gives the same digest, in any process and
under any ``PYTHONHASHSEED``.

``selfcheck`` is what CI runs (``python -m nawa.memory.replay --check``):
- determinism: two independent runs of the same script give the same digest, and consolidation run twice is a no-op;
- isolation: for every pair of distinct synthetic users, nothing the first one wrote is visible to the second through
  read, scan, search, associate, summaries or due tasks;
- no leak after deletion: every forgotten item is absent from read, scan, search, associate, summaries and every
  in-process structure including caches (``trace_scan``), and from the files of a persisted store;
- the forgetting log chain verifies.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import tempfile
from pathlib import Path

from nawa.memory import consolidation
from nawa.memory.forgetting import trace_scan
from nawa.memory.isolation import SYNTHETIC_USERS, Principal
from nawa.memory.provenance import Provenance, SourceType
from nawa.memory.store import LogicalClock, MemoryStore
from nawa.memory.types import MemoryKind, Modality, TaskStatus

SEED = 7
# Invented words only. Each written item also gets a unique marker "zq<5 digits>x" so a leak can be detected by search.
VOCAB = ("brelto", "kavun", "mirsel", "tobrak", "elvanu", "qisto", "dorvel", "nupra", "salvek", "yorin", "fendra",
         "glomir")


def marker(i: int) -> str:
    return f"zq{i:05d}x"


def synthetic_ops(seed: int = SEED, n: int = 200) -> list[dict]:
    rng = random.Random(seed)
    ops: list[dict] = []
    written = 0
    owners: list[str] = []
    for _ in range(n):
        r = rng.random()
        if r < 0.55 or written == 0:
            user = rng.choice(SYNTHETIC_USERS)
            kind = rng.choice(("conversation", "user_persistent", "task", "knowledge", "procedural", "sensory"))
            words = " ".join(rng.choice(VOCAB) for _ in range(3))
            ops.append({"op": "write", "user": user, "kind": kind, "content": f"{words} {marker(written)}",
                        "confidence": round(rng.uniform(0.3, 1.0), 3),
                        "remember": rng.random() < 0.3})
            owners.append(user)
            written += 1
        elif r < 0.70:
            ops.append({"op": "advance", "seconds": rng.randint(1, 5)})
        elif r < 0.82:
            ops.append({"op": "forget", "ref": rng.randrange(written)})
        elif r < 0.90:
            ops.append({"op": "update", "ref": rng.randrange(written), "suffix": rng.choice(VOCAB)})
        elif r < 0.96:
            ops.append({"op": "consolidate", "user": rng.choice(SYNTHETIC_USERS)})
        else:
            ops.append({"op": "expire"})
    return ops


def _write(store: MemoryStore, op: dict, i: int):
    pr = Principal(op["user"])
    kind = MemoryKind(op["kind"])
    now = store.clock.now()
    src = {MemoryKind.SENSORY: SourceType.SENSOR, MemoryKind.KNOWLEDGE: SourceType.SYNTHETIC_DOCUMENT,
           MemoryKind.TASK: SourceType.TASK_EXECUTION, MemoryKind.PROCEDURAL: SourceType.TASK_EXECUTION}.get(
        kind, SourceType.USER_STATED)
    evidence = f"synthetic:evidence/{i}" if kind is MemoryKind.KNOWLEDGE else None
    kw: dict = {}
    if kind is MemoryKind.KNOWLEDGE:
        from nawa.verification.states import VerificationState
        kw["verification_state"] = VerificationState.SUPPORTED if i % 2 == 0 else VerificationState.UNCERTAIN
        kw["fact_key"] = (op["content"].split()[0], "attr")
    if kind is MemoryKind.USER_PERSISTENT or (kind is MemoryKind.CONVERSATION and op.get("remember")):
        kw["consent"] = True
    if kind is MemoryKind.CONVERSATION and op.get("remember"):
        kw["tags"] = ("remember",)
    if kind is MemoryKind.SENSORY:
        kw["modality"] = (Modality.TEXT, Modality.VISUAL, Modality.AUDIO, Modality.TACTILE)[i % 4]
        kw["tags"] = ("attend",) if op.get("remember") else ()
    if kind is MemoryKind.TASK:
        kw["task_status"] = TaskStatus.DONE if op.get("remember") else TaskStatus.OPEN
        kw["steps"] = ("step one", "step two")
    return store.write(pr, kind, op["content"], provenance=Provenance(src, f"synthetic:replay/{i}", op["user"], now,
                                                                      evidence),
                       confidence=op["confidence"], **kw)


def run(ops: list[dict], directory: Path | None = None) -> tuple[MemoryStore, list]:
    """Apply a script to a fresh store. Returns the store and, per write, (principal, item_id, content)."""
    store = MemoryStore(LogicalClock(0), directory)
    written: list = []
    for op in ops:
        kind = op["op"]
        if kind == "write":
            it = _write(store, op, len(written))
            written.append((Principal(op["user"]), it.item_id, op["content"]))
        elif kind == "advance":
            store.clock.advance(op["seconds"])
        elif kind == "forget":
            pr, item_id, _ = written[op["ref"]]
            if store.read(pr, item_id) is not None:
                store.forget(pr, item_id, reason="user_request")
        elif kind == "update":
            pr, item_id, content = written[op["ref"]]
            it = store.read(pr, item_id)
            if it is not None and it.kind is not MemoryKind.SENSORY:
                n = it.version + 1
                ev = f"synthetic:evidence/{item_id}/v{n}" if it.kind is MemoryKind.KNOWLEDGE else None
                store.update(pr, item_id, f"{it.content} {op['suffix']}",
                             provenance=Provenance(it.provenance.source_type, f"synthetic:replay/update/{n}",
                                                   pr.user_id, store.clock.now(), ev,
                                                   it.provenance.derived_from))
        elif kind == "consolidate":
            consolidation.apply(store, Principal(op["user"]))
        elif kind == "expire":
            store.expire()
        else:
            raise ValueError(f"unknown op {kind}")
    return store, written


def digest(ops: list[dict]) -> str:
    return run(ops)[0].state_digest()


def _visible_markers(store: MemoryStore, pr: Principal) -> set[str]:
    """Every marker a principal can reach through any read path."""
    text = []
    for it in store.scan(pr):
        text.append(it.content)
        text += [h.item.content for h in store.associate(pr, it.item_id, limit=1000)]
    for w in VOCAB:
        text += [h.item.content for h in store.search(pr, w, limit=1000)]
    text.append(store.summarize(pr))
    text += [it.content for it in store.due_tasks(pr)]
    return {tok for t in text for tok in t.split() if tok.startswith("zq") and tok.endswith("x")}


def selfcheck(seed: int = SEED, n: int = 300) -> dict:
    ops = synthetic_ops(seed, n)
    d1, d2 = digest(ops), digest(ops)
    store, written = run(ops)
    # consolidation is idempotent on a stable state
    before = store.state_digest()
    for u in SYNTHETIC_USERS:
        created, retired = consolidation.apply(store, Principal(u))
        if created or retired:
            consolidation.apply(store, Principal(u))
    after1 = store.state_digest()
    for u in SYNTHETIC_USERS:
        consolidation.apply(store, Principal(u))
    idempotent = store.state_digest() == after1
    # isolation over every ordered pair of distinct users
    own: dict[str, set[str]] = {u: set() for u in SYNTHETIC_USERS}
    for pr, _, content in written:
        own[pr.user_id].add(content.split()[-1])
    leaks = []
    for u in SYNTHETIC_USERS:
        seen = _visible_markers(store, Principal(u))
        for v in SYNTHETIC_USERS:
            if v != u and seen & own[v]:
                leaks.append(f"{v}->{u}:{len(seen & own[v])}")
        for pr, item_id, _ in written:
            if pr.user_id != u and store.read(Principal(u), item_id) is not None:
                leaks.append(f"read:{pr.user_id}->{u}")
    # no trace after deletion: forget every third surviving item by user request, then scan everything
    with tempfile.TemporaryDirectory() as tmp:
        pstore, pwritten = run(ops, Path(tmp))
        targets = [(pr, i, c) for pr, i, c in pwritten if pstore.read(pr, i) is not None][::3]
        needles = []
        for pr, item_id, content in targets:
            if pstore.read(pr, item_id) is not None:
                for e in pstore.forget(pr, item_id, reason="user_request"):
                    needles.append(e.id)
                needles.append(content.split()[-1])
        traces = trace_scan(pstore, needles=needles, directory=tmp)
        reachable = set()
        for u in SYNTHETIC_USERS:
            reachable |= _visible_markers(pstore, Principal(u)) & set(needles)
        log_ok = not pstore.log.verify()
    ok = d1 == d2 and idempotent and not leaks and not traces and not reachable and log_ok
    return {"ok": ok, "seed": seed, "ops": n, "digest": d1, "deterministic": d1 == d2,
            "consolidation_idempotent": idempotent, "changed_by_first_consolidation": before != after1,
            "isolation_leaks": leaks, "forgotten_checked": len(needles), "traces_after_forget": traces,
            "reachable_after_forget": sorted(reachable), "log_chain_ok": log_ok,
            "od12": "OPEN: synthetic users only; no real memory before the owner decides OD-12"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="NAWA memory deterministic replay and self-check (synthetic only)")
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--ops", type=int, default=300)
    ap.add_argument("--check", action="store_true", help="run determinism, isolation and no-leak checks")
    a = ap.parse_args(argv)
    if a.check:
        res = selfcheck(a.seed, a.ops)
        print(json.dumps(res, indent=2, sort_keys=True))
        return 0 if res["ok"] else 1
    print(digest(synthetic_ops(a.seed, a.ops)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
