"""P7-08: Adversarial memory tests and automated mutation harness (ADR-0009).

Covers the three areas P7-05 did not cover:
1. Pre-registered synthetic recall benchmark (expected answers declared before running).
2. Adversarial probes: ID guessing, query/tag injection, overlapping sequences.
3. Automated mutations on ``nawa.memory`` (targeted monkeypatches, not a global score).

Code-only scope: synthetic users only, no external model, no network, no real data, no quality claim.
"""

from __future__ import annotations

import copy
import json
import pytest

from memory_support import ALPHA, BETA, GAMMA
from nawa.memory import MemoryKind, MemoryStore, Principal, Provenance, SourceType
from nawa.memory import benchmark as bench
from nawa.memory import consolidation
from nawa.memory.forgetting import trace_scan
from nawa.memory.isolation import can_access, SYNTHETIC_USERS
from nawa.memory.store import LogicalClock
from nawa.verification.states import VerificationState


# ---------------------------------------------------------------------------
# 1. Pre-registered recall benchmark
# ---------------------------------------------------------------------------

class TestRecallBenchmark:
    """The benchmark scenario and expectations are pre-registered constants, not derived from the code."""

    def test_scenario_is_non_empty_and_has_unique_labels(self):
        labels = [s[0] for s in bench.SCENARIO]
        assert len(labels) == len(set(labels)) > 0

    def test_every_expectation_label_resolves(self):
        """Every expected and forbidden label in EXPECTATIONS must exist in SCENARIO."""
        scenario_labels = {s[0] for s in bench.SCENARIO}
        for exp in bench.EXPECTATIONS + bench.EXPECTATIONS_LATE:
            for l in exp.get("expected", []) + exp.get("forbidden", []):
                assert l in scenario_labels, f"expectation {exp['label']} references unknown label {l}"

    def test_benchmark_passes(self):
        """The full benchmark (expectations + adversarial + late) must pass on the unmutated code."""
        report = bench.run_benchmark()
        assert report["ok"], f"benchmark failed: {json.dumps(report, indent=2, default=str)[:2000]}"

    def test_benchmark_is_deterministic(self):
        """Two independent runs must give the same pass/fail result."""
        r1 = bench.run_benchmark()
        r2 = bench.run_benchmark()
        assert r1["ok"] == r2["ok"]

    def test_expectation_count(self):
        """There must be at least 10 expectation cases and 3 late cases."""
        assert len(bench.EXPECTATIONS) >= 10
        assert len(bench.EXPECTATIONS_LATE) >= 3

    def test_scenario_covers_all_kinds(self):
        """The scenario must include at least one item of each core kind."""
        kinds = {s[2] for s in bench.SCENARIO}
        for k in (MemoryKind.CONVERSATION, MemoryKind.USER_PERSISTENT, MemoryKind.TASK,
                  MemoryKind.KNOWLEDGE, MemoryKind.PROCEDURAL, MemoryKind.SENSORY):
            assert k in kinds, f"scenario missing kind {k}"


# ---------------------------------------------------------------------------
# 2. Adversarial probes
# ---------------------------------------------------------------------------

class TestAdversarialIDGuessing:
    """Guessed IDs must behave exactly like missing IDs: read returns None, metadata raises KeyError."""

    @pytest.mark.parametrize("gid", [
        "mem-0000000000000000",
        "mem-ffffffffffffffff",
        "mem-" + "a" * 16,
        "mem-" + "0" * 16,
        "mem-invalid",
        "not-a-mem-id",
        "mem-deadbeefdeadbeef",
    ])
    def test_guessed_id_read_returns_none(self, gid):
        store, labels = bench.build_scenario()
        assert store.read(ALPHA, gid) is None

    @pytest.mark.parametrize("gid", [
        "mem-0000000000000000",
        "mem-ffffffffffffffff",
        "mem-" + "a" * 16,
    ])
    def test_guessed_id_metadata_raises_keyerror(self, gid):
        store, labels = bench.build_scenario()
        for fn_name in ("provenance", "confidence", "acl", "version", "versions"):
            fn = getattr(store, fn_name)
            with pytest.raises(KeyError):
                fn(ALPHA, gid)

    def test_guessed_id_does_not_enter_cache(self):
        store, labels = bench.build_scenario()
        gid = "mem-0000000000000000"
        store.read(ALPHA, gid)  # miss
        state = store.dump_state()
        cache_text = json.dumps(state.get("cache", {}), sort_keys=True, ensure_ascii=False)
        assert gid not in cache_text

    def test_other_users_real_id_behaves_like_missing(self):
        store, labels = bench.build_scenario()
        beta_id = labels.get("beta_fact_weather_tokens")
        assert beta_id is not None
        # Alpha reading beta's id is None (same as missing)
        assert store.read(ALPHA, beta_id) is None
        # Probing beta's id as alpha raises KeyError (same as missing)
        with pytest.raises(KeyError):
            store.provenance(ALPHA, beta_id)

    def test_near_miss_id_fails(self):
        store, labels = bench.build_scenario()
        real_id = next(iter(labels.values()))
        # Flip the last character
        near = real_id[:-1] + ("0" if real_id[-1] != "0" else "1")
        assert store.read(ALPHA, near) is None


