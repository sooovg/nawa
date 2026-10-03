"""Shared synthetic fixtures for the memory tests (P7-05). Invented words and the three synthetic users only."""

from __future__ import annotations

from nawa.memory import MemoryKind, MemoryStore, Principal, Provenance, SourceType, LogicalClock
from nawa.verification.states import VerificationState

ALPHA, BETA, GAMMA = Principal("user_alpha"), Principal("user_beta"), Principal("user_gamma")
USERS = (ALPHA, BETA, GAMMA)


def pv(ref: str = "synthetic:test/1", t: int = 0, src: SourceType = SourceType.USER_STATED, author: str = "user_alpha",
       evidence: str | None = None, derived=()) -> Provenance:
    return Provenance(src, ref, author, t, evidence, tuple(derived))


def new_store(directory=None) -> MemoryStore:
    return MemoryStore(LogicalClock(0), directory)


def put(store: MemoryStore, who: Principal, kind: MemoryKind, content: str, **kw):
    """Write with valid defaults for each kind."""
    now = store.clock.now()
    defaults: dict = {"confidence": 0.9}
    if kind is MemoryKind.KNOWLEDGE:
        defaults.update(verification_state=VerificationState.SUPPORTED,
                        provenance=pv(f"synthetic:doc/{len(content)}", now, SourceType.SYNTHETIC_DOCUMENT,
                                      who.user_id, "synthetic:evidence/1"))
    if kind is MemoryKind.USER_PERSISTENT:
        defaults["consent"] = True
    if kind is MemoryKind.TASK:
        from nawa.memory import TaskStatus
        defaults["task_status"] = TaskStatus.OPEN
    if kind is MemoryKind.SENSORY:
        from nawa.memory import Modality
        defaults["modality"] = Modality.TEXT
    defaults.setdefault("provenance", pv("synthetic:test/put", now, author=who.user_id))
    defaults.update(kw)
    return store.write(who, kind, content, **defaults)
