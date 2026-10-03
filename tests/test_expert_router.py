"""P7-03: expert delegation router (ADR-0009).

Tests that:
1. A query matching an expert domain delegates to that expert.
2. A query matching no expert falls back to the core (P6-06 route unchanged).
3. Safety expert has highest priority (lowest number).
4. Delegation trace is documented.
5. Multiple experts matching: highest priority wins, tie broken by expert_id.
6. Fallback to core when expert is disabled.
7. The expert router does not reimplement P6-06 classification.
8. Ambiguous route never delegates.
9. base_route.to_dict() matches P6-06 output at fallback.

Code-only scope: synthetic data only, no external model, no network, no real data.
"""

from __future__ import annotations

import pytest

from nawa.experts import (EXPERT_REGISTRY, ExpertRoute, ExpertStatus, route_with_experts,
                          registry_snapshot, get_expert_spec)
from nawa.experts.router import _matches
from nawa.routing.router import Handler, Kind, Route, RouterConfig, Step, route as p6_route


# ---------------------------------------------------------------------------
# 1. Delegation to matching expert
# ---------------------------------------------------------------------------

class TestExpertDelegation:

    def test_math_query_delegates_to_math_expert(self):
        """A math query should delegate to the math expert."""
        er = route_with_experts("احسب 2 + 3", RouterConfig(granted_tools={"CALCULATE"}))
        assert not er.core_only
        assert "expert.math" in er.selected_experts

    def test_code_query_delegates_to_programming_expert(self):
        """A code query should delegate to the programming expert."""
        er = route_with_experts("```python\ndef f(): pass\n```",
                                RouterConfig(granted_tools={"EXECUTE_CODE"}))
        assert not er.core_only
        assert "expert.programming" in er.selected_experts

    def test_arithmetic_expression_delegates(self):
        """A bare arithmetic expression should delegate to the math expert."""
        er = route_with_experts("5 + 7", RouterConfig(granted_tools={"CALCULATE"}))
        assert not er.core_only
        assert "expert.math" in er.selected_experts


# ---------------------------------------------------------------------------
# 2. Fallback to core
# ---------------------------------------------------------------------------

class TestFallbackToCore:

    def test_unmatched_query_falls_back_to_core(self):
        """A query matching no expert should fall back to core only.
        Most queries will match safety (ABSTAIN handler) when the core has nothing,
        so we test with a query that matches the FACT kind with retrieval available —
        no expert has FACT+RETRIEVAL except documents/search, and those need the
        handler in the plan. With retrieval available, the plan has RETRIEVAL,
        and safety's ABSTAIN handler won't match.
        """
        # Use a query that routes to FACT+RETRIEVAL — no expert matches that combo
        # except expert.documents and expert.search, but those have different kinds.
        # Actually expert.search has routing_kinds=(FACT, OTHER) and routing_handler=RETRIEVAL.
        # So with retrieval available, search would match. Let's disable search and documents.
        snap = registry_snapshot()
        snap.deregister("expert.search")
        snap.deregister("expert.documents")
        snap.deregister("expert.safety")
        er = route_with_experts("ما هو الوقت", RouterConfig(retrieval_available=True), registry=snap)
        assert er.core_only
        assert er.selected_experts == ()
        assert er.fallback_reason is not None

    def test_fallback_base_route_matches_p6_06(self):
        """At fallback, base_route.to_dict() must match the P6-06 route exactly."""
        snap = registry_snapshot()
        snap.deregister("expert.search")
        snap.deregister("expert.documents")
        snap.deregister("expert.safety")
        query = "ما هو الوقت"
        cfg = RouterConfig(retrieval_available=True)
        p6 = p6_route(query, cfg)
        er = route_with_experts(query, cfg, registry=snap)
        assert er.base_route.to_dict() == p6.to_dict()

    def test_fallback_trace_documents_no_match(self):
        """The trace should document that no expert matched."""
        snap = registry_snapshot()
        snap.deregister("expert.search")
        snap.deregister("expert.documents")
        snap.deregister("expert.safety")
        er = route_with_experts("ما هو الوقت", RouterConfig(retrieval_available=True), registry=snap)
        trace_text = " ".join(s.detail for s in er.expert_trace)
        assert "no expert" in trace_text.lower() or "core only" in trace_text.lower()


# ---------------------------------------------------------------------------
# 3. Safety priority
# ---------------------------------------------------------------------------

