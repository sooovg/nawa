"""P7-05 provenance, confidence, timestamp and owner on every item, and the write/update policy (ADR-0009)."""

from __future__ import annotations

import math

import pytest

from memory_support import ALPHA, new_store, put, pv
from nawa.memory import MemoryKind, Modality, PolicyViolation, Provenance, SourceType, TaskStatus
from nawa.memory import consolidation
from nawa.memory.provenance import combine_confidence, problems
from nawa.memory.types import iso
from nawa.verification.states import VerificationState

K = MemoryKind


def test_every_item_has_source_confidence_timestamp_and_owner() -> None:
    st = new_store()
    st.clock.advance(65)
    for k in MemoryKind:
        put(st, ALPHA, k, f"brelto {k.value}")
    consolidation.apply(st, ALPHA)
    items = st.scan(ALPHA)
    assert {it.kind for it in items} == set(MemoryKind)
    for it in items:
        assert problems(it.provenance) == []
        assert it.provenance.source_ref.startswith("synthetic:")
        assert 0.0 <= it.confidence <= 1.0
        assert it.owner == "user_alpha" and it.project == "project_default"
        assert it.timestamp == iso(it.updated_at) == "2026-01-01T00:01:05Z"
        assert st.provenance(ALPHA, it.item_id) == it.provenance
        assert st.confidence(ALPHA, it.item_id) == it.confidence


@pytest.mark.parametrize("bad,reason", [
    (None, "provenance_missing"),
    (Provenance(SourceType.USER_STATED, "https://real.example/page", "user_alpha", 0), "source_ref_not_synthetic"),
    (Provenance(SourceType.USER_STATED, "synthetic:x", "", 0), "author_missing"),
    (Provenance(SourceType.USER_STATED, "synthetic:x", "user_alpha", -1), "recorded_at_invalid"),
    (Provenance(SourceType.USER_STATED, "synthetic:x", "user_alpha", 0, "doi:10.1/real"), "evidence_ref_not_synthetic"),
    (Provenance(SourceType.CONSOLIDATION, "synthetic:x", "user_alpha", 0), "consolidation_without_sources"),
    (Provenance(SourceType.USER_STATED, "synthetic:x", "user_alpha", 0, None, ("mem-1",)),
     "derived_from_without_consolidation"),
])
def test_invalid_or_real_provenance_is_refused(bad, reason) -> None:
    st = new_store()
    with pytest.raises(PolicyViolation) as e:
        st.write(ALPHA, K.CONVERSATION, "kavun", provenance=bad, confidence=0.5)
    assert reason in e.value.reasons and st.scan(ALPHA) == []


@pytest.mark.parametrize("c", [-0.01, 1.01, math.nan, math.inf, True, "0.5", None])
def test_confidence_must_be_a_finite_number_in_unit_interval(c) -> None:
    with pytest.raises(PolicyViolation, match="confidence_out_of_range"):
        new_store().write(ALPHA, K.CONVERSATION, "kavun", provenance=pv(), confidence=c)


def test_combined_confidence_is_the_minimum() -> None:
    assert combine_confidence([0.9, 0.4, 0.7]) == 0.4


@pytest.mark.parametrize("text,reason", [
    ("mail me at someone@example.com", "pii:email"),
    ("token hf_" + "a" * 30, "pii:secret"),
    ("", "content_empty"),
    ("x" * 4001, "content_too_long"),
])
def test_pii_secrets_and_bad_content_are_refused_not_stored(text, reason) -> None:
    st = new_store()
    with pytest.raises(PolicyViolation) as e:
        st.write(ALPHA, K.CONVERSATION, text, provenance=pv(), confidence=0.5)
    assert reason in e.value.reasons
    assert "someone@example.com" not in str(e.value) and "hf_" not in str(e.value)   # reasons never echo content
    assert st.dump_state()["items"] == {}


def test_user_persistent_memory_requires_explicit_consent() -> None:
    with pytest.raises(PolicyViolation, match="consent_required"):
        new_store().write(ALPHA, K.USER_PERSISTENT, "kavun", provenance=pv(), confidence=0.5)


def test_knowledge_requires_state_and_evidence_and_refuses_contradicted() -> None:
    st = new_store()
    with pytest.raises(PolicyViolation) as e:
        st.write(ALPHA, K.KNOWLEDGE, "mirsel is blue", provenance=pv(), confidence=0.5)
    assert {"verification_state_required", "evidence_ref_required"} <= set(e.value.reasons)
    with pytest.raises(PolicyViolation, match="contradicted_knowledge_refused"):
        put(st, ALPHA, K.KNOWLEDGE, "mirsel is red", verification_state=VerificationState.CONTRADICTED)
    fact = put(st, ALPHA, K.KNOWLEDGE, "mirsel is blue")
    belief = put(st, ALPHA, K.KNOWLEDGE, "mirsel is tall", verification_state=VerificationState.UNCERTAIN)
    assert fact.epistemic == "fact" and belief.epistemic == "belief"
    assert [h.item.item_id for h in st.search(ALPHA, "mirsel", facts_only=True)] == [fact.item_id]


