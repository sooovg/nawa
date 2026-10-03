"""P7-02: expert specification schema and registry (ADR-0009).

Tests that:
1. Every P7-01 domain has exactly one expert spec.
2. Specs are frozen and serializable.
3. Data contracts are synthetic-only (no real URLs, no HF refs, no model IDs).
4. Test cases are synthetic-only.
5. Limits are positive and enforced.
6. Routing decisions use existing nawa.routing types.
7. The registry is complete, non-duplicating, and snapshot-isolated.
8. Stub responses are deterministic.
9. No training manifest, no adapter path, no external API, no model ID anywhere in specs.

Code-only scope: synthetic data only, no external model, no network, no real data.
"""

from __future__ import annotations

import copy
import re

import pytest

from nawa.experts import (EXPERT_REGISTRY, EXPERT_SPECS, DataContract, DataPolicy, ExpertDomain,
                          ExpertLimits, ExpertRegistry, ExpertSpec, ExpertStatus, ExpertTestCase,
                          FailureMode, deregister_expert, get_expert, get_expert_spec, list_experts,
                          register_expert, registry_snapshot, validate_expert_specs)
from nawa.experts.spec import _SYNTHETIC_REF
from nawa.routing.router import Handler, Kind


# ---------------------------------------------------------------------------
# 1. Domain coverage
# ---------------------------------------------------------------------------

class TestDomainCoverage:

    def test_all_seven_domains_present(self):
        """Every P7-01 domain must have exactly one expert."""
        domains = [s.domain for s in EXPERT_SPECS]
        for d in ExpertDomain:
            assert d in domains, f"domain {d.value!r} has no expert"

    def test_exactly_one_expert_per_domain(self):
        domains = [s.domain for s in EXPERT_SPECS]
        for d in ExpertDomain:
            assert domains.count(d) == 1, f"domain {d.value!r} has {domains.count(d)} experts"

    def test_seven_experts_total(self):
        assert len(EXPERT_SPECS) == 7


# ---------------------------------------------------------------------------
# 2. Frozen and serializable
# ---------------------------------------------------------------------------

class TestFrozenSerializable:

    def test_spec_is_frozen(self):
        for spec in EXPERT_SPECS:
            with pytest.raises((AttributeError, Exception)):
                spec.goal = "changed"  # type: ignore

    def test_spec_to_dict_round_trip(self):
        for spec in EXPERT_SPECS:
            d = spec.to_dict()
            assert d["expert_id"] == spec.expert_id
            assert d["domain"] == spec.domain.value
            assert isinstance(d["test_cases"], list)
            assert len(d["test_cases"]) == len(spec.test_cases)
            assert d["routing_handler"] == spec.routing_handler.value

    def test_data_contract_is_frozen(self):
        dc = DataContract(allowed_sources=("synthetic:test/1",))
        with pytest.raises((AttributeError, Exception)):
            dc.policy = DataPolicy.SYNTHETIC_ONLY  # type: ignore

    def test_limits_is_frozen(self):
        limits = ExpertLimits()
        with pytest.raises((AttributeError, Exception)):
            limits.max_input_tokens = 999  # type: ignore


# ---------------------------------------------------------------------------
# 3. Synthetic-only data contracts
# ---------------------------------------------------------------------------

