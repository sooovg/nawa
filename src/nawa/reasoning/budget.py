"""Reasoning budget (ROADMAP P6-03, ADR-0008).

A :class:`Budget` holds hard integer limits on what one reasoning run may spend:

* ``STEPS``: recorded steps of any kind;
* ``TOOL_CALLS``: calculator or sandbox calls;
* ``CANDIDATES``: generated candidate answers (summed over all generator calls);
* ``SUBTASKS``: sub-questions the planner may schedule.

A :class:`Spend` is an immutable count of what was used. :meth:`Budget.charge` returns a new ``Spend`` or raises
:class:`BudgetExhausted`; it never returns a spend above a limit, and a refused charge changes nothing (all or nothing,
even when one charge touches several resources). Limits are plain non-negative ``int``: no floats, no ``bool``, no
"unlimited" value, so a budget can never be infinite by accident. A limit of ``0`` is valid and forbids the resource.

There are no defaults tuned on data. :data:`DEFAULT_LIMITS` are small round numbers for tests and smoke runs only; they
are not adopted settings (ADR-0008 D2: nothing is tuned on synthetic data).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum


class Resource(str, Enum):
    STEPS = "STEPS"
    TOOL_CALLS = "TOOL_CALLS"
    CANDIDATES = "CANDIDATES"
    SUBTASKS = "SUBTASKS"


DEFAULT_LIMITS = {Resource.STEPS: 64, Resource.TOOL_CALLS: 8, Resource.CANDIDATES: 16, Resource.SUBTASKS: 8}


class BudgetExhausted(Exception):
    """A charge would exceed a limit. ``resource`` is the first resource (in :class:`Resource` order) that would."""

    def __init__(self, resource: Resource, limit: int, used: int, requested: int) -> None:
        super().__init__(f"budget_exhausted:{resource.value} (limit {limit}, used {used}, requested {requested})")
        self.resource = resource
        self.limit = limit
        self.used = used
        self.requested = requested

    @property
    def reason(self) -> str:
        return f"budget_exhausted:{self.resource.value}"


def _count(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative int, got {value!r}")
    return value


def _cost(cost: Mapping[Resource, int]) -> dict[Resource, int]:
    if not isinstance(cost, Mapping):
        raise ValueError("cost must be a mapping Resource -> int")
    out = {}
    for r, n in cost.items():
        if not isinstance(r, Resource):
            raise ValueError(f"not a Resource: {r!r}")
        out[r] = _count(f"cost[{r.value}]", n)
    return out


@dataclass(frozen=True)
class Spend:
    steps: int = 0
    tool_calls: int = 0
    candidates: int = 0
    subtasks: int = 0

    def __post_init__(self) -> None:
        for r in Resource:
            _count(r.value, getattr(self, r.value.lower()))

    def get(self, r: Resource) -> int:
        return getattr(self, r.value.lower())

    def to_dict(self) -> dict[str, int]:
        return {r.value: self.get(r) for r in Resource}


@dataclass(frozen=True)
class Budget:
    max_steps: int = DEFAULT_LIMITS[Resource.STEPS]
    max_tool_calls: int = DEFAULT_LIMITS[Resource.TOOL_CALLS]
    max_candidates: int = DEFAULT_LIMITS[Resource.CANDIDATES]
    max_subtasks: int = DEFAULT_LIMITS[Resource.SUBTASKS]

    def __post_init__(self) -> None:
        for r in Resource:
            _count(f"max_{r.value.lower()}", self.limit(r))

    def limit(self, r: Resource) -> int:
        return getattr(self, f"max_{r.value.lower()}")

    def remaining(self, spend: Spend, r: Resource) -> int:
        return self.limit(r) - spend.get(r)

    def allows(self, spend: Spend, cost: Mapping[Resource, int]) -> bool:
        c = _cost(cost)
        return all(spend.get(r) + c.get(r, 0) <= self.limit(r) for r in Resource)

    def charge(self, spend: Spend, cost: Mapping[Resource, int]) -> Spend:
        """All-or-nothing: either every resource fits and the new spend is returned, or nothing is charged."""
        if not isinstance(spend, Spend):
            raise ValueError("spend must be a Spend")
        c = _cost(cost)
        for r in Resource:
            if spend.get(r) + c.get(r, 0) > self.limit(r):
                raise BudgetExhausted(r, self.limit(r), spend.get(r), c.get(r, 0))
        return Spend(**{r.value.lower(): spend.get(r) + c.get(r, 0) for r in Resource})

    def to_dict(self) -> dict[str, int]:
        return {r.value: self.limit(r) for r in Resource}

    @classmethod
    def from_dict(cls, d: Mapping[str, int]) -> Budget:
        if set(d) != {r.value for r in Resource}:
            raise ValueError(f"budget keys must be exactly {[r.value for r in Resource]}")
        return cls(**{f"max_{k.lower()}": v for k, v in d.items()})