class TestQueryInjection:
    """Queries that look like filters or cross-user access must be treated as plain text."""

    @pytest.mark.parametrize("query", [
        "owner:user_beta",
        "user:user_beta",
        "tag:secret",
        "project:project_other",
        '{"cross_user": true}',
        "user_beta",
        "user_gamma",
        "principal:user_beta",
        "isolation:bypass",
        "SELECT * FROM memory",
        "<script>alert(1)</script>",
        "../../../etc/passwd",
    ])
    def test_injection_query_does_not_leak_other_users(self, query):
        store, labels = bench.build_scenario()
        hits = store.search(ALPHA, query, limit=100)
        owners = {h.item.owner for h in hits}
        assert "user_beta" not in owners
        assert "user_gamma" not in owners


class TestTagInjection:
    """Tags that look like capabilities must be treated as plain strings."""

    @pytest.mark.parametrize("tags", [
        ("owner:user_beta",),
        ("cross_user:true",),
        ("admin",),
        ("isolation:bypass",),
        ("project:other",),
    ])
    def test_injection_tag_is_plain_string(self, tags):
        store, labels = bench.build_scenario()
        store.clock.advance(1)
        # Use a safe source_ref that only has allowed characters
        tag_str = tags[0].replace(":", "_") if len(tags) == 1 else "multi"
        prov = Provenance(SourceType.USER_STATED, f"synthetic:inj/{tag_str}", ALPHA.user_id,
                          store.clock.now())
        item = store.write(ALPHA, MemoryKind.CONVERSATION, "kavun injection test", provenance=prov,
                           confidence=0.9, tags=tags)
        # The item is findable by its own tags (literal string match)
        hits = store.search(ALPHA, "kavun", tags=tags, limit=10)
        assert any(h.item.item_id == item.item_id for h in hits)

    def test_injection_tag_does_not_cross_users(self):
        store, labels = bench.build_scenario()
        store.clock.advance(1)
        prov = Provenance(SourceType.USER_STATED, "synthetic:inj/cross", ALPHA.user_id,
                          store.clock.now())
        tags = ("owner:user_beta",)
        item = store.write(ALPHA, MemoryKind.CONVERSATION, "kavun cross test", provenance=prov,
                           confidence=0.9, tags=tags)
        # Beta cannot find alpha's tagged item
        beta_hits = store.search(BETA, "kavun", limit=10)
        assert all(h.item.item_id != item.item_id for h in beta_hits)


