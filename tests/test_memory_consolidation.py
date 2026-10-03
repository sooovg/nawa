"""P7-05 consolidation and determinism: same inputs give the same outputs, in any process (ADR-0009)."""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest

from memory_support import ALPHA, BETA, new_store, put, pv
from nawa.memory import MemoryKind, Modality, SourceType, TaskStatus
from nawa.memory import consolidation
from nawa.memory.replay import digest, run, selfcheck, synthetic_ops
from nawa.verification.states import VerificationState

ROOT = Path(__file__).resolve().parents[1]


def _scenario():
    st = new_store()
    put(st, ALPHA, MemoryKind.SENSORY, "red square", modality=Modality.VISUAL, tags=("event:e1",))
    put(st, ALPHA, MemoryKind.SENSORY, "low tone", modality=Modality.AUDIO, tags=("event:e1",))
    put(st, ALPHA, MemoryKind.SENSORY, "say brelto", modality=Modality.TEXT, tags=("attend",))
    put(st, ALPHA, MemoryKind.CONVERSATION, "i like kavun", consent=True, tags=("remember",))
    put(st, ALPHA, MemoryKind.CONVERSATION, "no consent nupra", tags=("remember",))
    put(st, ALPHA, MemoryKind.TASK, "build tobrak", task_status=TaskStatus.DONE, steps=("plan", "do"))
    put(st, ALPHA, MemoryKind.TASK, "open task", task_status=TaskStatus.OPEN)
    for i, state in enumerate((VerificationState.SUPPORTED, VerificationState.UNCERTAIN)):
        put(st, ALPHA, MemoryKind.KNOWLEDGE, "Mirsel is blue", fact_key=("mirsel", "colour"), confidence=0.9 - i * 0.4,
            verification_state=state,
            provenance=pv(f"synthetic:doc/{i}", 0, SourceType.SYNTHETIC_DOCUMENT, "user_alpha", f"synthetic:ev/{i}"))
    return st


def test_rules_create_exactly_the_expected_items_with_lineage() -> None:
    st = _scenario()
    before = {it.item_id: it for it in st.scan(ALPHA)}
    created, retired = consolidation.apply(st, ALPHA)
    rules = [c.provenance.source_ref.rsplit("/", 1)[1] for c in created]
    assert rules == ["fuse", "attend", "promote", "experience", "dedupe"]
    fused, attended, promoted, exp, merged = created
    assert fused.modality is Modality.MULTISENSORY and fused.content == "audio: low tone | visual: red square"
    assert attended.kind is MemoryKind.CONVERSATION and attended.content == "say brelto"
    assert promoted.kind is MemoryKind.USER_PERSISTENT and promoted.consent and promoted.content == "i like kavun"
    assert "no consent nupra" not in [c.content for c in created]          # never promoted without consent
    assert exp.kind is MemoryKind.PROCEDURAL and exp.content == "build tobrak => done: plan ; do"
    assert merged.kind is MemoryKind.KNOWLEDGE and merged.confidence == 0.5
    assert merged.verification_state is VerificationState.UNCERTAIN and merged.epistemic == "belief"
    assert len(retired) == 2 and all(before[r].kind is MemoryKind.KNOWLEDGE for r in retired)
    for c in created:
        assert c.provenance.source_type is SourceType.CONSOLIDATION and c.provenance.derived_from
        assert set(c.provenance.derived_from) <= set(before)
        assert c.confidence == min(before[s].confidence for s in c.provenance.derived_from)
    assert all(e.reason == "consolidated" for e in st.log.entries)


def test_consolidation_is_idempotent() -> None:
    st = _scenario()
    consolidation.apply(st, ALPHA)
    d = st.state_digest()
    assert consolidation.plan(st.scan(ALPHA)).empty
    assert consolidation.apply(st, ALPHA) == ([], [])
    assert st.state_digest() == d


def test_plan_does_not_depend_on_input_order() -> None:
    st = _scenario()
    items = st.scan(ALPHA)
    assert consolidation.plan(items) == consolidation.plan(list(reversed(items)))


def test_same_scenario_twice_gives_identical_state() -> None:
    a, b = _scenario(), _scenario()
    consolidation.apply(a, ALPHA)
    consolidation.apply(b, ALPHA)
    assert a.state_digest() == b.state_digest()
    assert a.dump_state()["items"] == b.dump_state()["items"]


