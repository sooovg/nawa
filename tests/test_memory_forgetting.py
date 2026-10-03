"""P7-05 forgetting: deletion is real, logged in a hash chain, and leaves no trace (ADR-0009)."""

from __future__ import annotations

import json

import pytest

from memory_support import ALPHA, BETA, new_store, put, pv
from nawa.memory import ForgettingLog, MemoryKind, MemoryOrchestrator, Modality, TaskStatus, trace_scan
from nawa.memory import consolidation
from nawa.memory.forgetting import GENESIS, LogIntegrityError, entry_hash
from nawa.memory.replay import selfcheck
from nawa.memory.store import DATA_FILE, LOG_FILE

FORGOTTEN_TEXT = "glomir zq77777x"


def _all_read_paths(st, who, item_id=None):
    """Concatenated text of every read path: read, scan, search, associate, summaries, versions, due, cache."""
    parts = [it.content for it in st.scan(who)]
    parts += [h.item.content for h in st.search(who, "glomir", limit=100)]
    parts += [h.item.content for h in st.search(who, "zq77777x", limit=100)]
    for it in st.scan(who):
        parts += [h.item.content for h in st.associate(who, it.item_id, limit=100)]
    parts.append(st.summarize(who))
    parts += [it.content for it in st.due_tasks(who)]
    if item_id:
        r = st.read(who, item_id)
        parts.append(r.content if r else "")
    return "\n".join(parts)


def _warm(st, who):
    """Fill every cache so a forget that does not invalidate them would be caught."""
    _all_read_paths(st, who)
    for it in st.scan(who):
        st.read(who, it.item_id)


def test_forget_removes_item_from_search_summaries_association_cache_and_read() -> None:
    st = new_store()
    keep = put(st, ALPHA, MemoryKind.KNOWLEDGE, "glomir brelto fact", fact_key=("glomir", "colour"))
    gone = put(st, ALPHA, MemoryKind.KNOWLEDGE, FORGOTTEN_TEXT, fact_key=("glomir", "size"))
    _warm(st, ALPHA)
    assert FORGOTTEN_TEXT in _all_read_paths(st, ALPHA)
    assert FORGOTTEN_TEXT in json.dumps(st.dump_state()["cache"], ensure_ascii=False)   # the cache really held it
    entries = st.forget(ALPHA, gone.item_id)
    assert [e.id for e in entries] == [gone.item_id]
    assert trace_scan(st, needles=[gone.item_id, "zq77777x"]) == []
    text = _all_read_paths(st, ALPHA, gone.item_id)
    assert "zq77777x" not in text and st.read(ALPHA, gone.item_id) is None
    assert trace_scan(st, needles=[gone.item_id, "zq77777x"]) == []
    assert st.read(ALPHA, keep.item_id) is not None


def test_forget_removes_every_version_of_an_updated_item() -> None:
    st = new_store()
    it = put(st, ALPHA, MemoryKind.CONVERSATION, "kavun zq11111x")
    st.clock.advance(1)
    st.update(ALPHA, it.item_id, "kavun corrected", provenance=pv("synthetic:test/2", 1))
    assert len(st.versions(ALPHA, it.item_id)) == 2
    assert "zq11111x" in json.dumps(st.dump_state()["history"])
    st.forget(ALPHA, it.item_id)
    assert trace_scan(st, needles=[it.item_id, "zq11111x", "kavun corrected"]) == []


def test_forget_cascades_through_consolidation_lineage() -> None:
    st = new_store()
    turn = put(st, ALPHA, MemoryKind.CONVERSATION, "nupra zq22222x", consent=True, tags=("remember",))
    created, _ = consolidation.apply(st, ALPHA)
    assert [c.kind for c in created] == [MemoryKind.USER_PERSISTENT]
    # forgetting the durable copy also forgets the conversation it was copied from, and vice versa
    entries = st.forget(ALPHA, created[0].item_id)
    assert {e.id for e in entries} == {created[0].item_id, turn.item_id}
    assert entries[1].reason == f"cascade:{created[0].item_id}"
    assert trace_scan(st, needles=["zq22222x"]) == []


def test_persisted_store_deletion_reaches_the_disk(tmp_path) -> None:
    st = new_store(tmp_path)
    it = put(st, ALPHA, MemoryKind.USER_PERSISTENT, "salvek zq33333x")
    other = put(st, BETA, MemoryKind.USER_PERSISTENT, "salvek beta")
    assert b"zq33333x" in (tmp_path / DATA_FILE).read_bytes()
    st.forget(ALPHA, it.item_id)
    assert b"zq33333x" not in (tmp_path / DATA_FILE).read_bytes()
    assert not list(tmp_path.glob("*.tmp"))
    assert trace_scan(st, needles=[it.item_id, "zq33333x"], directory=tmp_path) == []
    # the id stays only in the log, never the content
    log_text = (tmp_path / LOG_FILE).read_text(encoding="utf-8")
    assert it.item_id in log_text and "zq33333x" not in log_text and "salvek" not in log_text
    reloaded = new_store(tmp_path)
    assert reloaded.read(ALPHA, it.item_id) is None and reloaded.read(BETA, other.item_id) is not None
    assert reloaded.state_digest() == st.state_digest()


