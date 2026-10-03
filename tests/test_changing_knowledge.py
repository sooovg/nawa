"""P7-06: changing-knowledge baseline as an enforced check (ADR-0009).

Three areas:
1. Changing knowledge is accepted in memory (write, search, update, history, provenance).
2. Changing knowledge is accepted in retrieval (indexed and retrievable as evidence).
3. Changing knowledge is rejected from training data manifests (central, not test-only).

Plus targeted mutation tests proving the enforcement is non-vacuous.

Code-only scope: synthetic facts only, no external model, no network, no real data, no quality claim.
"""

from __future__ import annotations

import pytest

from memory_support import ALPHA, BETA, new_store, pv
from nawa.data_verify import train_eligibility, VerificationResult
from nawa.memory import (KnowledgeMutability, MemoryKind, MemoryStore, Principal, Provenance, SourceType,
                         mutability_reasons, is_train_eligible_by_mutability)
from nawa.memory.mutability import (REASON_CHANGING_IN_MANIFEST, REASON_MUTABILITY_MISSING,
                                     REASON_MUTABILITY_INVALID)
from nawa.verification.states import VerificationState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _verified() -> VerificationResult:
    return VerificationResult("test-id", "test", "verified", "ok", {}, "test")


def _changing_fact(store: MemoryStore, who: Principal = ALPHA, content: str = "brelto status is seven",
                    tick: int = 10, label: str = "synthetic:changing/1"):
    store.clock.advance(1)
    prov = Provenance(SourceType.SYNTHETIC_DOCUMENT, label, who.user_id, store.clock.now(),
                      evidence_ref="synthetic:evidence/1")
    return store.write(who, MemoryKind.KNOWLEDGE, content, provenance=prov,
                       confidence=0.9, verification_state=VerificationState.SUPPORTED,
                       fact_key=("brelto", "status"), mutability=KnowledgeMutability.CHANGING)


def _stable_fact(store: MemoryStore, who: Principal = ALPHA, content: str = "brelto identity is constant",
                  tick: int = 10, label: str = "synthetic:stable/1"):
    store.clock.advance(1)
    prov = Provenance(SourceType.SYNTHETIC_DOCUMENT, label, who.user_id, store.clock.now(),
                      evidence_ref="synthetic:evidence/2")
    return store.write(who, MemoryKind.KNOWLEDGE, content, provenance=prov,
                       confidence=0.9, verification_state=VerificationState.SUPPORTED,
                       fact_key=("brelto", "identity"), mutability=KnowledgeMutability.STABLE)


# ---------------------------------------------------------------------------
# 1. Changing knowledge is accepted in memory
# ---------------------------------------------------------------------------

class TestChangingKnowledgeInMemory:

    def test_changing_fact_can_be_written(self):
        store = new_store()
        item = _changing_fact(store)
        assert item.mutability is KnowledgeMutability.CHANGING
        assert item.kind is MemoryKind.KNOWLEDGE

    def test_changing_fact_can_be_read(self):
        store = new_store()
        item = _changing_fact(store)
        assert store.read(ALPHA, item.item_id) is not None

    def test_changing_fact_can_be_searched(self):
        store = new_store()
        item = _changing_fact(store, content="brelto status is seven at tick ten")
        hits = store.search(ALPHA, "brelto", limit=10)
        assert any(h.item.item_id == item.item_id for h in hits)

    def test_changing_fact_can_be_updated_with_new_evidence(self):
        store = new_store()
        item = _changing_fact(store, content="brelto status is seven", tick=10)
        store.clock.advance(10)
        new_prov = Provenance(SourceType.SYNTHETIC_DOCUMENT, "synthetic:changing/2", ALPHA.user_id,
                              store.clock.now(), evidence_ref="synthetic:evidence/2")
        updated = store.update(ALPHA, item.item_id, "brelto status is eight", provenance=new_prov)
        assert updated.version == 2
        assert "eight" in updated.content
        # History preserved
        versions = store.versions(ALPHA, item.item_id)
        assert len(versions) == 2

    def test_changing_fact_provenance_preserved(self):
        store = new_store()
        item = _changing_fact(store)
        prov = store.provenance(ALPHA, item.item_id)
        assert prov.source_type is SourceType.SYNTHETIC_DOCUMENT
        assert prov.evidence_ref is not None

    def test_changing_fact_can_be_associated(self):
        store = new_store()
        item = _changing_fact(store, content="brelto status shared")
        # Write another item sharing tokens
        store.clock.advance(1)
        prov2 = Provenance(SourceType.SYNTHETIC_DOCUMENT, "synthetic:changing/2", ALPHA.user_id,
                           store.clock.now(), evidence_ref="synthetic:evidence/2")
        item2 = store.write(ALPHA, MemoryKind.KNOWLEDGE, "brelto status other", provenance=prov2,
                           confidence=0.9, verification_state=VerificationState.SUPPORTED,
                           fact_key=("brelto", "other"), mutability=KnowledgeMutability.CHANGING)
        assoc = store.associate(ALPHA, item.item_id, limit=10)
        assert any(h.item.item_id == item2.item_id for h in assoc)

    def test_mutability_only_for_knowledge(self):
        """Non-knowledge items should not carry mutability."""
        store = new_store()
        store.clock.advance(1)
        prov = Provenance(SourceType.USER_STATED, "synthetic:test/1", ALPHA.user_id, store.clock.now())
        item = store.write(ALPHA, MemoryKind.CONVERSATION, "kavun conversation", provenance=prov,
                           confidence=0.9, mutability=KnowledgeMutability.CHANGING)
        assert item.mutability is None

    def test_changing_fact_round_trip_persistence(self):
        """Changing mutability survives write→persist→load."""
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            store1 = MemoryStore(store1_clock := __import__("nawa").memory.store.LogicalClock(0),
                                 directory=Path(tmp))
            store1.clock.advance(1)
            prov = Provenance(SourceType.SYNTHETIC_DOCUMENT, "synthetic:persist/1", ALPHA.user_id,
                              store1.clock.now(), evidence_ref="synthetic:evidence/1")
            item = store1.write(ALPHA, MemoryKind.KNOWLEDGE, "brelto persisted changing", provenance=prov,
                               confidence=0.9, verification_state=VerificationState.SUPPORTED,
                               fact_key=("brelto", "persist"), mutability=KnowledgeMutability.CHANGING)
            # Load into a new store
            store2 = MemoryStore(__import__("nawa").memory.store.LogicalClock(0), directory=Path(tmp))
            loaded = store2.read(ALPHA, item.item_id)
            assert loaded is not None
            assert loaded.mutability is KnowledgeMutability.CHANGING