def test_consolidation_goes_through_the_write_policy() -> None:
    st = new_store()
    long = " ".join(["fendra"] * 350)          # 2,449 chars each; fused > MAX_CHARS (4,000)
    put(st, ALPHA, MemoryKind.SENSORY, long, modality=Modality.VISUAL, tags=("event:big",))
    put(st, ALPHA, MemoryKind.SENSORY, long, modality=Modality.AUDIO, tags=("event:big",))
    created, _ = consolidation.apply(st, ALPHA)         # fused text would exceed MAX_CHARS: skipped, not truncated
    assert created == []


def test_seeded_script_replays_to_the_same_digest() -> None:
    ops = synthetic_ops(seed=3, n=200)
    assert ops == synthetic_ops(seed=3, n=200)
    assert digest(ops) == digest(ops)
    assert digest(ops) != digest(synthetic_ops(seed=4, n=200))     # negative control: the digest is not constant


def test_replay_is_identical_across_processes_and_hash_seeds() -> None:
    env = dict(os.environ)
    outs = []
    for hs in ("0", "1", "12345"):
        env["PYTHONHASHSEED"] = hs
        r = subprocess.run([sys.executable, "-m", "nawa.memory.replay", "--seed", "9", "--ops", "150"],
                           capture_output=True, text=True, env=env, cwd=ROOT, check=True)
        outs.append(r.stdout.strip())
    assert len(set(outs)) == 1 and len(outs[0]) == 64
    assert outs[0] == digest(synthetic_ops(9, 150))


def test_digest_changes_when_any_stored_byte_changes() -> None:
    st, _ = run(synthetic_ops(2, 80))
    d = st.state_digest()
    st.clock.advance(1)
    assert st.state_digest() != d


def test_selfcheck_cli_passes() -> None:
    r = subprocess.run([sys.executable, "-m", "nawa.memory.replay", "--check", "--ops", "200"], capture_output=True,
                       text=True, cwd=ROOT)
    assert r.returncode == 0, r.stdout + r.stderr
    assert '"ok": true' in r.stdout and "OD-12" in r.stdout


def test_selfcheck_detects_nondeterminism(monkeypatch) -> None:
    """Negative control: an id that depends on a process-random value must make the self-check fail."""
    import itertools
    import nawa.memory.store as store_mod
    counter = itertools.count()
    orig = store_mod.MemoryStore._new_id

    def unstable(self, principal, p, kind):
        return orig(self, principal, p, kind)[:-4] + f"{next(counter) % 65536:04x}"
    monkeypatch.setattr(store_mod.MemoryStore, "_new_id", unstable)
    res = selfcheck(seed=7, n=60)
    assert not res["deterministic"] and not res["ok"]


def test_memory_package_has_no_wall_clock_or_unseeded_randomness() -> None:
    banned_modules = {"time", "uuid", "secrets"}
    for path in sorted((ROOT / "src/nawa/memory").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert not {a.name.split(".")[0] for a in node.names} & banned_modules, path.name
            if isinstance(node, ast.ImportFrom) and node.module:
                assert node.module.split(".")[0] not in banned_modules, path.name
            if isinstance(node, ast.Attribute) and node.attr in {"now", "utcnow", "today", "urandom"}:
                assert isinstance(node.value, ast.Attribute) and node.value.attr == "clock", \
                    f"{path.name}: {ast.unparse(node)}"
        if path.name != "replay.py":
            assert "import random" not in path.read_text(encoding="utf-8"), path.name
    text = (ROOT / "src/nawa/memory/replay.py").read_text(encoding="utf-8")
    assert "random.Random(seed)" in text and "random.random(" not in text and "random.choice(" not in text


def test_beta_consolidation_does_not_change_alpha_state() -> None:
    st = _scenario()
    put(st, BETA, MemoryKind.CONVERSATION, "beta kavun", consent=True, tags=("remember",))
    alpha_before = [it.to_record() for it in st.scan(ALPHA)]
    consolidation.apply(st, BETA)
    assert [it.to_record() for it in st.scan(ALPHA)] == alpha_before


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_selfcheck_passes_for_several_seeds(seed) -> None:
    assert selfcheck(seed=seed, n=150)["ok"]


def test_rules_emit_items_in_chronological_source_order() -> None:
    st = new_store()
    first = put(st, ALPHA, MemoryKind.CONVERSATION, "first kavun", consent=True, tags=("remember",))
    st.clock.advance(1)
    second = put(st, ALPHA, MemoryKind.CONVERSATION, "second kavun", consent=True, tags=("remember",))
    p = consolidation.plan(st.scan(ALPHA))
    assert [c.sources for c in p.create] == [(first.item_id,), (second.item_id,)]
