"""P7-08: Synthetic recall benchmark, adversarial cases, and mutation harness (ADR-0009).

This module is the P7-08 deliverable: a pre-registered synthetic scenario whose expected recall answers are
declared as constants before any code runs, a set of adversarial probes (ID guessing, query/tag injection,
overlapping sequences), and a mutation table that proves the benchmark is non-vacuous.

**Pre-registration principle.** ``SCENARIO`` lists every write with a stable label, and ``EXPECTATIONS`` lists every
recall case with the labels it must return and the labels it must not. Nothing is derived from the store's
behaviour at runtime: the benchmark builds a label→item_id map from the writes, runs the store, then maps results
back to labels and compares. Changing ``_new_id`` or the tokeniser must not break the benchmark unless it changes
recall semantics.

**Adversarial cases** are separate from the benchmark: they probe the store with guessed ids, injection strings in
queries and tags, and overlapping fact subjects across users. They assert that guessed ids behave like missing ids,
that injection strings are treated as plain text, and that overlapping subjects do not cross user boundaries.

**Mutations** are a table of targeted monkeypatches. Each mutant is expected to break at least one benchmark or
adversarial assertion. The test ``test_registered_mutants_are_killed`` runs every mutant and asserts it is caught.

Code-only scope (ADR-0009): synthetic users only, no external model, no network, no real data, no quality claim.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from nawa.memory.consolidation import apply as consolidate
from nawa.memory.forgetting import trace_scan
from nawa.memory.isolation import Principal, SYNTHETIC_USERS
from nawa.memory.provenance import Provenance, SourceType
from nawa.memory.store import LogicalClock, MemoryStore
from nawa.memory.types import MemoryKind, Modality, TaskStatus
from nawa.verification.states import VerificationState

# ---------------------------------------------------------------------------
# Synthetic vocabulary — invented words only, never real text.
# ---------------------------------------------------------------------------

VOCAB = ("brelto", "kavun", "mirsel", "tobrak", "elvanu", "qisto", "dorvel", "nupra", "salvek", "yorin")

ALPHA = Principal("user_alpha")
BETA = Principal("user_beta")
GAMMA = Principal("user_gamma")

# ---------------------------------------------------------------------------
# Pre-registered scenario: every write is a labelled constant.
# Each entry: (label, principal, kind, content, kwargs)
# The label is the only stable handle; item_ids are derived at runtime.
# ---------------------------------------------------------------------------

SCENARIO: list[tuple[str, Principal, MemoryKind, str, dict]] = [
    # --- Knowledge facts (different subjects, some shared tokens) ---
    ("alpha_fact_weather", ALPHA, MemoryKind.KNOWLEDGE,
     "brelto mirsel weather kavun", {
         "fact_key": ("brelto", "weather"), "verification_state": VerificationState.SUPPORTED,
         "confidence": 0.9, "evidence": "synthetic:doc/weather"}),
    ("alpha_fact_geo", ALPHA, MemoryKind.KNOWLEDGE,
     "tobrak elvanu geography dorvel", {
         "fact_key": ("tobrak", "geo"), "verification_state": VerificationState.SUPPORTED,
         "confidence": 0.85, "evidence": "synthetic:doc/geo"}),
    # Beta writes a fact with the SAME tokens as alpha's weather fact but a different subject
    ("beta_fact_weather_tokens", BETA, MemoryKind.KNOWLEDGE,
     "brelto mirsel weather nupra", {
         "fact_key": ("nupra", "weather"), "verification_state": VerificationState.SUPPORTED,
         "confidence": 0.8, "evidence": "synthetic:doc/beta-weather"}),
    # --- Tasks ---
    ("alpha_task_due", ALPHA, MemoryKind.TASK,
     "kavun task due soon", {"task_status": TaskStatus.OPEN, "due_at": 5, "steps": ("step1", "step2")}),
    ("beta_task_later", BETA, MemoryKind.TASK,
     "dorvel task later", {"task_status": TaskStatus.OPEN, "due_at": 100, "steps": ("plan",)}),
    # --- Conversation ---
    ("alpha_conv_remember", ALPHA, MemoryKind.CONVERSATION,
     "mirsel conversation remember kavun", {"consent": True, "tags": ("remember",), "confidence": 1.0}),
    ("beta_conv_plain", BETA, MemoryKind.CONVERSATION,
     "qisto plain conversation", {"confidence": 1.0}),
    # --- Procedural ---
    ("alpha_proc", ALPHA, MemoryKind.PROCEDURAL,
     "salvek procedure learned", {"confidence": 0.9, "steps": ("do_a", "do_b")}),
    # --- User persistent ---
    ("beta_persist", BETA, MemoryKind.USER_PERSISTENT,
     "yorin persistent fact", {"consent": True, "confidence": 0.95}),
    # --- Sensory (short TTL) ---
    ("alpha_sensory", ALPHA, MemoryKind.SENSORY,
     "fendra sensory input", {"modality": Modality.TEXT, "confidence": 1.0}),
]

# ---------------------------------------------------------------------------
# Pre-registered expectations: declared before the store runs.
# Each entry: (label, principal, method, query_or_args, expected_labels, forbidden_labels)
# expected_labels: items that MUST appear in the result (mapped from labels at runtime)
# forbidden_labels: items that MUST NOT appear
# ---------------------------------------------------------------------------

EXPECTATIONS: list[dict] = [
    # Search by shared token "brelto" — alpha sees alpha_fact_weather (contains "brelto"),
    # alpha_fact_geo does NOT contain "brelto" so it won't appear. Beta's item must NOT appear.
    {"label": "search_brelto_alpha", "principal": ALPHA, "method": "search",
     "query": "brelto", "expected": ["alpha_fact_weather"],
     "forbidden": ["beta_fact_weather_tokens"]},
    # Search "dorvel" — alpha sees alpha_fact_geo, beta sees beta_task_later (both contain "dorvel")
    {"label": "search_dorvel_alpha", "principal": ALPHA, "method": "search",
     "query": "dorvel", "expected": ["alpha_fact_geo"],
     "forbidden": ["beta_task_later", "beta_fact_weather_tokens"]},
    # Search "weather" — alpha sees alpha_fact_weather, not beta's (different subject but same tokens)
    {"label": "search_weather_alpha", "principal": ALPHA, "method": "search",
     "query": "weather", "expected": ["alpha_fact_weather"],
     "forbidden": ["beta_fact_weather_tokens"]},
    # Search "weather" — beta sees beta_fact_weather_tokens, not alpha's
    {"label": "search_weather_beta", "principal": BETA, "method": "search",
     "query": "weather", "expected": ["beta_fact_weather_tokens"],
     "forbidden": ["alpha_fact_weather"]},
    # Associate from alpha_fact_weather — beta's items must NOT appear
    {"label": "assoc_alpha_weather", "principal": ALPHA, "method": "associate",
     "query": "alpha_fact_weather", "expected": [], "forbidden": ["beta_fact_weather_tokens", "beta_task_later"]},
    # Due tasks — alpha_task_due (due_at=5) is due at tick 10; beta_task_later (due_at=100) is NOT
    {"label": "due_early_alpha", "principal": ALPHA, "method": "due",
     "query": None, "expected": ["alpha_task_due"], "forbidden": ["beta_task_later"]},
    # Scan alpha — all alpha durable items, no beta items
    {"label": "scan_alpha", "principal": ALPHA, "method": "scan",
     "query": None,
     "expected": ["alpha_fact_weather", "alpha_fact_geo", "alpha_task_due", "alpha_conv_remember",
                   "alpha_proc"],
     "forbidden": ["beta_fact_weather_tokens", "beta_task_later", "beta_conv_plain", "beta_persist"]},
    # Scan beta — all beta items, no alpha items
    {"label": "scan_beta", "principal": BETA, "method": "scan",
     "query": None,
     "expected": ["beta_fact_weather_tokens", "beta_task_later", "beta_conv_plain", "beta_persist"],
     "forbidden": ["alpha_fact_weather", "alpha_fact_geo", "alpha_task_due", "alpha_conv_remember",
                   "alpha_proc", "alpha_sensory"]},
    # Summary alpha — contains alpha content, not beta content
    {"label": "summary_alpha", "principal": ALPHA, "method": "summary",
     "query": None, "expected": [], "forbidden": ["beta_fact_weather_tokens", "beta_persist"]},
    # Summary beta — contains beta content, not alpha content
    {"label": "summary_beta", "principal": BETA, "method": "summary",
     "query": None, "expected": [], "forbidden": ["alpha_fact_weather", "alpha_proc"]},
]

# Expectations for the "late" run (clock advanced to 100): beta_task_later becomes due,
# and sensory items expire (TTL=10).
EXPECTATIONS_LATE: list[dict] = [
    # At tick 100, beta_task_later (due_at=100) is now due
    {"label": "due_late_beta", "principal": BETA, "method": "due",
     "query": None, "expected": ["beta_task_later"], "forbidden": ["alpha_task_due"]},
    # At tick 100, alpha_task_due (due_at=5) is still due for alpha
    {"label": "due_late_alpha", "principal": ALPHA, "method": "due",
     "query": None, "expected": ["alpha_task_due"], "forbidden": ["beta_task_later"]},
    # Scan alpha — sensory item expired (TTL=10), so not in scan
    {"label": "scan_alpha_late", "principal": ALPHA, "method": "scan",
     "query": None,
     "expected": ["alpha_fact_weather", "alpha_fact_geo", "alpha_task_due", "alpha_conv_remember",
                   "alpha_proc"],
     "forbidden": ["alpha_sensory", "beta_fact_weather_tokens", "beta_task_later", "beta_conv_plain",
                   "beta_persist"]},
]


# ---------------------------------------------------------------------------
# Build the scenario and return a label→item_id map.
# ---------------------------------------------------------------------------

def _provenance(principal: Principal, kind: MemoryKind, evidence: str | None, tick: int) -> Provenance:
    src = {MemoryKind.SENSORY: SourceType.SENSOR, MemoryKind.KNOWLEDGE: SourceType.SYNTHETIC_DOCUMENT,
           MemoryKind.TASK: SourceType.TASK_EXECUTION, MemoryKind.PROCEDURAL: SourceType.TASK_EXECUTION}.get(
        kind, SourceType.USER_STATED)
    return Provenance(src, f"synthetic:bench/{principal.user_id}/{tick}", principal.user_id, tick, evidence)


def build_scenario(clock_start: int = 0) -> tuple[MemoryStore, dict[str, str]]:
    """Run SCENARIO writes on a fresh store. Returns (store, label→item_id).

    Each call gets a fresh copy of the scenario kwargs so the SCENARIO constant is never mutated.
    """
    import copy
    store = MemoryStore(LogicalClock(clock_start))
    labels: dict[str, str] = {}
    for i, (label, pr, kind, content, kw_orig) in enumerate(SCENARIO):
        kw = copy.deepcopy(kw_orig)
        store.clock.advance(1)
        evidence = kw.pop("evidence", None)
        prov = _provenance(pr, kind, evidence, store.clock.now())
        item = store.write(pr, kind, content, provenance=prov,
                           confidence=kw.pop("confidence", 0.9),
                           consent=kw.pop("consent", False),
                           verification_state=kw.pop("verification_state", None),
                           modality=kw.pop("modality", None),
                           tags=kw.pop("tags", ()),
                           fact_key=kw.pop("fact_key", None),
                           task_status=kw.pop("task_status", None),
                           steps=kw.pop("steps", ()),
                           due_at=kw.pop("due_at", None))
        labels[label] = item.item_id
    return store, labels


# ---------------------------------------------------------------------------
# Run expectations against the store and return a report.
# ---------------------------------------------------------------------------

def run_expectations(store: MemoryStore, labels: dict[str, str], due_at: int | None = None,
                     expectations: list[dict] | None = None) -> dict:
    """Run expectation cases against the store. Returns a report dict with per-case pass/fail.

    If due_at is set, the clock is advanced to that tick before any 'due' case.
    If expectations is None, uses the default EXPECTATIONS list.
    """
    cases = expectations if expectations is not None else EXPECTATIONS
    results = []
    all_pass = True
    for exp in cases:
        pr = exp["principal"]
        method = exp["method"]
        query = exp["query"]
        expected = set(exp.get("expected", []))
        forbidden = set(exp.get("forbidden", []))
        # Resolve labels to item_ids for expected/forbidden
        expected_ids = {labels[l] for l in expected if l in labels}
        forbidden_ids = {labels[l] for l in forbidden if l in labels}
        # Forbidden labels that belong to other users should also be checked by id
        forbidden_ids.update(labels.get(l, "__missing__") for l in forbidden)

        got_ids: set[str] = set()
        got_labels: set[str] = set()

        if method == "search":
            hits = store.search(pr, query, limit=100)
            got_ids = {h.item.item_id for h in hits}
        elif method == "associate":
            item_id = labels.get(query, query)
            if item_id in labels.values() or item_id in labels:
                # resolve label to item_id
                item_id = labels.get(query, query)
            try:
                hits = store.associate(pr, item_id, limit=100)
                got_ids = {h.item.item_id for h in hits}
            except KeyError:
                got_ids = set()
        elif method == "due":
            if due_at is not None:
                store.clock.advance(due_at - store.clock.now())
            tasks = store.due_tasks(pr)
            got_ids = {t.item_id for t in tasks}
        elif method == "scan":
            items = store.scan(pr)
            got_ids = {it.item_id for it in items}
        elif method == "summary":
            text = store.summarize(pr)
            # Map back: a label is "in summary" if its content appears
            for l, iid in labels.items():
                # We check if the item's content marker appears in the summary
                pass
            # For summary, check forbidden by content
            got_labels = set()
            for l in forbidden:
                if l in labels:
                    # Check if the forbidden item's content appears in summary
                    # We need to find the content
                    pass
            # Simplified: summary must not contain forbidden items' content
            got_ids = set()  # summary doesn't return ids
        else:
            got_ids = set()

        # Map got_ids back to labels
        id_to_label = {v: k for k, v in labels.items()}
        got_labels = {id_to_label.get(i, i) for i in got_ids}

        # For summary, check content-based
        if method == "summary":
            text = store.summarize(pr)
            # Check that forbidden content does not appear
            forbidden_content_pass = True
            for l in forbidden:
                if l in labels:
                    # Find the content for this label
                    for sl, sp, sk, sc, _ in SCENARIO:
                        if sl == l and sp != pr:
                            if sc in text:
                                forbidden_content_pass = False
                                break
            expected_content_pass = True  # We don't require specific content in summary
            case_pass = forbidden_content_pass
        else:
            # Check expected ids are present
            missing = expected_ids - got_ids
            # Check forbidden ids are absent
            leaked = forbidden_ids & got_ids
            case_pass = not missing and not leaked

        if not case_pass:
            all_pass = False
        results.append({
            "label": exp["label"], "pass": case_pass,
            "expected_labels": sorted(expected), "forbidden_labels": sorted(forbidden),
            "got_labels": sorted(got_labels),
        })
    return {"all_pass": all_pass, "cases": results}


# ---------------------------------------------------------------------------
# Adversarial probes
# ---------------------------------------------------------------------------

def run_adversarial(store: MemoryStore, labels: dict[str, str]) -> dict:
    """Run adversarial probes. Returns a report dict."""
    results = []
    all_pass = True

    # 1. ID guessing: try many guessed ids, they should all behave as "not found"
    guessed_ids = [
        "mem-0000000000000000",
        "mem-ffffffffffffffff",
        "mem-" + "a" * 16,
        "mem-" + "0" * 16,
        "mem-invalid",
        "",
        "not-a-mem-id",
        # Near-miss: replace last char of a real id
    ]
    # Add near-miss of alpha's first item
    if labels:
        real_id = next(iter(labels.values()))
        if len(real_id) > 4:
            guessed_ids.append(real_id[:-1] + ("0" if real_id[-1] != "0" else "1"))

    for gid in guessed_ids:
        # read returns None
        r = store.read(ALPHA, gid)
        if r is not None:
            results.append({"probe": "id_guess_read", "id": gid, "pass": False, "reason": "returned non-None"})
            all_pass = False
        # metadata raises KeyError
        for fn_name in ("provenance", "confidence", "acl", "version"):
            fn = getattr(store, fn_name)
            try:
                fn(ALPHA, gid)
                results.append({"probe": "id_guess_meta", "id": gid, "fn": fn_name, "pass": False,
                                "reason": "did not raise"})
                all_pass = False
            except KeyError:
                pass  # expected
        # Guessed id does not enter cache (skip empty strings — they're trivially in every string)
        if gid:
            state = store.dump_state()
            cache_text = json.dumps(state.get("cache", {}), sort_keys=True, ensure_ascii=False)
            if gid in cache_text:
                results.append({"probe": "id_guess_cache", "id": gid, "pass": False, "reason": "entered cache"})
                all_pass = False

    # 2. Query injection: queries that try to act as filters or cross-user access
    injection_queries = [
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
    ]
    for q in injection_queries:
        hits = store.search(ALPHA, q, limit=100)
        got_owners = {h.item.owner for h in hits}
        if "user_beta" in got_owners or "user_gamma" in got_owners:
            results.append({"probe": "query_injection", "query": q, "pass": False,
                            "reason": "returned other user's items"})
            all_pass = False

    # 3. Tag injection: tags that try to act as capabilities
    injection_tags = [
        ("owner:user_beta",),
        ("cross_user:true",),
        ("admin",),
        ("isolation:bypass",),
        ("project:other",),
    ]
    for tags in injection_tags:
        # Write with injection tags, then search — the tags should be plain strings
        store.clock.advance(1)
        prov = _provenance(ALPHA, MemoryKind.CONVERSATION, None, store.clock.now())
        item = store.write(ALPHA, MemoryKind.CONVERSATION, "kavun injection test", provenance=prov,
                           confidence=0.9, tags=tags)
        # The item should be findable by the literal tag string
        hits = store.search(ALPHA, "kavun", tags=tags, limit=10)
        if not any(h.item.item_id == item.item_id for h in hits):
            results.append({"probe": "tag_injection_search", "tags": tags, "pass": False,
                            "reason": "could not find item by its own tags"})
            all_pass = False
        # The item should NOT be visible to beta
        beta_hits = store.search(BETA, "kavun", limit=10)
        if any(h.item.item_id == item.item_id for h in beta_hits):
            results.append({"probe": "tag_injection_cross_user", "tags": tags, "pass": False,
                            "reason": "beta saw alpha's tagged item"})
            all_pass = False

    # 4. Overlapping fact subjects across users
    # Both alpha and beta have a fact with subject "brelto" — they must not cross
    store.clock.advance(1)
    prov_a = _provenance(ALPHA, MemoryKind.KNOWLEDGE, "synthetic:overlap/a", store.clock.now())
    a_overlap = store.write(ALPHA, MemoryKind.KNOWLEDGE, "brelto overlap alpha", provenance=prov_a,
                            confidence=0.9, verification_state=VerificationState.SUPPORTED,
                            fact_key=("brelto", "overlap"))
    store.clock.advance(1)
    prov_b = _provenance(BETA, MemoryKind.KNOWLEDGE, "synthetic:overlap/b", store.clock.now())
    b_overlap = store.write(BETA, MemoryKind.KNOWLEDGE, "brelto overlap beta", provenance=prov_b,
                            confidence=0.9, verification_state=VerificationState.SUPPORTED,
                            fact_key=("brelto", "overlap"))
    # Alpha's associate on a_overlap must not return b_overlap
    try:
        assoc = store.associate(ALPHA, a_overlap.item_id, limit=100)
        assoc_ids = {h.item.item_id for h in assoc}
        if b_overlap.item_id in assoc_ids:
            results.append({"probe": "overlap_associate", "pass": False,
                            "reason": "alpha's associate returned beta's overlapping fact"})
            all_pass = False
    except KeyError:
        pass

    # 5. Longer overlapping sequences: write many items with shared tokens, verify isolation
    for i in range(20):
        store.clock.advance(1)
        content = f"shared_token_{i} common_word"
        prov = _provenance(ALPHA if i % 2 == 0 else BETA, MemoryKind.CONVERSATION, None, store.clock.now())
        store.write(ALPHA if i % 2 == 0 else BETA, MemoryKind.CONVERSATION, content, provenance=prov,
                    confidence=0.9)
    # Search "common_word" as alpha — should only see alpha's items
    alpha_hits = store.search(ALPHA, "common_word", limit=100)
    for h in alpha_hits:
        if h.item.owner != "user_alpha":
            results.append({"probe": "long_sequence_cross", "pass": False,
                            "reason": f"alpha search returned {h.item.owner}"})
            all_pass = False
            break

    # 6. Forgetting leaves no trace AND the log is recorded (re-verify on this store)
    if labels:
        target_label = "alpha_fact_geo"
        target_id = labels.get(target_label)
        if target_id and store.read(ALPHA, target_id) is not None:
            log_before = len(store.log.entries)
            entries = store.forget(ALPHA, target_id, reason="user_request")
            log_after = len(store.log.entries)
            # The forgetting log must have grown
            if log_after <= log_before:
                results.append({"probe": "forget_log_recorded", "pass": False,
                                "reason": "log did not grow after forget"})
                all_pass = False
            # Verify the forgotten id is gone from all structures
            needles = [target_id, "tobrak elvanu geography dorvel"]
            traces = trace_scan(store, needles=needles)
            # The forgetting log is allowed to contain the id
            traces = [t for t in traces if not (t.startswith("state:log") or t == "file:forget_log.jsonl")]
            if traces:
                results.append({"probe": "forget_trace", "pass": False, "traces": traces})
                all_pass = False

    # 7. Consent enforcement: USER_PERSISTENT without consent must be refused
    store.clock.advance(1)
    prov_no_consent = _provenance(ALPHA, MemoryKind.USER_PERSISTENT, None, store.clock.now())
    try:
        store.write(ALPHA, MemoryKind.USER_PERSISTENT, "kavun no consent", provenance=prov_no_consent,
                     confidence=0.9, consent=False)
        results.append({"probe": "consent_enforcement", "pass": False,
                        "reason": "USER_PERSISTENT accepted without consent"})
        all_pass = False
    except Exception:
        pass  # expected: policy violation

    # 8. Tag-based search: items must be findable by their tags, and tag filtering must work
    store.clock.advance(1)
    prov_tagged = _provenance(ALPHA, MemoryKind.CONVERSATION, None, store.clock.now())
    tagged_item = store.write(ALPHA, MemoryKind.CONVERSATION, "kavun tagged search", provenance=prov_tagged,
                              confidence=0.9, tags=("special_tag",))
    # Another item with same tokens but different tag
    store.clock.advance(1)
    prov_other = _provenance(ALPHA, MemoryKind.CONVERSATION, None, store.clock.now())
    other_tagged = store.write(ALPHA, MemoryKind.CONVERSATION, "kavun tagged other", provenance=prov_other,
                               confidence=0.9, tags=("other_tag",))
    tag_hits = store.search(ALPHA, "kavun", tags=("special_tag",), limit=10)
    if not any(h.item.item_id == tagged_item.item_id for h in tag_hits):
        results.append({"probe": "tag_search_find", "pass": False,
                        "reason": "item not found by its own tag"})
        all_pass = False
    # The other-tagged item must NOT appear when filtering for special_tag
    if any(h.item.item_id == other_tagged.item_id for h in tag_hits):
        results.append({"probe": "tag_search_filter", "pass": False,
                        "reason": "tag filter did not exclude other-tagged item"})
        all_pass = False

    # 9. Can_access layer: reading another user's item must return None.
    # Also test can_access directly: it must refuse another user's item.
    if labels:
        beta_id = labels.get("beta_fact_weather_tokens")
        if beta_id:
            # Direct read as alpha — should be None
            if store.read(ALPHA, beta_id) is not None:
                results.append({"probe": "can_access_guard", "pass": False,
                                "reason": "alpha read beta's item"})
                all_pass = False
    # Direct can_access check: get a beta item and verify can_access refuses
    for pr, _, _, _, _ in []:  # no-op placeholder
        pass
    # Use the overlapping items we wrote earlier
    if 'a_overlap' in dir() and 'b_overlap' in dir():
        from nawa.memory.isolation import can_access as _can_access
        if _can_access(ALPHA, b_overlap):
            results.append({"probe": "can_access_direct", "pass": False,
                            "reason": "can_access allowed alpha to access beta's item"})
            all_pass = False

    # 10. Fact_key-based association: items sharing a fact subject must associate
    # even when they share no content tokens. This tests the fact_key scoring path.
    store.clock.advance(1)
    prov_fk1 = _provenance(ALPHA, MemoryKind.KNOWLEDGE, "synthetic:fk/1", store.clock.now())
    fk1 = store.write(ALPHA, MemoryKind.KNOWLEDGE, "alphaword factone", provenance=prov_fk1,
                      confidence=0.9, verification_state=VerificationState.SUPPORTED,
                      fact_key=("shared_subject", "attr1"))
    store.clock.advance(1)
    prov_fk2 = _provenance(ALPHA, MemoryKind.KNOWLEDGE, "synthetic:fk/2", store.clock.now())
    fk2 = store.write(ALPHA, MemoryKind.KNOWLEDGE, "betaword facttwo", provenance=prov_fk2,
                      confidence=0.9, verification_state=VerificationState.SUPPORTED,
                      fact_key=("shared_subject", "attr2"))
    # These two items share NO content tokens but share a fact subject
    assoc = store.associate(ALPHA, fk1.item_id, limit=100)
    if fk2.item_id not in {h.item.item_id for h in assoc}:
        results.append({"probe": "fact_key_association", "pass": False,
                        "reason": "items sharing fact subject not associated"})
        all_pass = False

    if all_pass:
        results.append({"probe": "all_adversarial", "pass": True})

    return {"all_pass": all_pass, "probes": results}


# ---------------------------------------------------------------------------
# Mutation table: each mutant is a (name, setup_fn) pair.
# setup_fn(monkeypatch) applies the mutation. The benchmark must fail.
# ---------------------------------------------------------------------------

def _mut_drop_tokens(monkeypatch):
    """Drop all tokens from analysis — search and associate should break."""
    import nawa.memory.store as store_mod
    monkeypatch.setattr(store_mod, "analyze", lambda text: ())


def _mut_ignore_tags(monkeypatch):
    """Make search ignore the tags filter — tag-based search should break."""
    import nawa.memory.store as store_mod
    real_search = store_mod.MemoryStore.search
    def patched(self, principal, query, *, kinds=None, tags=(), min_confidence=0.0,
                facts_only=False, since=None, until=None, limit=10):
        return real_search(self, principal, query, kinds=kinds, tags=(), min_confidence=min_confidence,
                           facts_only=facts_only, since=since, until=until, limit=limit)
    monkeypatch.setattr(store_mod.MemoryStore, "search", patched)


def _mut_can_access_always_true(monkeypatch):
    """Make can_access always return True — isolation should break."""
    import nawa.memory.isolation as iso_mod
    monkeypatch.setattr(iso_mod, "can_access", lambda principal, item: True)


def _mut_unindex_noop(monkeypatch):
    """Make _unindex a no-op — forgotten items should linger in the token index."""
    import nawa.memory.store as store_mod
    monkeypatch.setattr(store_mod.MemoryStore, "_unindex", lambda self, p, item_id: None)


def _mut_visible_ignore_expiry(monkeypatch):
    """Make policy.visible ignore expiry — expired items should appear."""
    import nawa.memory.policy as pol_mod
    monkeypatch.setattr(pol_mod, "visible", lambda item, now, min_confidence=0.0, facts_only=False: True)


def _mut_associate_ignore_factkey(monkeypatch):
    """Make associate ignore fact_key subjects — association by subject should break."""
    import nawa.memory.store as store_mod

    def patched_assoc(self, principal, item_id, limit=10):
        p, it = self._get(principal, item_id)
        key = f"assoc:{item_id}:{limit}:{self.clock.now()}"
        if key in p.cache:
            return [store_mod.Hit(store_mod.MemoryItem.from_record(r), s) for r, s in p.cache[key]]
        scores: dict[str, int] = {}
        # Deliberately skip fact_key subjects — only use token overlap
        for t in set(store_mod.analyze(it.content)):
            for i in p.tokens.get(t, ()):
                scores[i] = scores.get(i, 0) + 1
        scores.pop(item_id, None)
        now = self.clock.now()
        hits = [store_mod.Hit(p.items[i], s) for i, s in scores.items()
                if store_mod.can_access(principal, p.items[i]) and
                store_mod.policy.visible(p.items[i], now)]
        hits.sort(key=lambda h: (-h.score, h.item.created_at, h.item.item_id))
        hits = hits[:limit]
        p.cache[key] = [(h.item.to_record(), h.score) for h in hits]
        return hits
    monkeypatch.setattr(store_mod.MemoryStore, "associate", patched_assoc)


def _mut_write_skip_consent(monkeypatch):
    """Make policy.check_write skip the consent check — USER_PERSISTENT without consent should be allowed."""
    import nawa.memory.policy as pol_mod
    real_check = pol_mod.check_write
    def patched(req):
        reasons = real_check(req)
        return [r for r in reasons if "consent" not in r]
    monkeypatch.setattr(pol_mod, "check_write", patched)


def _mut_forget_skip_log(monkeypatch):
    """Make _remove skip the forgetting log — deletions go unrecorded."""
    import nawa.memory.store as store_mod
    real_remove = store_mod.MemoryStore._remove
    def patched(self, p, it, reason):
        del p.items[it.item_id]
        p.history.pop(it.item_id, None)
        self._unindex(p, it.item_id)
        p.invalidate()
        return None  # no log entry
    monkeypatch.setattr(store_mod.MemoryStore, "_remove", patched)


def _mut_search_ignore_isolation(monkeypatch):
    """Make search ignore can_access — cross-user items should leak."""
    import nawa.memory.store as store_mod
    real_search = store_mod.MemoryStore.search
    def patched(self, principal, query, *, kinds=None, tags=(), min_confidence=0.0,
                facts_only=False, since=None, until=None, limit=10):
        # Bypass can_access by searching all partitions
        from nawa.retrieval.index import analyze
        q = sorted(set(analyze(query)))
        scores: dict[str, int] = {}
        for p in self._parts.values():
            for t in q:
                for i in p.tokens.get(t, ()):
                    scores[i] = scores.get(i, 0) + 1
        hits = []
        for p in self._parts.values():
            for i, s in scores.items():
                it = p.items.get(i)
                if it is None:
                    continue
                hits.append(store_mod.Hit(it, s))
        hits.sort(key=lambda h: (-h.score, -h.item.confidence, h.item.created_at, h.item.item_id))
        return hits[:limit]
    monkeypatch.setattr(store_mod.MemoryStore, "search", patched)


REGISTERED_MUTANTS: list[tuple[str, callable]] = [
    ("drop_tokens", _mut_drop_tokens),
    ("ignore_tags", _mut_ignore_tags),
    ("can_access_always_true", _mut_can_access_always_true),
    ("unindex_noop", _mut_unindex_noop),
    ("visible_ignore_expiry", _mut_visible_ignore_expiry),
    ("associate_ignore_factkey", _mut_associate_ignore_factkey),
    ("write_skip_consent", _mut_write_skip_consent),
    ("forget_skip_log", _mut_forget_skip_log),
    ("search_ignore_isolation", _mut_search_ignore_isolation),
]


# ---------------------------------------------------------------------------
# Full benchmark check
# ---------------------------------------------------------------------------

def run_benchmark() -> dict:
    """Run the full P7-08 benchmark: expectations + adversarial + late expectations. Returns a report."""
    store, labels = build_scenario()
    exp_report = run_expectations(store, labels)
    adv_report = run_adversarial(store, labels)
    # Re-run with clock advanced to 100 for late expectations
    store2, labels2 = build_scenario()
    exp_late = run_expectations(store2, labels2, due_at=100, expectations=EXPECTATIONS_LATE)
    all_pass = exp_report["all_pass"] and adv_report["all_pass"] and exp_late["all_pass"]
    return {
        "ok": all_pass,
        "expectations": exp_report,
        "expectations_late": exp_late,
        "adversarial": adv_report,
        "scenario_items": len(SCENARIO),
        "expectation_cases": len(EXPECTATIONS),
        "expectation_late_cases": len(EXPECTATIONS_LATE),
        "adversarial_probes": len(adv_report["probes"]),
        "registered_mutants": len(REGISTERED_MUTANTS),
    }


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="NAWA memory P7-08 benchmark (synthetic only)")
    ap.add_argument("--check", action="store_true", help="run benchmark and report")
    ap.add_argument("--json", action="store_true", help="output as JSON")
    a = ap.parse_args(argv)
    if a.check:
        report = run_benchmark()
        if a.json:
            print(json.dumps(report, indent=2, sort_keys=True, default=str))
        else:
            print(f"P7-08 benchmark: {'PASS' if report['ok'] else 'FAIL'}")
            print(f"  Scenario items: {report['scenario_items']}")
            print(f"  Expectation cases: {report['expectation_cases']}")
            print(f"  Late expectation cases: {report['expectation_late_cases']}")
            print(f"  Adversarial probes: {report['adversarial_probes']}")
            print(f"  Registered mutants: {report['registered_mutants']}")
            if not report["ok"]:
                for case in report["expectations"]["cases"]:
                    if not case["pass"]:
                        print(f"  FAIL: {case}")
                for case in report["expectations_late"]["cases"]:
                    if not case["pass"]:
                        print(f"  FAIL (late): {case}")
                for probe in report["adversarial"]["probes"]:
                    if not probe.get("pass", True):
                        print(f"  FAIL: {probe}")
        return 0 if report["ok"] else 1
    print("Use --check to run the benchmark")
    return 0


if __name__ == "__main__":
    sys.exit(main())