class TestOverlappingSequences:
    """Overlapping fact subjects and shared tokens across users must not cross boundaries."""

    def test_same_subject_different_users_no_cross_association(self):
        store = MemoryStore(LogicalClock(0))
        store.clock.advance(1)
        prov_a = Provenance(SourceType.SYNTHETIC_DOCUMENT, "synthetic:overlap/a", ALPHA.user_id,
                            store.clock.now(), "synthetic:evidence/a")
        a = store.write(ALPHA, MemoryKind.KNOWLEDGE, "brelto overlap alpha", provenance=prov_a,
                        confidence=0.9, verification_state=VerificationState.SUPPORTED,
                        fact_key=("brelto", "overlap"))
        store.clock.advance(1)
        prov_b = Provenance(SourceType.SYNTHETIC_DOCUMENT, "synthetic:overlap/b", BETA.user_id,
                            store.clock.now(), "synthetic:evidence/b")
        b = store.write(BETA, MemoryKind.KNOWLEDGE, "brelto overlap beta", provenance=prov_b,
                        confidence=0.9, verification_state=VerificationState.SUPPORTED,
                        fact_key=("brelto", "overlap"))
        # Alpha's associate on its item must NOT return beta's item
        assoc = store.associate(ALPHA, a.item_id, limit=100)
        assoc_ids = {h.item.item_id for h in assoc}
        assert b.item_id not in assoc_ids

    def test_shared_tokens_long_sequence_no_cross(self):
        store = MemoryStore(LogicalClock(0))
        for i in range(20):
            store.clock.advance(1)
            content = f"shared_token_{i} common_word"
            pr = ALPHA if i % 2 == 0 else BETA
            prov = Provenance(SourceType.USER_STATED, f"synthetic:long/{i}", pr.user_id,
                              store.clock.now())
            store.write(pr, MemoryKind.CONVERSATION, content, provenance=prov, confidence=0.9)
        # Search "common_word" as alpha — only alpha's items
        alpha_hits = store.search(ALPHA, "common_word", limit=100)
        assert all(h.item.owner == "user_alpha" for h in alpha_hits)
        beta_hits = store.search(BETA, "common_word", limit=100)
        assert all(h.item.owner == "user_beta" for h in beta_hits)

    def test_update_then_recall_finds_latest_version(self):
        store = MemoryStore(LogicalClock(0))
        store.clock.advance(1)
        prov = Provenance(SourceType.USER_STATED, "synthetic:update/1", ALPHA.user_id,
                          store.clock.now())
        item = store.write(ALPHA, MemoryKind.CONVERSATION, "kavun original", provenance=prov,
                           confidence=0.9)
        store.clock.advance(1)
        new_prov = Provenance(SourceType.USER_STATED, "synthetic:update/2", ALPHA.user_id,
                              store.clock.now())
        store.update(ALPHA, item.item_id, "kavun updated mirsel", provenance=new_prov)
        hits = store.search(ALPHA, "mirsel", limit=10)
        assert any(h.item.item_id == item.item_id for h in hits)
        assert any("updated" in h.item.content for h in hits)

    def test_forget_then_recall_does_not_find_item(self):
        store = MemoryStore(LogicalClock(0))
        store.clock.advance(1)
        prov = Provenance(SourceType.SYNTHETIC_DOCUMENT, "synthetic:forget/1", ALPHA.user_id,
                          store.clock.now(), "synthetic:evidence/f")
        item = store.write(ALPHA, MemoryKind.KNOWLEDGE, "kavun forgettable mirsel", provenance=prov,
                           confidence=0.9, verification_state=VerificationState.SUPPORTED,
                           fact_key=("kavun", "attr"))
        store.forget(ALPHA, item.item_id, reason="user_request")
        # Search should not find it
        hits = store.search(ALPHA, "kavun", limit=100)
        assert all(h.item.item_id != item.item_id for h in hits)
        # Read returns None
        assert store.read(ALPHA, item.item_id) is None
        # No trace in structures
        traces = trace_scan(store, needles=[item.item_id, "kavun forgettable mirsel"])
        # Forgetting log is allowed to contain the id
        traces = [t for t in traces if not (t.startswith("state:log") or t == "file:forget_log.jsonl")]
        assert traces == []

    def test_consolidation_does_not_cross_users(self):
        store = MemoryStore(LogicalClock(0))
        for who in (ALPHA, BETA, GAMMA):
            for i in range(3):
                store.clock.advance(1)
                prov = Provenance(SourceType.USER_STATED, f"synthetic:cons/{who.user_id}/{i}",
                                  who.user_id, store.clock.now())
                store.write(who, MemoryKind.CONVERSATION, f"kavun {who.user_id} {i}", provenance=prov,
                           confidence=0.9, tags=("remember",), consent=True)
        # Consolidate each user
        for who in (ALPHA, BETA, GAMMA):
            consolidation.apply(store, who)
        # Each user's scan contains only their items
        for who in (ALPHA, BETA, GAMMA):
            items = store.scan(who)
            assert all(it.owner == who.user_id for it in items)


# ---------------------------------------------------------------------------
# 3. Automated mutation harness
# ---------------------------------------------------------------------------

class TestMutations:
    """Each registered mutant must break at least one benchmark or adversarial assertion."""

    @pytest.mark.parametrize("name,mutate", bench.REGISTERED_MUTANTS)
    def test_registered_mutant_is_killed(self, monkeypatch, name, mutate):
        """Apply the mutant, then run the benchmark. It must fail (assertion or exception)."""
        mutate(monkeypatch)
        with pytest.raises((AssertionError, Exception)):
            report = bench.run_benchmark()
            assert report["ok"], f"mutant {name} was NOT killed — benchmark still passes"

    def test_mutant_count(self):
        """There must be at least 9 registered mutants."""
        assert len(bench.REGISTERED_MUTANTS) >= 9

    def test_mutant_names_are_unique(self):
        names = [m[0] for m in bench.REGISTERED_MUTANTS]
        assert len(names) == len(set(names))

    def test_unmutated_benchmark_passes(self):
        """Sanity check: without any mutation, the benchmark must pass."""
        report = bench.run_benchmark()
        assert report["ok"]
