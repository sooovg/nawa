"""Routes memory requests to the store, the policy and consolidation (ROADMAP P7-05, ADR-0009).

``handle(principal, request)`` takes a plain dict ``{"op": ..., ...}`` and dispatches it through a fixed routing table.
An unknown operation is refused, never guessed. Each route picks the memory kind and the provenance source type, so
callers cannot, for example, store a conversation turn as verified knowledge.
"""

from __future__ import annotations

from nawa.memory import consolidation
from nawa.memory.isolation import Principal
from nawa.memory.provenance import Provenance, SourceType
from nawa.memory.store import MemoryStore
from nawa.memory.types import MemoryKind, Modality, TaskStatus
from nawa.verification.states import VerificationState


class UnknownOperation(ValueError):
    pass


class MemoryOrchestrator:
    ROUTES = {
        "ingest": "ingest", "turn": "turn", "learn_fact": "learn_fact", "start_task": "start_task",
        "update_task": "update_task", "recall": "recall", "associate": "associate", "forget": "forget",
        "consolidate": "consolidate", "end_session": "end_session", "due": "due", "introspect": "introspect",
        "summary": "summary",
    }

    def __init__(self, store: MemoryStore):
        self.store = store

    def handle(self, principal: Principal, request: dict):
        op = request.get("op")
        if op not in self.ROUTES:
            raise UnknownOperation(str(op))
        args = {k: v for k, v in request.items() if k != "op"}
        return getattr(self, self.ROUTES[op])(principal, **args)

    def _prov(self, principal: Principal, source: SourceType, ref: str, evidence: str | None = None) -> Provenance:
        return Provenance(source, ref, principal.user_id if source is SourceType.USER_STATED else "nawa:system",
                          self.store.clock.now(), evidence)

    # sensory buffers (short TTL)
    def ingest(self, principal, modality: str, payload: str, ref: str, confidence: float = 1.0, tags=()):
        return self.store.write(principal, MemoryKind.SENSORY, payload,
                                provenance=self._prov(principal, SourceType.SENSOR, ref), confidence=confidence,
                                modality=Modality(modality), tags=tuple(tags))

    # conversation
    def turn(self, principal, text: str, ref: str, remember: bool = False, consent: bool = False,
             confidence: float = 1.0):
        tags = ("remember",) if remember else ()
        return self.store.write(principal, MemoryKind.CONVERSATION, text,
                                provenance=self._prov(principal, SourceType.USER_STATED, ref),
                                confidence=confidence, consent=consent, tags=tags)

    # knowledge
    def learn_fact(self, principal, text: str, ref: str, evidence: str, state: str, confidence: float,
                   fact_key=None, tags=()):
        return self.store.write(principal, MemoryKind.KNOWLEDGE, text,
                                provenance=self._prov(principal, SourceType.SYNTHETIC_DOCUMENT, ref, evidence),
                                confidence=confidence, verification_state=VerificationState(state),
                                fact_key=tuple(fact_key) if fact_key else None, tags=tuple(tags))

    # tasks
    def start_task(self, principal, goal: str, ref: str, steps=(), due_at: int | None = None,
                   confidence: float = 1.0):
        return self.store.write(principal, MemoryKind.TASK, goal,
                                provenance=self._prov(principal, SourceType.TASK_EXECUTION, ref),
                                confidence=confidence, task_status=TaskStatus.OPEN, steps=tuple(steps),
                                due_at=due_at)

    def update_task(self, principal, item_id: str, status: str, ref: str, steps=None):
        old = self.store.read(principal, item_id)
        if old is None:
            raise KeyError("not_found")
        return self.store.update(principal, item_id, old.content,
                                 provenance=self._prov(principal, SourceType.TASK_EXECUTION, ref),
                                 task_status=TaskStatus(status), steps=tuple(steps) if steps is not None else None)

    # read side
    def recall(self, principal, query: str, **filters):
        if "kinds" in filters and filters["kinds"] is not None:
            filters["kinds"] = tuple(MemoryKind(k) for k in filters["kinds"])
        return self.store.search(principal, query, **filters)

    def associate(self, principal, item_id: str, limit: int = 10):
        return self.store.associate(principal, item_id, limit)

    def due(self, principal):
        return self.store.due_tasks(principal)

    def introspect(self, principal):
        return self.store.introspect(principal)

    def summary(self, principal, kind: str | None = None):
        return self.store.summarize(principal, MemoryKind(kind) if kind else None)

    # lifecycle
    def forget(self, principal, item_id: str):
        return self.store.forget(principal, item_id, reason="user_request")

    def consolidate(self, principal):
        return consolidation.apply(self.store, principal)

    def end_session(self, principal):
        """Consolidate, then forget every remaining conversation and sensory item of the session (logged)."""
        created, retired = consolidation.apply(self.store, principal)
        forgotten = []
        for it in self.store.scan(principal, (MemoryKind.CONVERSATION, MemoryKind.SENSORY)):
            forgotten += self.store.forget(principal, it.item_id, reason="session_end")
        return {"created": [c.item_id for c in created], "retired": retired,
                "forgotten": [e.id for e in forgotten]}