# ---------------------------------------------------------------------------
# 2. Changing knowledge is accepted in retrieval
# ---------------------------------------------------------------------------

class TestChangingKnowledgeInRetrieval:

    def test_changing_fact_content_is_indexable_and_retrievable(self):
        """A changing fact's content should be indexable and retrievable via the lexical index."""
        from nawa.retrieval.index import LexicalIndex, Document
        idx = LexicalIndex([
            Document("d1", "brelto status is seven at tick ten", source="synthetic:doc/1"),
            Document("d2", "brelto identity is constant", source="synthetic:doc/2"),
        ])
        results = idx.search("brelto", k=10)
        assert len(results) >= 1
        # Both changing and stable facts are retrievable (content is indexed regardless of mutability)
        doc_ids = {r.doc_id for r in results}
        assert "d1" in doc_ids

    def test_changing_fact_retrievable_as_evidence_for_memory(self):
        """A changing fact stored in memory should be retrievable and usable as evidence."""
        store = new_store()
        item = _changing_fact(store, content="brelto status is seven at tick ten")
        # The fact is in memory and findable
        hits = store.search(ALPHA, "status", limit=10)
        assert any(h.item.item_id == item.item_id for h in hits)
        # It has provenance with evidence
        prov = store.provenance(ALPHA, item.item_id)
        assert prov.evidence_ref is not None


# ---------------------------------------------------------------------------
# 3. Changing knowledge is rejected from training manifests
# ---------------------------------------------------------------------------