class TestSafetyPriority:

    def test_safety_highest_priority(self):
        """Safety expert should have the lowest priority number (highest priority)."""
        safety = get_expert_spec("expert.safety")
        for spec in EXPERT_REGISTRY.list_experts():
            if spec.expert_id != "expert.safety":
                assert safety.routing_priority <= spec.routing_priority


# ---------------------------------------------------------------------------
# 4. Delegation trace
# ---------------------------------------------------------------------------

class TestDelegationTrace:

    def test_trace_records_match(self):
        """The trace should record which experts matched."""
        er = route_with_experts("احسب 2 + 3", RouterConfig(granted_tools={"CALCULATE"}))
        trace_text = " ".join(s.detail for s in er.expert_trace)
        assert "expert.math" in trace_text

    def test_trace_records_selection(self):
        """The trace should record the final selection."""
        er = route_with_experts("احسب 2 + 3", RouterConfig(granted_tools={"CALCULATE"}))
        trace_text = " ".join(s.detail for s in er.expert_trace)
        assert "selected" in trace_text.lower()

    def test_trace_steps_have_rule_and_detail(self):
        """Each trace step should have a rule id and a detail string."""
        er = route_with_experts("احسب 2 + 3", RouterConfig(granted_tools={"CALCULATE"}))
        assert er.expert_trace, "expert_trace should not be empty for a delegating query"
        for step in er.expert_trace:
            assert isinstance(step.rule, str)
            assert step.rule, "trace step rule should not be empty"
            assert isinstance(step.detail, str)
            assert step.detail, "trace step detail should not be empty"


# ---------------------------------------------------------------------------
# 5. Multiple experts and tie-breaking
# ---------------------------------------------------------------------------

class TestMultipleExperts:

    def test_max_experts_limit(self):
        """max_experts=2 should return at most 2 experts."""
        er = route_with_experts("احسب 2 + 3", RouterConfig(granted_tools={"CALCULATE"}), max_experts=2)
        assert len(er.selected_experts) <= 2

    def test_tie_break_by_expert_id(self):
        """When two experts share priority, the tie is broken by expert_id."""
        # The default specs don't have ties on the same kind/handler, so test with a snapshot
        snap = registry_snapshot()
        # Add a second math expert with the same priority
        from nawa.experts.spec import ExpertSpec, ExpertDomain, ExpertLimits, DataContract, ExpertTestCase, FailureMode
        from nawa.routing.router import Handler, Kind
        original = get_expert_spec("expert.math")
        twin = ExpertSpec(
            expert_id="expert.math2",
            domain=ExpertDomain.MATH,
            goal="هدف مزدوج",
            data_contract=original.data_contract,
            test_cases=original.test_cases,
            limits=original.limits,
            routing_kinds=original.routing_kinds,
            routing_handler=original.routing_handler,
            routing_priority=original.routing_priority,  # same priority
            failure_mode=original.failure_mode,
            stub_response="[stub:math2] مزدوج",
        )
        snap.register(twin)
        er = route_with_experts("احسب 2 + 3", RouterConfig(granted_tools={"CALCULATE"}), registry=snap, max_experts=2)
        # Both should be selected, ordered by expert_id
        assert "expert.math" in er.selected_experts
        assert "expert.math2" in er.selected_experts
        assert er.selected_experts.index("expert.math") < er.selected_experts.index("expert.math2")


# ---------------------------------------------------------------------------
# 6. Disabled expert fallback
# ---------------------------------------------------------------------------

class TestDisabledExpert:

    def test_disabled_expert_not_selected(self):
        """A disabled expert should not be selected."""
        snap = registry_snapshot()
        spec = snap.deregister("expert.math")
        snap.register(spec, status=ExpertStatus.DISABLED)
        er = route_with_experts("احسب 2 + 3", RouterConfig(granted_tools={"CALCULATE"}), registry=snap)
        assert "expert.math" not in er.selected_experts

    def test_disabled_expert_trace_records_skip(self):
        """The trace should mention the disabled expert was skipped."""
        snap = registry_snapshot()
        spec = snap.deregister("expert.math")
        snap.register(spec, status=ExpertStatus.DISABLED)
        er = route_with_experts("احسب 2 + 3", RouterConfig(granted_tools={"CALCULATE"}), registry=snap)
        trace_text = " ".join(s.detail for s in er.expert_trace)
        assert "disabled" in trace_text.lower()


# ---------------------------------------------------------------------------
# 7. Does not reimplement P6-06
# ---------------------------------------------------------------------------