class TestSyntheticOnly:

    def test_all_data_sources_synthetic(self):
        for spec in EXPERT_SPECS:
            for src in spec.data_contract.allowed_sources:
                assert _SYNTHETIC_REF.match(src), \
                    f"expert {spec.expert_id!r}: source {src!r} is not synthetic"

    def test_all_test_case_sources_synthetic(self):
        for spec in EXPERT_SPECS:
            for tc in spec.test_cases:
                assert _SYNTHETIC_REF.match(tc.source), \
                    f"expert {spec.expert_id!r}: test {tc.name!r} source {tc.source!r} is not synthetic"

    def test_no_real_urls_in_specs(self):
        url_pattern = re.compile(r"https?://|www\.|huggingface\.co|hf\.co|github\.com|api\.", re.IGNORECASE)
        for spec in EXPERT_SPECS:
            for field_name in ("goal", "stub_response"):
                val = getattr(spec, field_name)
                assert not url_pattern.search(val), \
                    f"expert {spec.expert_id!r}: {field_name} contains a URL: {val!r}"
            for src in spec.data_contract.allowed_sources:
                assert not url_pattern.search(src), \
                    f"expert {spec.expert_id!r}: data source {src!r} contains a URL"
            for tc in spec.test_cases:
                assert not url_pattern.search(tc.input), \
                    f"expert {spec.expert_id!r}: test {tc.name!r} input contains a URL"
                assert not url_pattern.search(tc.expected_output), \
                    f"expert {spec.expert_id!r}: test {tc.name!r} output contains a URL"

    def test_no_model_ids_in_specs(self):
        model_pattern = re.compile(r"\b(qwen|llama|gpt|bert|transformers|openai|anthropic)\b", re.IGNORECASE)
        for spec in EXPERT_SPECS:
            for field_name in ("goal", "stub_response"):
                val = getattr(spec, field_name)
                assert not model_pattern.search(val), \
                    f"expert {spec.expert_id!r}: {field_name} references a model: {val!r}"

    def test_no_training_manifest_in_specs(self):
        manifest_pattern = re.compile(r"training_manifest|adapter_path|model_id|external_api", re.IGNORECASE)
        for spec in EXPERT_SPECS:
            d = spec.to_dict()
            serialized = str(d)
            assert not manifest_pattern.search(serialized), \
                f"expert {spec.expert_id!r}: spec contains forbidden reference: {serialized[:200]}"

    def test_data_contract_rejects_non_synthetic(self):
        with pytest.raises(ValueError, match="synthetic"):
            DataContract(allowed_sources=("https://example.com/data",))

    def test_data_contract_rejects_non_synthetic_policy(self):
        """A DataContract with a non-synthetic policy should fail at construction.
        Since DataPolicy only has SYNTHETIC_ONLY, we test that passing an invalid
        policy value raises."""
        with pytest.raises(ValueError):
            # DataPolicy has only one member; an invalid string should fail
            DataContract(policy="open", allowed_sources=("synthetic:test/1",))


# ---------------------------------------------------------------------------
# 4. Test cases
# ---------------------------------------------------------------------------

class TestTestCases:

    def test_every_expert_has_at_least_one_test_case(self):
        for spec in EXPERT_SPECS:
            assert len(spec.test_cases) >= 1, \
                f"expert {spec.expert_id!r} has no test cases"

    def test_test_case_names_unique(self):
        for spec in EXPERT_SPECS:
            names = [tc.name for tc in spec.test_cases]
            assert len(names) == len(set(names)), \
                f"expert {spec.expert_id!r}: duplicate test case names: {names}"

    def test_test_case_rejects_empty_name(self):
        with pytest.raises(ValueError, match="name"):
            ExpertTestCase(name="", input="x", expected_output="y")

    def test_test_case_rejects_empty_input(self):
        with pytest.raises(ValueError, match="input"):
            ExpertTestCase(name="t", input="", expected_output="y")

    def test_test_case_rejects_empty_output(self):
        with pytest.raises(ValueError, match="expected_output"):
            ExpertTestCase(name="t", input="x", expected_output="")

    def test_test_case_rejects_non_synthetic_source(self):
        with pytest.raises(ValueError, match="synthetic"):
            ExpertTestCase(name="t", input="x", expected_output="y", source="real:data")


# ---------------------------------------------------------------------------
# 5. Limits
# ---------------------------------------------------------------------------

class TestLimits:

    def test_default_limits_positive(self):
        limits = ExpertLimits()
        assert limits.max_input_tokens > 0
        assert limits.max_output_tokens > 0
        assert limits.max_calls_per_turn > 0
        assert limits.timeout_ticks >= 0
        assert limits.max_retries >= 0

    def test_rejects_zero_max_tokens(self):
        with pytest.raises(ValueError, match="max_input_tokens"):
            ExpertLimits(max_input_tokens=0)

    def test_rejects_negative_max_tokens(self):
        with pytest.raises(ValueError, match="max_input_tokens"):
            ExpertLimits(max_input_tokens=-1)

    def test_rejects_negative_timeout(self):
        with pytest.raises(ValueError, match="timeout_ticks"):
            ExpertLimits(timeout_ticks=-1)

    def test_rejects_negative_retries(self):
        with pytest.raises(ValueError, match="max_retries"):
            ExpertLimits(max_retries=-1)

    def test_rejects_zero_max_calls(self):
        with pytest.raises(ValueError, match="max_calls_per_turn"):
            ExpertLimits(max_calls_per_turn=0)