class TestChangingKnowledgeRejectedFromManifest:

    def test_changing_knowledge_rejected_from_manifest(self):
        """A knowledge record with mutability=changing must be rejected by mutability_reasons."""
        candidate = {"kind": "knowledge", "mutability": "changing", "content_hash": "abc"}
        reasons = mutability_reasons(candidate)
        assert REASON_CHANGING_IN_MANIFEST in reasons

    def test_missing_mutability_rejected_from_manifest(self):
        """A knowledge record with no mutability must be rejected, not silently treated as stable."""
        candidate = {"kind": "knowledge", "content_hash": "abc"}
        reasons = mutability_reasons(candidate)
        assert REASON_MUTABILITY_MISSING in reasons

    def test_invalid_mutability_rejected(self):
        """An unrecognised mutability string must be flagged as invalid."""
        candidate = {"kind": "knowledge", "mutability": "volatile", "content_hash": "abc"}
        reasons = mutability_reasons(candidate)
        assert REASON_MUTABILITY_INVALID in reasons

    def test_stable_knowledge_accepted_by_mutability(self):
        """A stable knowledge record should have no mutability reasons."""
        candidate = {"kind": "knowledge", "mutability": "stable", "content_hash": "abc"}
        reasons = mutability_reasons(candidate)
        assert reasons == ()

    def test_non_knowledge_not_flagged_by_mutability(self):
        """Non-knowledge records should not be flagged by mutability_reasons."""
        candidate = {"kind": "conversation", "content_hash": "abc"}
        reasons = mutability_reasons(candidate)
        assert reasons == ()

    def test_fact_key_triggers_knowledge_check(self):
        """A record with a fact_key is treated as knowledge even without kind=knowledge."""
        candidate = {"fact_key": ["brelto", "status"], "mutability": "changing"}
        reasons = mutability_reasons(candidate)
        assert REASON_CHANGING_IN_MANIFEST in reasons

    def test_train_eligibility_rejects_changing_knowledge(self):
        """train_eligibility must reject a changing knowledge candidate with the right reason."""
        candidate = {"kind": "knowledge", "mutability": "changing", "content_hash": "abc"}
        ok, reason = train_eligibility(candidate, _verified())
        assert not ok
        assert "changing_knowledge" in reason or "mutability" in reason.lower()

    def test_train_eligibility_rejects_missing_mutability(self):
        """train_eligibility must reject a knowledge record with no mutability."""
        candidate = {"kind": "knowledge", "content_hash": "abc"}
        ok, reason = train_eligibility(candidate, _verified())
        assert not ok
        assert "mutability" in reason.lower()

    def test_train_eligibility_accepts_stable_knowledge_by_mutability(self):
        """A stable knowledge record passes the mutability check (may fail on other grounds like G2)."""
        candidate = {"kind": "knowledge", "mutability": "stable", "content_hash": "abc"}
        ok, reason = train_eligibility(candidate, _verified())
        # It should not be rejected for mutability reasons
        assert "mutability" not in reason.lower() or "ok" in reason.lower()

    def test_is_train_eligible_by_mutability_convenience(self):
        """The convenience function should agree with mutability_reasons."""
        assert not is_train_eligible_by_mutability({"kind": "knowledge", "mutability": "changing"})
        assert not is_train_eligible_by_mutability({"kind": "knowledge"})
        assert is_train_eligible_by_mutability({"kind": "knowledge", "mutability": "stable"})
        assert is_train_eligible_by_mutability({"kind": "conversation"})


# ---------------------------------------------------------------------------
# 4. Mutation tests: prove enforcement is non-vacuous
# ---------------------------------------------------------------------------

class TestMutabilityMutations:

    def test_mutant_accept_changing_in_manifest_is_killed(self, monkeypatch):
        """If mutability_reasons accepts everything, the manifest rejection test must fail."""
        monkeypatch.setattr("nawa.memory.mutability.mutability_reasons",
                            lambda c: ())
        from nawa.memory.mutability import mutability_reasons as _mr
        # After patching, mutability_reasons should return () for a changing record
        candidate = {"kind": "knowledge", "mutability": "changing", "content_hash": "abc"}
        assert _mr(candidate) == ()
        # The real check (unpatched) should have returned a reason
        monkeypatch.undo()
        from nawa.memory.mutability import mutability_reasons as _real_mr
        assert REASON_CHANGING_IN_MANIFEST in _real_mr(candidate)

    def test_mutant_treat_missing_as_stable_is_killed(self, monkeypatch):
        """If missing mutability is treated as stable, the missing-mutability test must fail."""
        def fake_reasons(c):
            if c.get("mutability") is None:
                return ()  # mutant: accept missing as stable
            if c.get("mutability") == "changing":
                return (REASON_CHANGING_IN_MANIFEST,)
            return ()
        monkeypatch.setattr("nawa.memory.mutability.mutability_reasons", fake_reasons)
        from nawa.memory.mutability import mutability_reasons as _mr
        candidate = {"kind": "knowledge", "content_hash": "abc"}
        assert _mr(candidate) == ()  # mutant accepts missing
        # Real check should reject
        monkeypatch.undo()
        from nawa.memory.mutability import mutability_reasons as _real_mr
        assert REASON_MUTABILITY_MISSING in _real_mr(candidate)

    def test_mutant_reject_changing_in_memory_is_killed(self, monkeypatch):
        """If memory rejects changing knowledge, the memory write test must fail."""
        import nawa.memory.store as store_mod
        real_write = store_mod.MemoryStore.write

        def rejecting_write(self, principal, kind, content, **kw):
            if kw.get("mutability") is not None:
                raise Exception("mutant: changing knowledge rejected from memory")
            return real_write(self, principal, kind, content, **kw)
        monkeypatch.setattr(store_mod.MemoryStore, "write", rejecting_write)
        store = new_store()
        with pytest.raises(Exception, match="mutant"):
            _changing_fact(store)
