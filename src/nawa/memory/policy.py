"""Write, update and read rules for memory (ROADMAP P7-05, ADR-0009).

Rules are deterministic and return reason codes, never the refused content, so a refusal cannot leak what it refused.
This is a code-only policy on synthetic data. It is NOT a final privacy policy: OD-12 must be decided by the owner
before any real user memory is stored.

Write rules:
- W1 the principal is a synthetic user (``isolation.Principal``).
- W2 content is a non-empty string of at most ``MAX_CHARS`` characters.
- W3 no secret or PII pattern (``nawa.data.pii.find_pii``, P2-05) — refused, not redacted.
- W4 provenance is valid and synthetic (``provenance.problems``).
- W5 confidence is a finite number in [0, 1].
- W6 USER_PERSISTENT requires explicit consent.
- W7 KNOWLEDGE requires a verification state (P6-08) and an evidence reference; CONTRADICTED is refused.
- W8 SENSORY requires a modality and always expires; other kinds carry no modality except CONVERSATION (text).
- W9 TASK requires a task status.
- W10 tags are lowercase codes; ``domain:`` tags must be registered domains.
Update rules:
- U1 read-only items cannot be updated (they can still be forgotten).
- U2 every update carries new provenance recorded no earlier than the current version.
- U3 a KNOWLEDGE update needs a new evidence reference: a fact never changes without provenance.
- U4 an update keeps the item's consolidation lineage (``derived_from``); dropping it is refused.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from nawa.data.pii import find_pii
from nawa.memory import provenance as prov
from nawa.memory.types import DEFAULT_TTL, DOMAIN_TAGS, MemoryItem, MemoryKind, Modality, TaskStatus
from nawa.verification.states import VerificationState

MAX_CHARS = 4000
_TAG = re.compile(r"^[a-z][a-z0-9_]*(:[a-z0-9_\-]+)?$")


class PolicyViolation(ValueError):
    def __init__(self, reasons: list[str]):
        super().__init__(",".join(reasons))
        self.reasons = tuple(reasons)


@dataclass(frozen=True)
class WriteRequest:
    kind: MemoryKind
    content: str
    provenance: prov.Provenance
    confidence: float
    consent: bool = False
    verification_state: VerificationState | None = None
    modality: Modality | None = None
    tags: tuple[str, ...] = ()
    fact_key: tuple[str, ...] | None = None
    task_status: TaskStatus | None = None
    steps: tuple[str, ...] = ()
    due_at: int | None = None
    read_only: bool = False
    ttl: int | None = None


def content_problems(content: object) -> list[str]:
    if not isinstance(content, str) or not content.strip():
        return ["content_empty"]
    out = []
    if len(content) > MAX_CHARS:
        out.append("content_too_long")
    out += sorted({f"pii:{s.type}" for s in find_pii(content)})
    return out


def check_write(req: WriteRequest) -> list[str]:
    r: list[str] = []
    if not isinstance(req.kind, MemoryKind):
        return ["kind_invalid"]
    r += content_problems(req.content)
    for s in req.steps:
        r += [f"step_{x}" for x in content_problems(s)]
    r += prov.problems(req.provenance)
    try:
        prov.check_confidence(req.confidence)
    except prov.ProvenanceError:
        r.append("confidence_out_of_range")
    k = req.kind
    if k is MemoryKind.USER_PERSISTENT and req.consent is not True:
        r.append("consent_required")
    if k is MemoryKind.KNOWLEDGE:
        if not isinstance(req.verification_state, VerificationState):
            r.append("verification_state_required")
        elif req.verification_state is VerificationState.CONTRADICTED:
            r.append("contradicted_knowledge_refused")
        if isinstance(req.provenance, prov.Provenance) and req.provenance.evidence_ref is None \
                and req.provenance.source_type is not prov.SourceType.CONSOLIDATION:
            r.append("evidence_ref_required")
    elif req.verification_state is not None:
        r.append("verification_state_only_for_knowledge")
    if k is MemoryKind.SENSORY:
        if not isinstance(req.modality, Modality):
            r.append("modality_required")
    elif req.modality is not None and not (k is MemoryKind.CONVERSATION and req.modality is Modality.TEXT):
        r.append("modality_only_for_sensory")
    if k is MemoryKind.TASK and not isinstance(req.task_status, TaskStatus):
        r.append("task_status_required")
    if k is not MemoryKind.TASK and (req.task_status is not None or req.due_at is not None):
        r.append("task_fields_only_for_task")
    if req.ttl is not None and (not isinstance(req.ttl, int) or req.ttl <= 0):
        r.append("ttl_invalid")
    if k is MemoryKind.SENSORY and req.ttl is not None and req.ttl > DEFAULT_TTL[MemoryKind.SENSORY]:
        r.append("sensory_ttl_too_long")
    for t in req.tags:
        if not isinstance(t, str) or not _TAG.match(t):
            r.append("tag_invalid")
        elif t.startswith("domain:") and t not in DOMAIN_TAGS:
            r.append("domain_tag_unknown")
    if req.fact_key is not None and (not 2 <= len(req.fact_key) <= 3
                                     or any(not isinstance(x, str) or not x.strip() for x in req.fact_key)):
        r.append("fact_key_invalid")
    return sorted(set(r))


def expiry(req: WriteRequest, now: int) -> int | None:
    ttl = req.ttl if req.ttl is not None else DEFAULT_TTL.get(req.kind)
    return None if ttl is None else now + ttl


def check_update(item: MemoryItem, content: str, new_prov: prov.Provenance, confidence: float | None,
                 verification_state: VerificationState | None) -> list[str]:
    r = content_problems(content) + prov.problems(new_prov)
    if item.read_only:
        r.append("read_only")
    if isinstance(new_prov, prov.Provenance):
        if new_prov.recorded_at < item.provenance.recorded_at:
            r.append("provenance_older_than_current")
        if new_prov == item.provenance:
            r.append("provenance_not_new")
        if item.provenance.derived_from and set(new_prov.derived_from) != set(item.provenance.derived_from):
            r.append("lineage_dropped")
        if item.kind is MemoryKind.KNOWLEDGE and (new_prov.evidence_ref is None
                                                  or new_prov.evidence_ref == item.provenance.evidence_ref):
            r.append("knowledge_change_without_new_evidence")
    if confidence is not None:
        try:
            prov.check_confidence(confidence)
        except prov.ProvenanceError:
            r.append("confidence_out_of_range")
    if verification_state is not None and item.kind is not MemoryKind.KNOWLEDGE:
        r.append("verification_state_only_for_knowledge")
    if verification_state is VerificationState.CONTRADICTED:
        r.append("contradicted_knowledge_refused")
    return sorted(set(r))


def visible(item: MemoryItem, now: int, *, min_confidence: float = 0.0, facts_only: bool = False) -> bool:
    """Read rule: expired items are never returned; optional confidence floor and facts-only filter."""
    if item.expires_at is not None and now >= item.expires_at:
        return False
    if item.confidence < min_confidence:
        return False
    if facts_only and item.epistemic != "fact":
        return False
    return True