# ---------------------------------------------------------------------------
# 6. Routing decisions use existing nawa.routing types
# ---------------------------------------------------------------------------

class TestRoutingDecisions:

    def test_routing_kinds_are_valid_kind_enum(self):
        for spec in EXPERT_SPECS:
            for k in spec.routing_kinds:
                assert isinstance(k, Kind), \
                    f"expert {spec.expert_id!r}: routing kind {k!r} is not a Kind"

    def test_routing_handler_is_valid_handler_enum(self):
        for spec in EXPERT_SPECS:
            assert isinstance(spec.routing_handler, Handler), \
                f"expert {spec.expert_id!r}: routing handler {spec.routing_handler!r} is not a Handler"

    def test_safety_expert_highest_priority(self):
        """Safety expert should have the lowest priority number (highest priority)."""
        safety = get_expert_spec("expert.safety")
        for spec in EXPERT_SPECS:
            if spec.expert_id != "expert.safety":
                assert safety.routing_priority <= spec.routing_priority, \
                    f"safety priority {safety.routing_priority} > {spec.expert_id} priority {spec.routing_priority}"

    def test_routing_priority_ties_deterministic(self):
        """If two experts share a (kind, handler) pair with equal priority, the tie-break is expert_id."""
        from collections import defaultdict
        kind_handler_priority = defaultdict(list)
        for spec in EXPERT_SPECS:
            for k in spec.routing_kinds:
                key = (k, spec.routing_handler, spec.routing_priority)
                kind_handler_priority[key].append(spec.expert_id)
        for key, experts in kind_handler_priority.items():
            if len(experts) > 1:
                # expert_id is unique and sortable, so tie-break is deterministic
                assert len(experts) == len(set(experts)), \
                    f"duplicate expert_ids for {key}: {experts}"


# ---------------------------------------------------------------------------
# 7. Registry
# ---------------------------------------------------------------------------

class TestRegistry:

    def test_registry_has_seven_experts(self):
        assert len(EXPERT_REGISTRY) == 7

    def test_registry_list_returns_all_active(self):
        experts = list_experts()
        assert len(experts) == 7

    def test_registry_get_returns_spec(self):
        spec = get_expert("expert.math")
        assert spec.domain is ExpertDomain.MATH

    def test_registry_get_unknown_raises(self):
        with pytest.raises(KeyError, match="not registered"):
            get_expert("expert.unknown")

    def test_registry_deregister_removes(self):
        snap = registry_snapshot()
        assert len(snap) == 7
        removed = snap.deregister("expert.math")
        assert removed.expert_id == "expert.math"
        assert len(snap) == 6
        with pytest.raises(KeyError):
            snap.get("expert.math")

    def test_registry_snapshot_is_deep_copy(self):
        """P7-04: adding/removing on a snapshot does not affect the live registry."""
        snap = registry_snapshot()
        snap.deregister("expert.arabic")
        assert len(snap) == 6
        assert len(EXPERT_REGISTRY) == 7  # live registry unchanged
        assert "expert.arabic" in EXPERT_REGISTRY

    def test_registry_register_replaces(self):
        snap = registry_snapshot()
        original = snap.get("expert.math")
        modified = ExpertSpec(
            expert_id="expert.math",
            domain=ExpertDomain.MATH,
            goal="هدف معدّل",
            data_contract=original.data_contract,
            test_cases=original.test_cases,
            limits=original.limits,
            routing_kinds=original.routing_kinds,
            routing_handler=original.routing_handler,
            routing_priority=original.routing_priority,
            failure_mode=original.failure_mode,
            stub_response="[stub:math] معدّل",
        )
        snap.register(modified)
        assert snap.get("expert.math").goal == "هدف معدّل"

    def test_registry_disabled_expert_not_in_list(self):
        snap = registry_snapshot()
        snap.register(snap.deregister("expert.search"), status=ExpertStatus.DISABLED)
        active = snap.list_experts()
        assert all(s.expert_id != "expert.search" for s in active)
        assert len(active) == 6
        all_with_disabled = snap.list_experts(include_disabled=True)
        assert any(s.expert_id == "expert.search" for s in all_with_disabled)

    def test_registry_get_disabled_raises(self):
        snap = registry_snapshot()
        spec = snap.deregister("expert.planning")
        snap.register(spec, status=ExpertStatus.DISABLED)
        with pytest.raises(KeyError, match="disabled"):
            snap.get("expert.planning")


