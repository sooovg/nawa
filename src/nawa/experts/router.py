"""Expert delegation router (ROADMAP P7-03; code-only scope, ADR-0009).

A thin delegation layer over the existing P6-06 router (``nawa.routing.router``). It does NOT reimplement
classification: it calls ``route()`` from P6-06, then checks the expert registry for matching experts. If an
expert matches, it is selected for delegation. If none match, the route falls back to the core alone — the
P6-06 route unchanged.

This module produces a documented selection decision only. It does not execute the expert or return its
``stub_response`` as an answer — that is the caller's job.

Selection rules (in order):
1. The P6-06 router classifies the query into kinds and produces a handler plan.
2. An expert matches when its ``routing_kinds`` intersect the route's kinds AND its ``routing_handler``
   appears in the route's plan before ``ABSTAIN``.
3. Experts whose ``routing_handler`` is ``ABSTAIN`` (e.g. safety) are selected only when the route's
   current handler is ``ABSTAIN`` — otherwise they would swallow most queries.
4. Matching experts are sorted by ``(routing_priority, expert_id)``; ties are deterministic.
5. An ambiguous route (flags present) never delegates to an expert — it stays on the core P6-06 route.
6. A disabled expert is never selected; the trace records the fallback.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from nawa.experts.registry import ExpertRegistry, ExpertStatus, registry_snapshot
from nawa.experts.spec import ExpertSpec
from nawa.routing.router import Handler, Kind, Route, Route as _Route, RouterConfig, route as _route, Step


@dataclass(frozen=True)
class ExpertRoute:
    """A P6-06 route augmented with expert delegation info.

    ``base_route`` is the original P6-06 route, unchanged. ``selected_experts`` is the ordered tuple of
    expert IDs chosen for delegation (empty = core only). ``core_only`` is True when no expert was
    selected. ``fallback_reason`` explains why the core was chosen instead. ``expert_trace`` documents
    the delegation decision step by step.
    """
    base_route: _Route
    selected_experts: tuple[str, ...] = ()
    core_only: bool = True
    fallback_reason: str | None = None
    expert_trace: tuple[Step, ...] = field(default=())

    @property
    def current(self) -> Handler:
        """The current handler — either the first selected expert's handler, or the base route's."""
        return self.base_route.current

    def to_dict(self) -> dict[str, Any]:
        return {
            "base_route": self.base_route.to_dict(),
            "selected_experts": list(self.selected_experts),
            "core_only": self.core_only,
            "fallback_reason": self.fallback_reason,
            "expert_trace": [s.to_list() for s in self.expert_trace],
        }


def _matches(spec: ExpertSpec, kinds: tuple[Kind, ...], plan: tuple[Handler, ...]) -> bool:
    """An expert matches when its routing_kinds intersect the route's kinds AND its routing_handler
    appears in the plan before ABSTAIN."""
    # Kind intersection
    if not any(k in spec.routing_kinds for k in kinds):
        return False
    # Handler must be in the plan (excluding the final ABSTAIN sentinel)
    plan_handlers = [h for h in plan if h is not Handler.ABSTAIN]
    if spec.routing_handler not in plan_handlers:
        # Special case: an expert with routing_handler ABSTAIN (e.g. safety) is selected only when
        # the route's current handler is ABSTAIN — i.e., the core has nothing else to offer.
        if spec.routing_handler is Handler.ABSTAIN and plan and plan[0] is Handler.ABSTAIN:
            return True
        return False
    return True


def route_with_experts(query: str, config: RouterConfig | None = None,
                       registry: ExpertRegistry | None = None, max_experts: int = 1) -> ExpertRoute:
    """Route a query through P6-06, then check the expert registry for delegation.

    Returns an :class:`ExpertRoute` with the delegation decision documented. Does not execute the expert.
    """
    if not isinstance(query, str):
        raise ValueError("query must be a string")
    if max_experts < 1:
        raise ValueError("max_experts must be >= 1")

    reg = registry if registry is not None else registry_snapshot()
    base = _route(query, config)
    trace: list[Step] = []

    # Ambiguous route: never delegate, stay on core
    if base.ambiguous:
        trace.append(Step("E0", "ambiguous route: no expert delegation, core only"))
        return ExpertRoute(base_route=base, selected_experts=(), core_only=True,
                           fallback_reason="ambiguous route", expert_trace=tuple(trace))

    # Find matching experts
    candidates: list[ExpertSpec] = []
    for spec in reg.list_experts(include_disabled=True):
        if _matches(spec, base.kinds, base.plan):
            # Skip disabled experts
            if reg._status.get(spec.expert_id) is ExpertStatus.DISABLED:
                trace.append(Step("E1", f"skip {spec.expert_id}: disabled"))
                continue
            candidates.append(spec)
            trace.append(Step("E2", f"match: {spec.expert_id} (domain={spec.domain.value}, "
                                    f"priority={spec.routing_priority})"))

    if not candidates:
        trace.append(Step("E3", "no expert matched: core only"))
        return ExpertRoute(base_route=base, selected_experts=(), core_only=True,
                           fallback_reason="no expert matched", expert_trace=tuple(trace))

    # Sort by (priority, expert_id) — deterministic
    candidates.sort(key=lambda s: (s.routing_priority, s.expert_id))
    selected = candidates[:max_experts]
    selected_ids = tuple(s.expert_id for s in selected)
    trace.append(Step("E4", f"selected: {', '.join(selected_ids)} (max={max_experts})"))

    return ExpertRoute(base_route=base, selected_experts=selected_ids, core_only=False,
                       fallback_reason=None, expert_trace=tuple(trace))