def test_every_forget_and_expiry_is_logged_with_the_required_fields() -> None:
    st = new_store()
    a = put(st, ALPHA, MemoryKind.CONVERSATION, "a one")
    s = put(st, BETA, MemoryKind.SENSORY, "b sensed", modality=Modality.AUDIO)
    st.forget(ALPHA, a.item_id)
    st.clock.advance(10)
    exp = st.expire()
    assert [e.id for e in exp] == [s.item_id] and exp[0].reason == "expired_ttl"
    log = st.log.entries
    assert [e.id for e in log] == [a.item_id, s.item_id]
    for e in log:
        assert set(e.__dict__) == {"id", "type", "owner", "reason", "timestamp", "hash", "prev_hash"}
    assert log[0].prev_hash == GENESIS and log[1].prev_hash == log[0].hash
    assert log[0].owner == "user_alpha" and log[0].type == "conversation" and log[1].timestamp == "2026-01-01T00:00:10Z"
    assert log[0].hash == entry_hash(a.item_id, "conversation", "user_alpha", "user_request", log[0].timestamp, GENESIS)
    assert st.log.verify() == []


def test_log_reason_is_a_closed_vocabulary_so_content_cannot_leak_through_it() -> None:
    st = new_store()
    a = put(st, ALPHA, MemoryKind.CONVERSATION, "kavun")
    with pytest.raises(ValueError, match="vocabulary"):
        st.forget(ALPHA, a.item_id, reason="user said kavun")
    assert st.read(ALPHA, a.item_id) is not None and st.log.entries == ()   # refused before anything was removed
    log = ForgettingLog()
    with pytest.raises(ValueError):
        log.append("mem-0000000000000000", "conversation", "user_alpha", "free text", "2026-01-01T00:00:00Z")


@pytest.mark.parametrize("tamper", ["edit_reason", "drop_first", "swap", "edit_owner"])
def test_tampering_with_the_persistent_log_is_detected(tmp_path, tamper) -> None:
    st = new_store(tmp_path)
    for i in range(3):
        st.forget(ALPHA, put(st, ALPHA, MemoryKind.CONVERSATION, f"item {i}").item_id)
    path = tmp_path / LOG_FILE
    lines = path.read_text(encoding="utf-8").splitlines()
    if tamper == "edit_reason":
        lines[1] = lines[1].replace("user_request", "policy")
    elif tamper == "drop_first":
        lines = lines[1:]
    elif tamper == "swap":
        lines[0], lines[1] = lines[1], lines[0]
    else:
        lines[2] = lines[2].replace("user_alpha", "user_beta")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(LogIntegrityError):
        ForgettingLog(path)


def test_end_session_consolidates_then_forgets_the_session() -> None:
    st = new_store()
    o = MemoryOrchestrator(st)
    keep = o.handle(ALPHA, {"op": "turn", "text": "remember fendra", "ref": "synthetic:dlg/1",
                            "remember": True, "consent": True})
    drop = o.handle(ALPHA, {"op": "turn", "text": "passing yorin zq44444x", "ref": "synthetic:dlg/2"})
    res = o.handle(ALPHA, {"op": "end_session"})
    assert set(res["forgotten"]) == {keep.item_id, drop.item_id}
    assert [it.kind for it in st.scan(ALPHA)] == [MemoryKind.USER_PERSISTENT]
    assert trace_scan(st, needles=["zq44444x"]) == []
    assert all(e.reason == "session_end" for e in st.log.entries)


def test_expired_items_are_never_returned_even_before_expire_runs() -> None:
    st = new_store()
    s = put(st, ALPHA, MemoryKind.SENSORY, "flash glomir", modality=Modality.VISUAL)
    st.clock.advance(10)
    assert st.read(ALPHA, s.item_id) is None and st.search(ALPHA, "glomir") == [] and st.scan(ALPHA) == []
    t = put(st, ALPHA, MemoryKind.TASK, "durable task", task_status=TaskStatus.OPEN)
    st.clock.advance(10**6)
    assert st.read(ALPHA, t.item_id) is not None      # long-term kinds do not expire


def test_selfcheck_no_trace_after_forget_on_a_persisted_seeded_script() -> None:
    res = selfcheck(seed=5, n=250)
    assert res["ok"] and res["forgotten_checked"] > 20 and res["traces_after_forget"] == [] \
        and res["reachable_after_forget"] == [], res


@pytest.mark.parametrize("bug", ["keep_cache", "keep_tokens", "keep_history", "keep_summaries", "no_persist"])
def test_cosmetic_deletion_is_caught(tmp_path, monkeypatch, bug) -> None:
    """Negative controls: each way of making deletion cosmetic must leave a trace that trace_scan finds."""
    import nawa.memory.store as store_mod
    st = new_store(tmp_path)
    it = put(st, ALPHA, MemoryKind.CONVERSATION, "kavun zq55555x")
    st.clock.advance(1)
    st.update(ALPHA, it.item_id, "kavun zq55555x edited", provenance=pv("synthetic:t/2", 1))
    _warm(st, ALPHA)
    if bug == "keep_cache":
        monkeypatch.setattr(store_mod._Partition, "invalidate", lambda self: self.summaries.clear())
    elif bug == "keep_tokens":
        monkeypatch.setattr(store_mod.MemoryStore, "_unindex", lambda self, p, i: None)
    elif bug == "keep_history":
        orig = store_mod.MemoryStore._remove

        def keep_hist(self, p, item, reason):
            h = p.history.get(item.item_id)
            e = orig(self, p, item, reason)
            if h:
                p.history[item.item_id] = h
            return e
        monkeypatch.setattr(store_mod.MemoryStore, "_remove", keep_hist)
    elif bug == "keep_summaries":
        monkeypatch.setattr(store_mod._Partition, "invalidate", lambda self: self.cache.clear())
    else:
        monkeypatch.setattr(store_mod.MemoryStore, "_persist", lambda self: None)
    st.forget(ALPHA, it.item_id)
    needles = ["zq55555x"] if bug != "keep_tokens" else [it.item_id]
    assert trace_scan(st, needles=needles, directory=tmp_path) != []