def test_a_fact_never_changes_without_new_provenance() -> None:
    st = new_store()
    f = put(st, ALPHA, K.KNOWLEDGE, "mirsel is blue")
    st.clock.advance(5)
    same = f.provenance
    with pytest.raises(PolicyViolation) as e:
        st.update(ALPHA, f.item_id, "mirsel is green", provenance=same)
    assert {"provenance_not_new", "knowledge_change_without_new_evidence"} <= set(e.value.reasons)
    with pytest.raises(PolicyViolation, match="knowledge_change_without_new_evidence"):
        st.update(ALPHA, f.item_id, "mirsel is green",
                  provenance=pv("synthetic:doc/2", 5, SourceType.SYNTHETIC_DOCUMENT, evidence=None))
    assert st.read(ALPHA, f.item_id).content == "mirsel is blue" and st.version(ALPHA, f.item_id) == 1
    new = st.update(ALPHA, f.item_id, "mirsel is green",
                    provenance=pv("synthetic:doc/4", 5, SourceType.SYNTHETIC_DOCUMENT, evidence="synthetic:ev/4"))
    assert new.version == 2 and [v.content for v in st.versions(ALPHA, f.item_id)] == ["mirsel is blue",
                                                                                     "mirsel is green"]
    assert new.updated_at == 5 and new.created_at == 0


def test_update_refuses_older_provenance() -> None:
    st = new_store()
    st.clock.advance(10)
    c = put(st, ALPHA, K.CONVERSATION, "kavun", provenance=pv("synthetic:t/1", 10))
    with pytest.raises(PolicyViolation, match="provenance_older_than_current"):
        st.update(ALPHA, c.item_id, "kavun two", provenance=pv("synthetic:t/2", 9))


def test_update_cannot_drop_consolidation_lineage() -> None:
    st = new_store()
    put(st, ALPHA, K.CONVERSATION, "i like kavun", consent=True, tags=("remember",))
    (promoted,), _ = consolidation.apply(st, ALPHA)
    with pytest.raises(PolicyViolation, match="lineage_dropped"):
        st.update(ALPHA, promoted.item_id, "i like nupra", provenance=pv("synthetic:t/9", 0))


def test_read_only_items_refuse_update_but_obey_deletion() -> None:
    st = new_store()
    r = put(st, ALPHA, K.PROCEDURAL, "fixed procedure", read_only=True)
    with pytest.raises(PolicyViolation, match="read_only"):
        st.update(ALPHA, r.item_id, "changed", provenance=pv("synthetic:t/2", 0))
    st.forget(ALPHA, r.item_id)
    assert st.read(ALPHA, r.item_id) is None


@pytest.mark.parametrize("kind,kw,reason", [
    (K.SENSORY, {}, "modality_required"),
    (K.SENSORY, {"modality": Modality.AUDIO, "ttl": 11}, "sensory_ttl_too_long"),
    (K.TASK, {}, "task_status_required"),
    (K.CONVERSATION, {"task_status": TaskStatus.OPEN}, "task_fields_only_for_task"),
    (K.PROCEDURAL, {"modality": Modality.VISUAL}, "modality_only_for_sensory"),
    (K.CONVERSATION, {"verification_state": VerificationState.SUPPORTED}, "verification_state_only_for_knowledge"),
    (K.CONVERSATION, {"tags": ("Bad Tag",)}, "tag_invalid"),
    (K.CONVERSATION, {"tags": ("domain:astrology",)}, "domain_tag_unknown"),
    (K.KNOWLEDGE, {"fact_key": ("only",)}, "fact_key_invalid"),
])
def test_kind_specific_write_rules(kind, kw, reason) -> None:
    st = new_store()
    base = {"provenance": pv("synthetic:t/1", 0, evidence="synthetic:ev/1"), "confidence": 0.5}
    if kind is K.KNOWLEDGE:
        base["verification_state"] = VerificationState.SUPPORTED
    with pytest.raises(PolicyViolation) as e:
        st.write(ALPHA, kind, "brelto", **{**base, **kw})
    assert reason in e.value.reasons


def test_sensory_buffers_expire_within_seconds_and_long_term_kinds_do_not() -> None:
    st = new_store()
    s = put(st, ALPHA, K.SENSORY, "beep", modality=Modality.AUDIO)
    c = put(st, ALPHA, K.CONVERSATION, "dialogue")
    u = put(st, ALPHA, K.USER_PERSISTENT, "pref")
    assert s.expires_at == 10 and c.expires_at == 3600 and u.expires_at is None
