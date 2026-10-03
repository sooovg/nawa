"""P7-05 isolation: nothing one synthetic user writes is visible to another, through any read path (ADR-0009)."""

from __future__ import annotations

import itertools

import pytest

from memory_support import ALPHA, BETA, GAMMA, USERS, new_store, put, pv
from nawa.memory import (IsolationError, MemoryKind, MemoryOrchestrator, Principal, PolicyViolation, SYNTHETIC_USERS)
from nawa.memory import consolidation
from nawa.memory.replay import selfcheck

KINDS = (MemoryKind.CONVERSATION, MemoryKind.USER_PERSISTENT, MemoryKind.TASK, MemoryKind.KNOWLEDGE,
         MemoryKind.PROCEDURAL, MemoryKind.SENSORY)


def _populated():
    st = new_store()
    ids = {}
    for who in USERS:
        tag = who.user_id.split("_")[1]
        for k in KINDS:
            # every user writes the SAME shared words plus a private marker, so a leak cannot hide behind scoring
            kw = {"fact_key": ("brelto", "attr")} if k is MemoryKind.KNOWLEDGE else {}
            if k is MemoryKind.TASK:
                kw["due_at"] = 0
            it = put(st, who, k, f"brelto kavun secret{tag}{k.value}", **kw)
            ids[(who.user_id, k)] = it.item_id
    return st, ids


def _everything_visible(st, who):
    out = []
    for it in st.scan(who):
        out.append(it)
        out += [h.item for h in st.associate(who, it.item_id, limit=100)]
    for q in ("brelto", "kavun", "secretalpha", "secretbeta", "secretgamma"):
        out += [h.item for h in st.search(who, q, limit=100)]
    out += st.due_tasks(who)
    return out


@pytest.mark.parametrize("reader,writer", list(itertools.permutations(USERS, 2)))
def test_no_item_of_another_user_is_visible_through_any_read_path(reader, writer) -> None:
    st, ids = _populated()
    seen = _everything_visible(st, reader)
    assert seen and all(it.owner == reader.user_id for it in seen)
    wtag = writer.user_id.split("_")[1]
    assert f"secret{wtag}" not in st.summarize(reader)
    for k in KINDS:
        other = ids[(writer.user_id, k)]
        assert st.read(reader, other) is None
        for fn in (st.provenance, st.confidence, st.acl, st.version, st.versions, st.associate):
            with pytest.raises(KeyError):
                fn(reader, other)
        with pytest.raises(KeyError):
            st.forget(reader, other)
        with pytest.raises(KeyError):
            st.update(reader, other, "brelto", provenance=pv("synthetic:x/2", 1, author=reader.user_id))
    assert st.introspect(reader)["items"] == len(KINDS)


def test_other_users_id_and_missing_id_are_indistinguishable() -> None:
    st, ids = _populated()
    other = ids[("user_beta", MemoryKind.KNOWLEDGE)]
    missing = "mem-" + "0" * 16
    for target in (other, missing):
        assert st.read(ALPHA, target) is None
        with pytest.raises(KeyError) as e:
            st.provenance(ALPHA, target)
        assert str(e.value) == "'not_found'"


def test_probing_another_users_id_leaves_no_trace_in_the_prober_cache() -> None:
    st, ids = _populated()
    other = ids[("user_beta", MemoryKind.CONVERSATION)]
    assert st.read(ALPHA, other) is None
    assert other not in str(st.dump_state()["cache"])


def test_projects_of_the_same_user_are_isolated() -> None:
    st = new_store()
    p1, p2 = Principal("user_alpha", "project_one"), Principal("user_alpha", "project_two")
    a = put(st, p1, MemoryKind.CONVERSATION, "kavun one")
    assert st.read(p2, a.item_id) is None and st.search(p2, "kavun") == [] and st.scan(p2) == []
    assert st.read(p1, a.item_id) == a


