"""Expert registry (ROADMAP P7-02; code-only scope, ADR-0009).

A registry of expert specs that P7-03 (router) and P7-04 (isolation test) will consume. The registry is a
mutable wrapper around the frozen ``EXPERT_SPECS`` tuple: specs are added or removed at load time, and a
snapshot can be taken for comparison. The registry starts empty and is populated by calling
``register_expert`` for each spec in ``EXPERT_SPECS``.

This is NOT a second router — it is a lookup table of expert metadata that the existing ``nawa.routing``
router (P6-06) can consult when deciding whether to delegate to an expert.
"""

from __future__ import annotations

import copy
from enum import Enum

from nawa.experts.spec import EXPERT_SPECS, ExpertSpec


class ExpertStatus(str, Enum):
    """Lifecycle status of a registered expert."""
    ACTIVE = "active"
    DISABLED = "disabled"


class ExpertRegistry:
    """A mutable registry of expert specs.

    ``register`` adds a spec (or replaces if the ID exists). ``deregister`` removes it. ``get`` looks up
    by ID. ``list_experts`` returns all active specs. ``snapshot`` returns a deep copy for isolation
    testing (P7-04): the caller can add or remove experts on the snapshot without touching the live
    registry.
    """

    def __init__(self) -> None:
        self._specs: dict[str, ExpertSpec] = {}
        self._status: dict[str, ExpertStatus] = {}

    def register(self, spec: ExpertSpec, status: ExpertStatus = ExpertStatus.ACTIVE) -> None:
        """Add or replace an expert spec."""
        if not isinstance(spec, ExpertSpec):
            raise TypeError(f"spec must be an ExpertSpec; got {type(spec).__name__}")
        if not isinstance(status, ExpertStatus):
            raise TypeError(f"status must be an ExpertStatus; got {type(status).__name__}")
        self._specs[spec.expert_id] = spec
        self._status[spec.expert_id] = status

    def deregister(self, expert_id: str) -> ExpertSpec:
        """Remove an expert and return its spec. Raises KeyError if not found."""
        if expert_id not in self._specs:
            raise KeyError(f"expert not registered: {expert_id!r}")
        spec = self._specs.pop(expert_id)
        self._status.pop(expert_id, None)
        return spec

    def get(self, expert_id: str) -> ExpertSpec:
        """Return the spec for ``expert_id``. Raises KeyError if not found or disabled."""
        if expert_id not in self._specs:
            raise KeyError(f"expert not registered: {expert_id!r}")
        if self._status.get(expert_id) is ExpertStatus.DISABLED:
            raise KeyError(f"expert disabled: {expert_id!r}")
        return self._specs[expert_id]

    def list_experts(self, include_disabled: bool = False) -> tuple[ExpertSpec, ...]:
        """Return all (active by default) expert specs, sorted by priority then ID."""
        active = [
            s for s in self._specs.values()
            if include_disabled or self._status.get(s.expert_id) is ExpertStatus.ACTIVE
        ]
        return tuple(sorted(active, key=lambda s: (s.routing_priority, s.expert_id)))

    def snapshot(self) -> "ExpertRegistry":
        """Return a deep copy for isolation testing (P7-04)."""
        new = ExpertRegistry()
        for eid, spec in self._specs.items():
            new._specs[eid] = copy.deepcopy(spec)
            new._status[eid] = self._status[eid]
        return new

    def __len__(self) -> int:
        return len(self._specs)

    def __contains__(self, expert_id: object) -> bool:
        return expert_id in self._specs and self._status.get(expert_id) is not ExpertStatus.DISABLED


# ---------------------------------------------------------------------------
# The default registry, pre-populated with the seven expert specs.
# ---------------------------------------------------------------------------

EXPERT_REGISTRY = ExpertRegistry()
for _spec in EXPERT_SPECS:
    EXPERT_REGISTRY.register(_spec)


def register_expert(spec: ExpertSpec, status: ExpertStatus = ExpertStatus.ACTIVE) -> None:
    """Register an expert in the default registry."""
    EXPERT_REGISTRY.register(spec, status)


def deregister_expert(expert_id: str) -> ExpertSpec:
    """Deregister an expert from the default registry."""
    return EXPERT_REGISTRY.deregister(expert_id)


def get_expert(expert_id: str) -> ExpertSpec:
    """Look up an expert in the default registry."""
    return EXPERT_REGISTRY.get(expert_id)


def list_experts(include_disabled: bool = False) -> tuple[ExpertSpec, ...]:
    """List all experts in the default registry."""
    return EXPERT_REGISTRY.list_experts(include_disabled)


def registry_snapshot() -> ExpertRegistry:
    """Take a snapshot of the default registry for isolation testing (P7-04)."""
    return EXPERT_REGISTRY.snapshot()
