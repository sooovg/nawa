"""Deterministic consolidation: temporary memory to durable memory (ROADMAP P7-05, ADR-0009).

``plan`` is a pure function of the visible items of ONE principal and the current tick; ``apply`` executes the plan
through ``MemoryStore.write`` and ``MemoryStore.forget``, so consolidation can never bypass the write policy or the
forgetting log. Rules run in a fixed order over items sorted by (created_at, item_id):

- C0 ``fuse``     — SENSORY items of one event (tag ``event:<x>``) in two or more modalities become one MULTISENSORY
  buffer item (multisensory memory). Still transient.
- C1 ``attend``   — SENSORY items tagged ``attend`` become CONVERSATION items before they expire.
- C2 ``promote``  — CONVERSATION items tagged ``remember`` WITH consent become USER_PERSISTENT items.
- C3 ``experience`` — TASK items that are DONE or FAILED become PROCEDURAL items (goal, outcome, steps).
- C4 ``dedupe``   — durable items with the same kind, normalised content and fact key are merged into one item; the
  originals are forgotten with reason ``consolidated``.

Every created item has CONSOLIDATION provenance listing its sources, confidence = minimum of the sources, and, for
KNOWLEDGE, the weakest verification state of the sources. A rule never creates an item when an equal durable item
already exists, so running consolidation again on the same state changes nothing (idempotent). No model is used:
there is no summarisation or extraction, only these rules (model-driven consolidation is P7-05a, BLOCKED).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from nawa.evaluation.normalize import normalize
from nawa.memory import provenance as prov
from nawa.memory.policy import content_problems
from nawa.memory.isolation import Principal
from nawa.memory.types import DURABLE_KINDS, MemoryItem, MemoryKind, Modality, TaskStatus
from nawa.verification.states import VerificationState

AUTHOR = "nawa:consolidation"
_STRENGTH = [VerificationState.SUPPORTED, VerificationState.PARTIALLY_SUPPORTED, VerificationState.UNCERTAIN,
             VerificationState.INSUFFICIENT_EVIDENCE]


@dataclass(frozen=True)
class Create:
    rule: str
    kind: MemoryKind
    content: str
    sources: tuple[str, ...]
    confidence: float
    consent: bool = False
    verification_state: VerificationState | None = None
    modality: Modality | None = None
    tags: tuple[str, ...] = ()
    fact_key: tuple[str, ...] | None = None


@dataclass(frozen=True)
class Plan:
    create: tuple[Create, ...] = ()
    retire: tuple[str, ...] = ()
    notes: tuple[str, ...] = field(default=())

    @property
    def empty(self) -> bool:
        return not self.create and not self.retire


def _sig(kind: MemoryKind, content: str, fact_key) -> tuple:
    return (kind.value, normalize(content), tuple(fact_key) if fact_key else None)


def _weakest(states) -> VerificationState | None:
    states = [s for s in states if s is not None]
    return max(states, key=_STRENGTH.index) if states else None


def plan(items: list[MemoryItem]) -> Plan:
    items = sorted(items, key=lambda it: (it.created_at, it.item_id))
    owners = {(it.owner, it.project) for it in items}
    if len(owners) > 1:
        raise ValueError("consolidation_spans_principals")      # never mixes users or projects
    existing = {_sig(it.kind, it.content, it.fact_key) for it in items}
    creates: list[Create] = []

    def add(c: Create) -> None:
        s = _sig(c.kind, c.content, c.fact_key)
        if content_problems(c.content):         # e.g. a fused item longer than MAX_CHARS: skipped, never truncated
            return
        if s not in existing:
            existing.add(s)
            creates.append(c)

    # C0 fuse
    events: dict[str, list[MemoryItem]] = {}
    for it in items:
        if it.kind is MemoryKind.SENSORY and it.modality is not Modality.MULTISENSORY:
            for t in it.tags:
                if t.startswith("event:"):
                    events.setdefault(t, []).append(it)
    for ev in sorted(events):
        group = sorted(events[ev], key=lambda it: (it.modality.value, it.created_at, it.item_id))
        if len({it.modality for it in group}) >= 2:
            add(Create("fuse", MemoryKind.SENSORY, " | ".join(f"{it.modality.value}: {it.content}" for it in group),
                       tuple(it.item_id for it in group), prov.combine_confidence(it.confidence for it in group),
                       modality=Modality.MULTISENSORY, tags=(ev,)))
    # C1 attend
    for it in items:
        if it.kind is MemoryKind.SENSORY and "attend" in it.tags:
            add(Create("attend", MemoryKind.CONVERSATION, it.content, (it.item_id,), it.confidence,
                       tags=tuple(t for t in it.tags if t != "attend")))
    # C2 promote (consent is required again here and by the write policy)
    for it in items:
        if it.kind is MemoryKind.CONVERSATION and "remember" in it.tags and it.consent:
            add(Create("promote", MemoryKind.USER_PERSISTENT, it.content, (it.item_id,), it.confidence,
                       consent=True, tags=tuple(t for t in it.tags if t != "remember")))
    # C3 experience
    for it in items:
        if it.kind is MemoryKind.TASK and it.task_status in (TaskStatus.DONE, TaskStatus.FAILED):
            steps = " ; ".join(it.steps) if it.steps else "-"
            add(Create("experience", MemoryKind.PROCEDURAL, f"{it.content} => {it.task_status.value}: {steps}",
                       (it.item_id,), it.confidence, tags=("from_task",)))
    # C4 dedupe among existing durable items
    groups: dict[tuple, list[MemoryItem]] = {}
    for it in items:
        if it.kind in DURABLE_KINDS:
            groups.setdefault(_sig(it.kind, it.content, it.fact_key), []).append(it)
    retire: list[str] = []
    for sig in sorted(groups, key=lambda s: (s[0], s[1], s[2] or ())):
        g = groups[sig]
        if len(g) < 2:
            continue
        first = g[0]
        creates.append(Create(
            "dedupe", first.kind, first.content, tuple(it.item_id for it in g),
            prov.combine_confidence(it.confidence for it in g), consent=all(it.consent for it in g),
            verification_state=_weakest(it.verification_state for it in g),
            tags=tuple(sorted({t for it in g for t in it.tags})), fact_key=first.fact_key))
        retire += [it.item_id for it in g]
    return Plan(tuple(creates), tuple(retire))


def apply(store, principal: Principal) -> tuple[list[MemoryItem], list[str]]:
    """Plan on the principal's visible items and execute it. Returns (created items, retired ids)."""
    p = plan(store.scan(principal))
    now = store.clock.now()
    created = []
    for c in p.create:
        created.append(store.write(
            principal, c.kind, c.content, provenance=prov.derived(c.sources, AUTHOR, now, c.rule),
            confidence=c.confidence, consent=c.consent, verification_state=c.verification_state,
            modality=c.modality, tags=c.tags, fact_key=c.fact_key))
    for item_id in p.retire:
        store.forget(principal, item_id, reason="consolidated")
    return created, list(p.retire)