def test_only_synthetic_users_are_accepted_until_od12() -> None:
    assert SYNTHETIC_USERS == ("user_alpha", "user_beta", "user_gamma")
    for bad in ("user_delta", "ahmed", "admin", "", "USER_ALPHA", "user_alpha "):
        with pytest.raises(IsolationError, match="OD-12"):
            Principal(bad)
    with pytest.raises(IsolationError):
        Principal("user_alpha", "../user_beta")
    st = new_store()
    with pytest.raises(TypeError):
        st.write(("user_alpha", "project_default"), MemoryKind.CONVERSATION, "x",  # type: ignore[arg-type]
                 provenance=pv(), confidence=1.0)


def test_consolidation_never_mixes_users() -> None:
    st, _ = _populated()
    mixed = st.scan(ALPHA) + st.scan(BETA)
    with pytest.raises(ValueError, match="spans_principals"):
        consolidation.plan(mixed)
    for who in USERS:
        created, _ = consolidation.apply(st, who)
        assert all(c.owner == who.user_id for c in created)
    for reader, writer in itertools.permutations(USERS, 2):
        wtag = writer.user_id.split("_")[1]
        assert all(f"secret{wtag}" not in it.content for it in _everything_visible(st, reader))


def test_acl_is_owner_only_and_sharing_is_disabled_until_od12() -> None:
    st, ids = _populated()
    a = st.acl(ALPHA, ids[("user_alpha", MemoryKind.TASK)])
    assert a["readers"] == ["user_alpha"] and a["writers"] == ["user_alpha"]
    assert a["sharing"] == "disabled_until_OD-12"


def test_orchestrator_routes_keep_isolation_and_refuse_unknown_ops() -> None:
    st = new_store()
    o = MemoryOrchestrator(st)
    t = o.handle(ALPHA, {"op": "turn", "text": "kavun nupra", "ref": "synthetic:dlg/1"})
    assert o.handle(BETA, {"op": "recall", "query": "kavun"}) == []
    assert [h.item.item_id for h in o.handle(ALPHA, {"op": "recall", "query": "kavun"})] == [t.item_id]
    with pytest.raises(Exception):
        o.handle(ALPHA, {"op": "share_with", "user": "user_beta"})
    with pytest.raises(PolicyViolation):
        o.handle(GAMMA, {"op": "turn", "text": "", "ref": "synthetic:dlg/2"})


def test_selfcheck_isolation_over_a_seeded_random_script() -> None:
    res = selfcheck(seed=11, n=250)
    assert res["isolation_leaks"] == [] and res["ok"], res


def test_isolation_check_is_not_vacuous(monkeypatch) -> None:
    """Negative control: a store whose access check lets everyone read everything must be caught."""
    import nawa.memory.store as store_mod
    st, ids = _populated()
    monkeypatch.setattr(store_mod, "can_access", lambda principal, item: True)
    # route the read to the owner's partition, as a buggy store with one shared table would
    real_part = st._part

    def shared(principal, create=False):
        merged = store_mod._Partition()
        for p in st._parts.values():
            merged.items.update(p.items)
            for k, v in p.tokens.items():
                merged.tokens.setdefault(k, set()).update(v)
        return merged if not create else real_part(principal, create)
    monkeypatch.setattr(st, "_part", shared)
    seen = _everything_visible(st, ALPHA)
    assert any(it.owner != "user_alpha" for it in seen)


def test_access_check_layer_alone_refuses_other_owner_and_other_project() -> None:
    """Defence in depth, layer 2: ``can_access`` refuses on its own, independent of partitioning."""
    from nawa.memory.isolation import can_access
    st = new_store()
    a = put(st, ALPHA, MemoryKind.CONVERSATION, "kavun")
    assert can_access(ALPHA, a)
    assert not can_access(BETA, a)
    assert not can_access(Principal("user_alpha", "project_other"), a)


def test_partition_layer_alone_separates_users_and_projects() -> None:
    """Defence in depth, layer 1: every (user, project) has its own physical partition."""
    st = new_store()
    for who in (ALPHA, BETA, Principal("user_alpha", "project_two")):
        put(st, who, MemoryKind.CONVERSATION, "kavun")
    assert st.partitions() == [("user_alpha", "project_default"), ("user_alpha", "project_two"),
                               ("user_beta", "project_default")]
    for key, items in st.dump_state()["items"].items():
        user, project = key.split("|")
        assert all(r["owner"] == user and r["project"] == project for r in items)