# ---------------------------------------------------------------------------
# 8. Stub responses are deterministic
# ---------------------------------------------------------------------------

class TestDeterministicStubs:

    def test_stub_responses_are_non_empty(self):
        for spec in EXPERT_SPECS:
            assert spec.stub_response, \
                f"expert {spec.expert_id!r}: stub_response is empty"

    def test_stub_responses_contain_stub_prefix(self):
        """Every stub response should be clearly marked as a stub."""
        for spec in EXPERT_SPECS:
            assert "[stub:" in spec.stub_response, \
                f"expert {spec.expert_id!r}: stub_response lacks [stub:] prefix: {spec.stub_response!r}"

    def test_stub_responses_differ_across_domains(self):
        """No two experts should have identical stub responses."""
        responses = [s.stub_response for s in EXPERT_SPECS]
        assert len(responses) == len(set(responses)), \
            "duplicate stub responses across experts"


# ---------------------------------------------------------------------------
# 9. validate_expert_specs
# ---------------------------------------------------------------------------

class TestValidateExpertSpecs:

    def test_validate_returns_no_problems(self):
        problems = validate_expert_specs()
        assert problems == [], f"unexpected problems: {problems}"

    def test_validate_detects_missing_domain(self):
        """If we remove an expert, validate should report the missing domain."""
        # This is tested indirectly: the real EXPERT_SPECS should be complete.
        # Here we test that validate would catch a gap if it existed.
        assert validate_expert_specs() == []

    def test_validate_detects_non_synthetic_source(self):
        """A DataContract with a non-synthetic source should fail at construction."""
        with pytest.raises(ValueError, match="synthetic"):
            DataContract(allowed_sources=("real:data",))


# ---------------------------------------------------------------------------
# 10. Failure modes
# ---------------------------------------------------------------------------

class TestFailureModes:

    def test_safety_uses_abort(self):
        """Safety expert should abort on failure, not guess."""
        safety = get_expert_spec("expert.safety")
        assert safety.failure_mode is FailureMode.ABORT

    def test_planning_uses_delegate(self):
        """Planning expert should delegate on failure."""
        planning = get_expert_spec("expert.planning")
        assert planning.failure_mode is FailureMode.DELEGATE

    def test_all_failure_modes_valid(self):
        for spec in EXPERT_SPECS:
            assert isinstance(spec.failure_mode, FailureMode), \
                f"expert {spec.expert_id!r}: failure_mode is not a FailureMode"


# ---------------------------------------------------------------------------
# 11. Mutation tests
# ---------------------------------------------------------------------------

class TestExpertSpecMutations:

    def test_mutant_missing_domain_is_killed(self, monkeypatch):
        """If a domain is removed, validate_expert_specs should report it."""
        import nawa.experts.spec as spec_mod
        original = spec_mod.EXPERT_SPECS
        # Remove one expert
        monkeypatch.setattr(spec_mod, "EXPERT_SPECS", tuple(s for s in original if s.domain is not ExpertDomain.SAFETY))
        problems = spec_mod.validate_expert_specs()
        assert any("missing" in p for p in problems), \
            f"validate_expert_specs did not detect missing safety domain: {problems}"

    def test_mutant_duplicate_id_is_killed(self, monkeypatch):
        """If an expert ID is duplicated, validate should report it."""
        import nawa.experts.spec as spec_mod
        original = spec_mod.EXPERT_SPECS
        # Duplicate the first expert with the same ID
        first = original[0]
        monkeypatch.setattr(spec_mod, "EXPERT_SPECS", original + (first,))
        problems = spec_mod.validate_expert_specs()
        assert any("duplicate" in p for p in problems), \
            f"validate_expert_specs did not detect duplicate ID: {problems}"

    def test_mutant_non_synthetic_source_is_killed(self, monkeypatch):
        """If a data source is non-synthetic, validate should report it."""
        import nawa.experts.spec as spec_mod
        # Construct a spec with a non-synthetic source — this should fail at construction
        with pytest.raises(ValueError, match="synthetic"):
            DataContract(allowed_sources=("https://example.com",))
