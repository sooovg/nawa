"""Planner: sub-questions + grants + budget → an ordered, budgeted plan (ROADMAP P6-03, ADR-0008).

For each sub-question, in order, the planner schedules (first rule that applies):

====  =========================================  ===============================================================
rule  condition                                  steps
====  =========================================  ===============================================================
P1    ARITHMETIC and ``CALCULATE`` granted       ``TOOL`` (calculator) → ``VERIFY``
P2    CODE and ``EXECUTE_CODE`` granted          ``TOOL`` (python sandbox) → ``VERIFY``
P3    otherwise                                  ``GENERATE`` (n candidates) → ``CONSISTENCY`` (only if n > 1)
                                                 → ``VERIFY``; a tool-kind sub-question without its grant carries
                                                 the note ``tool_not_granted``
====  =========================================  ===============================================================

and one final ``DECIDE`` step that depends on every scheduled ``VERIFY``. Nothing is answered without a ``VERIFY``
step, and self-consistency is never a substitute for it (it only feeds the verifier and the decision).

Budget (all-or-nothing per sub-question, in order). The plan reserves two ``STEPS`` (the plan record and ``DECIDE``).
A sub-question is scheduled only if all its steps and resources fit in what is left; otherwise it is **dropped with a
reason** (``budget:<RESOURCE>``), and every sub-question that depends on a dropped one is dropped too
(``depends_on_dropped:<id>``). A plan with a dropped sub-question has ``complete = False``, so the decision step can
refuse to answer that part. Nothing is dropped silently: every sub-question is either scheduled or listed in
``dropped``.

Grants: only ``CALCULATE`` and ``EXECUTE_CODE`` matter here. ``NETWORK`` (search, external APIs) cannot be granted
(P6-02a BLOCKED until OD-11); the planner has no search step at all.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import Enum

from nawa.reasoning.budget import Budget, Resource
from nawa.reasoning.decomposer import Kind, SubTask, decompose
from nawa.reasoning.state import canonical
from nawa.tools.registry import BLOCKED, Permission

PLAN_RESERVED_STEPS = 2          # the plan record itself and the final DECIDE


class Action(str, Enum):
    TOOL = "TOOL"
    GENERATE = "GENERATE"
    CONSISTENCY = "CONSISTENCY"
    VERIFY = "VERIFY"
    DECIDE = "DECIDE"


TOOL_FOR_KIND = {Kind.ARITHMETIC: ("calculator", Permission.CALCULATE),
                 Kind.CODE: ("python", Permission.EXECUTE_CODE)}


@dataclass(frozen=True)
class PlanStep:
    step_id: str
    action: Action
    subtask: str | None                  # None only for DECIDE
    depends_on: tuple[str, ...] = ()
    tool: str | None = None
    cost: tuple[tuple[str, int], ...] = ()   # extra resources besides the one STEP every record costs
    note: str = ""

    def to_dict(self) -> dict:
        return {"step_id": self.step_id, "action": self.action.value, "subtask": self.subtask,
                "depends_on": list(self.depends_on), "tool": self.tool, "cost": dict(self.cost), "note": self.note}


@dataclass(frozen=True)
class Plan:
    subtasks: tuple[SubTask, ...]
    steps: tuple[PlanStep, ...]
    dropped: tuple[tuple[str, str], ...]       # (task_id, reason)
    grants: tuple[str, ...]
    budget: Budget
    n_candidates: int
    feasible: bool = True
    plan_hash: str = field(default="", compare=False)

    @property
    def complete(self) -> bool:
        return self.feasible and not self.dropped

    def scheduled(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(s.subtask for s in self.steps if s.subtask))

    def total_cost(self) -> dict[str, int]:
        tot = {r.value: 0 for r in Resource}
        tot[Resource.STEPS.value] = len(self.steps) + (1 if self.steps else 0)    # + the plan record
        tot[Resource.SUBTASKS.value] = len(self.scheduled())
        for s in self.steps:
            for k, n in s.cost:
                tot[k] += n
        return tot

    def body(self) -> dict:
        return {"subtasks": [t.to_dict() for t in self.subtasks], "steps": [s.to_dict() for s in self.steps],
                "dropped": [list(d) for d in self.dropped], "grants": list(self.grants),
                "budget": self.budget.to_dict(), "n_candidates": self.n_candidates, "feasible": self.feasible,
                "complete": self.complete}

    def to_dict(self) -> dict:
        return {**self.body(), "plan_hash": self.plan_hash}


def _grants(grants: Iterable[object]) -> frozenset[Permission]:
    out = set()
    for g in grants:
        try:
            p = Permission(g.value if isinstance(g, Permission) else g)
        except ValueError:
            raise ValueError(f"unknown permission {g!r}") from None
        if p in BLOCKED:
            raise ValueError(BLOCKED[p])
        out.add(p)
    return frozenset(out)


def _check_subtasks(subtasks: list[SubTask]) -> None:
    seen: set[str] = set()
    for i, t in enumerate(subtasks):
        if not isinstance(t, SubTask):
            raise ValueError(f"not a SubTask: {t!r}")
        if t.task_id != f"t{i + 1}":
            raise ValueError("sub-question ids must be t1, t2, ... in order")
        for d in t.depends_on:
            if d not in seen:       # also rejects self-dependency and cycles: dependencies must point backwards
                raise ValueError(f"{t.task_id} depends on {d!r}, which is not an earlier sub-question")
        seen.add(t.task_id)


def _steps_for(t: SubTask, grants: frozenset[Permission], n: int, verify_of: dict[str, str],
               next_id: int) -> list[PlanStep]:
    deps = tuple(verify_of[d] for d in t.depends_on)
    tool = TOOL_FOR_KIND.get(t.kind)
    steps: list[PlanStep] = []

    def sid() -> str:
        return f"s{next_id + len(steps)}"

    if tool and tool[1] in grants:
        steps.append(PlanStep(sid(), Action.TOOL, t.task_id, deps, tool[0], ((Resource.TOOL_CALLS.value, 1),)))
    else:
        note = "tool_not_granted" if tool else ""
        steps.append(PlanStep(sid(), Action.GENERATE, t.task_id, deps, None, ((Resource.CANDIDATES.value, n),), note))
        if n > 1:
            steps.append(PlanStep(sid(), Action.CONSISTENCY, t.task_id, (steps[-1].step_id,)))
    steps.append(PlanStep(sid(), Action.VERIFY, t.task_id, (steps[-1].step_id,)))
    return steps


def plan_subtasks(subtasks: Iterable[SubTask], *, grants: Iterable[object] = (), budget: Budget | None = None,
                  n_candidates: int = 1) -> Plan:
    subs = list(subtasks)
    _check_subtasks(subs)
    g = _grants(grants)
    budget = budget or Budget()
    if not isinstance(budget, Budget):
        raise ValueError("budget must be a Budget")
    if isinstance(n_candidates, bool) or not isinstance(n_candidates, int) or n_candidates < 1:
        raise ValueError("n_candidates must be a positive int")

    left = {r: budget.limit(r) for r in Resource}
    feasible = left[Resource.STEPS] >= PLAN_RESERVED_STEPS
    left[Resource.STEPS] -= PLAN_RESERVED_STEPS
    steps: list[PlanStep] = []
    verify_of: dict[str, str] = {}
    dropped: list[tuple[str, str]] = []
    dropped_ids: set[str] = set()
    for t in subs:
        bad_dep = next((d for d in t.depends_on if d in dropped_ids), None)
        if not feasible or bad_dep:
            dropped.append((t.task_id, "budget:STEPS" if not feasible else f"depends_on_dropped:{bad_dep}"))
            dropped_ids.add(t.task_id)
            continue
        cand = _steps_for(t, g, n_candidates, verify_of, len(steps) + 1)
        need = {r: 0 for r in Resource}
        need[Resource.STEPS] = len(cand)
        need[Resource.SUBTASKS] = 1
        for s in cand:
            for k, n in s.cost:
                need[Resource(k)] += n
        short = next((r for r in Resource if need[r] > left[r]), None)
        if short is not None:
            dropped.append((t.task_id, f"budget:{short.value}"))
            dropped_ids.add(t.task_id)
            continue
        for r in Resource:
            left[r] -= need[r]
        steps += cand
        verify_of[t.task_id] = cand[-1].step_id
    if feasible:
        steps.append(PlanStep(f"s{len(steps) + 1}", Action.DECIDE, None, tuple(verify_of.values())))
    p = Plan(tuple(subs), tuple(steps), tuple(dropped), tuple(sorted(x.value for x in g)), budget, n_candidates,
             feasible)
    return Plan(p.subtasks, p.steps, p.dropped, p.grants, p.budget, p.n_candidates, p.feasible,
                hashlib.sha256(canonical(p.body()).encode("utf-8")).hexdigest())


def plan(question: str, *, grants: Iterable[object] = (), budget: Budget | None = None,
         n_candidates: int = 1) -> Plan:
    """Decompose ``question`` (rules in :mod:`nawa.reasoning.decomposer`) and plan it."""
    return plan_subtasks(decompose(question), grants=grants, budget=budget, n_candidates=n_candidates)