class TestNoSecondRouter:

    def test_base_route_is_p6_06_route(self):
        """The base_route must be a P6-06 Route instance."""
        er = route_with_experts("احسب 2 + 3", RouterConfig(granted_tools={"CALCULATE"}))
        assert isinstance(er.base_route, Route)

    def test_base_route_kinds_match_p6(self):
        """The base_route's kinds must match the P6-06 classification."""
        query = "احسب 2 + 3"
        p6 = p6_route(query, RouterConfig(granted_tools={"CALCULATE"}))
        er = route_with_experts(query, RouterConfig(granted_tools={"CALCULATE"}))
        assert er.base_route.kinds == p6.kinds

    def test_base_route_plan_matches_p6(self):
        """The base_route's plan must match the P6-06 plan."""
        query = "احسب 2 + 3"
        cfg = RouterConfig(granted_tools={"CALCULATE"})
        p6 = p6_route(query, cfg)
        er = route_with_experts(query, cfg)
        assert er.base_route.plan == p6.plan


# ---------------------------------------------------------------------------
# 8. Ambiguous route never delegates
# ---------------------------------------------------------------------------

class TestAmbiguousRoute:

    def test_empty_query_no_delegation(self):
        """An empty query is ambiguous and should not delegate."""
        er = route_with_experts("")
        assert er.core_only
        assert er.selected_experts == ()

    def test_ambiguous_route_core_only(self):
        """A query with conflicting directives is ambiguous and should not delegate."""
        er = route_with_experts("احسب 2 + 2 بدون ادوات استخدم الحاسبة")
        assert er.core_only or er.selected_experts == ()


# ---------------------------------------------------------------------------
# 9. ExpertRoute properties
# ---------------------------------------------------------------------------

class TestExpertRouteProperties:

    def test_to_dict_has_required_fields(self):
        er = route_with_experts("احسب 2 + 3", RouterConfig(granted_tools={"CALCULATE"}))
        d = er.to_dict()
        assert "base_route" in d
        assert "selected_experts" in d
        assert "core_only" in d
        assert "fallback_reason" in d
        assert "expert_trace" in d

    def test_current_returns_base_current(self):
        """The current handler should match the base route's current."""
        er = route_with_experts("احسب 2 + 3", RouterConfig(granted_tools={"CALCULATE"}))
        assert er.current == er.base_route.current

    def test_expert_route_is_frozen(self):
        er = route_with_experts("احسب 2 + 3", RouterConfig(granted_tools={"CALCULATE"}))
        with pytest.raises((AttributeError, Exception)):
            er.core_only = True  # type: ignore


# ---------------------------------------------------------------------------
# 10. _matches helper
# ---------------------------------------------------------------------------

class TestMatchesHelper:

    def test_matches_kind_and_handler(self):
        """An expert whose routing_kinds intersect the route's kinds and whose routing_handler is in the plan."""
        from nawa.experts import get_expert_spec
        math = get_expert_spec("expert.math")
        kinds = (Kind.ARITHMETIC,)
        plan = (Handler.CALCULATOR, Handler.ABSTAIN)
        assert _matches(math, kinds, plan)

    def test_no_kind_intersection(self):
        """No kind intersection means no match."""
        from nawa.experts import get_expert_spec
        math = get_expert_spec("expert.math")
        kinds = (Kind.CODE,)
        plan = (Handler.CODE_SANDBOX, Handler.ABSTAIN)
        assert not _matches(math, kinds, plan)

    def test_handler_not_in_plan(self):
        """If the handler is not in the plan, no match."""
        from nawa.experts import get_expert_spec
        math = get_expert_spec("expert.math")
        kinds = (Kind.ARITHMETIC,)
        plan = (Handler.REASONING, Handler.ABSTAIN)  # no CALCULATOR in plan
        assert not _matches(math, kinds, plan)

    def test_safety_abstain_only_when_current_is_abstain(self):
        """Safety expert (routing_handler=ABSTAIN) should only match when the plan's current is ABSTAIN."""
        from nawa.experts import get_expert_spec
        safety = get_expert_spec("expert.safety")
        # When the plan starts with ABSTAIN (core has nothing)
        kinds = (Kind.OTHER,)
        plan = (Handler.ABSTAIN,)
        assert _matches(safety, kinds, plan)
        # When the plan has a real handler, safety should not match
        plan2 = (Handler.RETRIEVAL, Handler.ABSTAIN)
        assert not _matches(safety, kinds, plan2)
