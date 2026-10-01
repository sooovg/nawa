"""P2-04: preference pairs schema, builder, and checker (ADR-0005)."""

from __future__ import annotations

import json
import random
import subprocess
import sys
from pathlib import Path

import pytest

from nawa.data import preference as pf
from nawa.data import twins as tw

ROOT = Path(__file__).resolve().parents[1]
CODES = pf.taxonomy_codes()
PAIRS = pf.build(40, seed=5)
A, U = tw.pairs(tw.build(3, seed=5))[0]


def test_taxonomy_codes_are_read_from_the_doc() -> None:
    assert {"FT-01", "FT-02", "FT-07", "FT-12", "FT-13", "FT-14"} <= CODES and "FT-99" not in CODES


def test_every_built_pair_is_valid_and_not_train_eligible() -> None:
    assert [(p["id"], pr) for p in PAIRS if (pr := pf.check_pair(p, CODES))] == []
    assert all(p["train_eligible"] is False and "G2" in p["train_block_reason"] for p in PAIRS)
    assert pf.build(40, seed=5) == PAIRS


def test_each_twin_yields_every_failure_type() -> None:
    kinds = {p["rejected_failure"] for p in PAIRS}
    assert kinds == {"FT-01", "FT-02", "FT-07", "FT-12", "FT-13", "FT-14"}
    assert all(p["rejected_failure"] != "FT-02" or p["gold"]["attr"] in pf.NUMERIC for p in PAIRS)


@pytest.mark.parametrize("response,kind,expected", [
    ("{answer} [{k}]", "a", None),
    ("{dv} [1]", "a", "FT-07"),
    ("{answer} [99]", "a", "FT-01"),
    ("{answer}", "a", "FT-12"),
    ("غير موجود في السياق", "a", "FT-13"),
    ("غير موجود في السياق. لا يذكر النص ذلك.", "u", None),
    ("{dv}", "u", "FT-14"),
    ("غير موجود في السياق [2]", "u", "FT-14"),
])
def test_judge(response: str, kind: str, expected: str | None) -> None:
    rec = A if kind == "a" else U
    g = rec["gold"]
    text = response.format(answer=g["answer"], k=g["support"], dv=g["distractor_value"])
    r = pf.judge(text, rec)
    assert r["failure"] == expected and r["correct"] is (expected is None)


def test_judge_rejects_citation_to_unsupporting_sentence() -> None:
    ctx = tw.parse_user(tw._msg(A, "user"))[0]
    other = next(i for i, s in enumerate(ctx, start=1) if A["gold"]["entity"] not in s or A["gold"]["answer"] not in s)
    assert pf.judge(f"{A['gold']['answer']} [{other}]", A)["failure"] == "FT-12"


@pytest.mark.parametrize("name", sorted(pf.corruptions(PAIRS[0])))
def test_checker_catches_each_corruption(name: str) -> None:
    for p in PAIRS[:30]:
        assert pf.check_pair(pf.corruptions(p)[name], CODES), (name, p["id"])


def test_wrong_number_never_collides_with_context() -> None:
    rng = random.Random(0)
    ctx = ["يبلغ طول السفينة ثاحو 101 مترًا.", "يبلغ طول السفينة خيذا 99 مترًا."]
    for _ in range(200):
        w = pf._wrong_number(rng, "100", ctx)
        assert w not in {"100", "101", "99"}


def test_from_model_outputs_picks_or_refuses() -> None:
    right, wrong = tw._msg(A, "assistant"), f"{A['gold']['distractor_value']} [1]"
    got = pf.from_model_outputs(A, [("m1", wrong), ("m2", right)])
    assert got and (got["chosen"], got["rejected"], got["chosen_model"], got["rejected_model"]) == (right, wrong, "m2", "m1")
    assert got["source"] == "model_output" and got["train_eligible"] is False and not pf.check_pair(got, CODES)
    assert pf.from_model_outputs(A, [("m1", right), ("m2", right)]) is None
    assert pf.from_model_outputs(A, [("m1", wrong)]) is None


@pytest.mark.parametrize("seed", [2026, 7])
def test_bench_meets_preregistered_criteria(seed: int) -> None:
    rep = pf.run_bench(seed, 200)
    assert rep["criteria"] == pf.CRITERIA and rep["passed"], rep["metrics"]


def test_cli_build_refuses_overwrite(tmp_path: Path) -> None:
    out = tmp_path / "p.jsonl"
    cmd = [sys.executable, "-m", "nawa.data.preference", "build", "--n", "4", "--seed", "3", "--out", str(out)]
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    assert p.returncode == 0, p.stderr
    rows = [json.loads(x) for x in out.read_text(encoding="utf-8").splitlines()]
    assert rows and all(not pf.check_pair(r, CODES) for r in rows)
    assert subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT).returncode != 0
