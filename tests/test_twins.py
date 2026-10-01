"""P2-03: abstention twins builder and checker (ADR-0005)."""

from __future__ import annotations

import json
import random
import subprocess
import sys
from pathlib import Path

import pytest

from nawa.data import twins as tw
from nawa.evaluation.normalize import is_abstention
from nawa.evaluation.suites._context import SYSTEM_CONTEXT
from nawa.evaluation.synth import SYLLABLES

ROOT = Path(__file__).resolve().parents[1]
RECS = tw.build(60, seed=11)
PAIRS = tw.pairs(RECS)


def test_build_is_deterministic_and_paired() -> None:
    assert tw.build(60, seed=11) == RECS and tw.build(60, seed=12) != RECS
    assert len(PAIRS) == 60 and all(a["kind"] == "answerable" and u["kind"] == "unanswerable" for a, u in PAIRS)
    assert len({r["id"] for r in RECS}) == len(RECS)


def test_every_built_pair_is_well_formed() -> None:
    assert [p for a, u in PAIRS if (p := tw.check_pair(a, u))] == []


def test_twins_differ_only_by_the_evidence_sentence() -> None:
    a, u = PAIRS[0]
    ca, qa = tw.parse_user(tw._msg(a, "user"))
    cu, qu = tw.parse_user(tw._msg(u, "user"))
    assert qa == qu and set(ca) - set(cu) == {a["gold"]["support_sentence"]} and set(cu) <= set(ca)
    assert ca[a["gold"]["support"] - 1] == a["gold"]["support_sentence"]


def test_targets_answer_with_citation_or_abstain_with_reason() -> None:
    for a, u in PAIRS:
        ra, ru = tw._msg(a, "assistant"), tw._msg(u, "assistant")
        assert ra == f"{a['gold']['answer']} [{a['gold']['support']}]" and not is_abstention(ra)
        assert is_abstention(ru) and a["gold"]["entity"] in ru and tw.LABELS[a["gold"]["attr"]] in ru


def test_hard_negative_distractor_has_the_asked_attribute() -> None:
    for a, u in PAIRS:
        g = a["gold"]
        assert g["distractor"] != g["entity"] and g["distractor_value"] != g["answer"]
        assert any(g["distractor"] in s for s in tw.parse_user(tw._msg(u, "user"))[0])


@pytest.mark.parametrize("name", sorted(tw.corruptions(*PAIRS[0])))
def test_checker_catches_each_corruption(name: str) -> None:
    for a, u in PAIRS[:20]:
        x, y = tw.corruptions(a, u)[name]
        assert tw.check_pair(x, y), name


def test_checker_rejects_non_pairs() -> None:
    a, u = PAIRS[0]
    assert tw.check_pair(u, a) == ["kinds or twin_id do not form a pair"]
    assert tw.check_pair(a, PAIRS[1][1]) == ["kinds or twin_id do not form a pair"]


def test_separation_from_evaluation_generator() -> None:
    eval_cons = {c for ar, _ in SYLLABLES for c in ar if c not in "اوي"}
    assert tw._TWIN_CONSONANTS and not set(tw._TWIN_CONSONANTS) & eval_cons
    assert tw.check_separation(RECS) == []
    bad = json.loads(json.dumps(RECS[0]))
    bad["gold"]["entity"] = "سالومي"
    assert tw.check_separation([bad])
    assert tw.SYSTEM_PROMPT != SYSTEM_CONTEXT


def test_nothing_is_train_eligible() -> None:
    assert all(r["train_eligible"] is False and "G2" in r["train_block_reason"] for r in RECS)


def test_eval_scorer_grades_targets_correct() -> None:
    assert all(tw.eval_scorer_ok(r) for r in RECS)
    wrong = json.loads(json.dumps(PAIRS[0][1]))
    tw._set_msg(wrong, "assistant", wrong["gold"]["distractor_value"])
    assert not tw.eval_scorer_ok(wrong)


@pytest.mark.parametrize("seed", [2026, 7])
def test_bench_meets_criteria(seed: int) -> None:
    rep = tw.run_bench(seed, 200)
    assert rep["criteria"] == tw.CRITERIA and rep["passed"], rep["metrics"]


def test_cli_build_refuses_overwrite(tmp_path: Path) -> None:
    out = tmp_path / "t.jsonl"
    cmd = [sys.executable, "-m", "nawa.data.twins", "build", "--n", "5", "--seed", "3", "--out", str(out)]
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    assert p.returncode == 0, p.stderr
    assert len(out.read_text(encoding="utf-8").splitlines()) == 10
    assert subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT).returncode != 0


def test_attributes_are_all_used() -> None:
    rng = random.Random(0)
    attrs = {tw.build_pair(rng, i)[0]["gold"]["attr"] for i in range(200)}
    assert attrs == set(tw.ATTRS)
