"""P2-02: independent verification of data candidates (ROADMAP P2-02, ADR-0005)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from nawa import data_verify as dv
from nawa.atlas import records_from_run
from nawa.evaluation.runner import make_backend, run

ROOT = Path(__file__).resolve().parents[1]
CFG = dv.load_config()
LIC = "test-fixture-license"
CFG_LIC = {**CFG, "approved_licenses": [LIC]}


def cand(method: str, evidence: dict, **kw) -> dict:
    return {"id": "C-1", "method": method, "producer": "agent-x", "evidence": evidence, **kw}


# ---- config ---------------------------------------------------------------------------------------

def test_committed_config_approves_no_license_until_od_03() -> None:
    assert CFG["approved_licenses"] == []
    assert set(CFG["methods"]) == {"calculation", "execution", "licensed_source", "expert_review"}


# ---- calculation ----------------------------------------------------------------------------------

@pytest.mark.parametrize("expr,claimed,status", [
    ("(12 + 30) * 2", "84", "verified"),
    ("(12 + 30) * 2", "85", "rejected"),
    ("١٢ × ٣", "٣٦", "verified"),
    ("7 / 2", "3.5", "verified"),
    ("1 / 3", "0.333", "rejected"),
    ("2 ** 10", "1024", "verified"),
])
def test_calculation(expr: str, claimed: str, status: str) -> None:
    assert dv.verify(cand("calculation", {"expression": expr, "claimed": claimed}), CFG).status == status


def test_calculation_tolerance_is_explicit() -> None:
    ev = {"expression": "1 / 3", "claimed": "0.333", "tolerance": "0.001"}
    assert dv.verify(cand("calculation", ev), CFG).status == "verified"


@pytest.mark.parametrize("expr", ["__import__('os').system('true')", "x + 1", "2 ** 100000", "1 / 0", "[1, 2]",
                                  "(lambda: 1)()", "1 if 1 else 2"])
def test_calculation_refuses_anything_but_arithmetic(expr: str) -> None:
    r = dv.verify(cand("calculation", {"expression": expr, "claimed": "1"}), CFG)
    assert r.status == "unverified", (expr, r)


# ---- execution ------------------------------------------------------------------------------------

GOOD = "def f(x):\n    return 2 * x\n"
TESTS = "assert f(2) == 4\nassert f(0) == 0\n"


def test_execution_independent_tests() -> None:
    ok = dv.verify(cand("execution", {"code": GOOD, "tests": TESTS, "tests_author": "tester"}), CFG)
    bad = dv.verify(cand("execution", {"code": GOOD.replace("2 *", "3 *"), "tests": TESTS, "tests_author": "tester"}), CFG)
    assert (ok.status, bad.status) == ("verified", "rejected")


def test_execution_refuses_producer_tests_and_assertless_tests() -> None:
    own = dv.verify(cand("execution", {"code": GOOD, "tests": TESTS, "tests_author": "agent-x"}), CFG)
    noassert = dv.verify(cand("execution", {"code": GOOD, "tests": "f(1)", "tests_author": "tester"}), CFG)
    assert own.status == noassert.status == "unverified"


def test_execution_runs_in_sandbox_without_network() -> None:
    code = "import socket\ndef f():\n    socket.create_connection(('example.com', 80))\n"
    r = dv.verify(cand("execution", {"code": code, "tests": "f()\nassert True\n", "tests_author": "tester"}), CFG)
    assert r.status == "rejected"


# ---- licensed_source ------------------------------------------------------------------------------

SRC = "نص اصطناعي للاختبار: يبلغ طول الجسر رقم 9 مئتين وعشرين مترًا، ويعبر النهر رقم 4."


def src_ev(**over) -> dict:
    ev = {"source_id": "fixture-1", "source_text": SRC, "source_sha256": dv.sha256_text(SRC), "license": LIC,
          "quote": "ويعبر النهر رقم 4", "answer": "4"}
    ev.update(over)
    return ev


def test_licensed_source_verifies_answer_in_verbatim_quote() -> None:
    assert dv.verify(cand("licensed_source", src_ev()), CFG_LIC).status == "verified"


def test_licensed_source_unapproved_license_is_unverified_with_committed_config() -> None:
    r = dv.verify(cand("licensed_source", src_ev()), CFG)
    assert r.status == "unverified" and "OD-03" in r.reason


@pytest.mark.parametrize("over,status", [
    ({"answer": "44"}, "rejected"),                     # answer not in the quote (and not a substring match)
    ({"quote": "ويعبر النهر رقم 5", "answer": "5"}, "rejected"),  # quote not in the source
    ({"source_text": SRC + "."}, "unverified"),         # hash mismatch
    ({"license": ""}, "unverified"),
])
def test_licensed_source_failures(over: dict, status: str) -> None:
    assert dv.verify(cand("licensed_source", src_ev(**over)), CFG_LIC).status == status


# ---- expert_review --------------------------------------------------------------------------------

@pytest.mark.parametrize("reviewer,decision,status", [
    ("human:dr-a", "accept", "verified"),
    ("human:dr-a", "reject", "rejected"),
    ("model:provider/m", "accept", "unverified"),      # a model is not an expert of record (ADR-0003 D4)
    ("automated:scorer", "accept", "unverified"),
    ("human:", "accept", "unverified"),
    ("human:agent-x", "accept", "unverified"),         # producer reviewing itself
])
def test_expert_review(reviewer: str, decision: str, status: str) -> None:
    ev = {"reviewer": reviewer, "decision": decision, "date": "2026-10-01"}
    assert dv.verify(cand("expert_review", ev), CFG).status == status


# ---- generic rules --------------------------------------------------------------------------------

def test_unknown_method_missing_producer_and_frozen_are_unverified() -> None:
    assert dv.verify(cand("vibes", {}), CFG).status == "unverified"
    assert dv.verify({**cand("calculation", {"expression": "1+1", "claimed": "2"}), "producer": ""}, CFG).status == "unverified"
    frozen = cand("calculation", {"expression": "1+1", "claimed": "2"}, split="frozen")
    assert dv.verify(frozen, CFG).status == "unverified"


def test_result_rejects_invented_status() -> None:
    with pytest.raises(ValueError):
        dv.VerificationResult("x", "calculation", "probably", "")


# ---- training eligibility -------------------------------------------------------------------------

def test_gate_status_reads_roadmap() -> None:
    assert dv.gate_status("G2") != "DONE"
    assert dv.gate_status("G1") == "PENDING_REVIEW"


def test_nothing_is_train_eligible_while_g2_is_open() -> None:
    c = cand("calculation", {"expression": "1+1", "claimed": "2"})
    ok, why = dv.train_eligibility(c, dv.verify(c, CFG))
    assert not ok and "G2" in why


def test_train_eligibility_order_of_blocks(tmp_path: Path) -> None:
    roadmap = tmp_path / "ROADMAP.md"
    roadmap.write_text("| G2 أطلس (P2) | DONE | 2026-10-01 | test |\n", encoding="utf-8")
    c = cand("calculation", {"expression": "1+1", "claimed": "2"})
    res = dv.verify(c, CFG)
    assert dv.train_eligibility(c, res, roadmap, frozen=set()) == (True, "verified, not evaluation-derived, no frozen hash, G2 closed")
    assert not dv.train_eligibility({**c, "split": "dev"}, res, roadmap, frozen=set())[0]
    assert "frozen" in dv.train_eligibility({**c, "content_hash": "h"}, res, roadmap, frozen={"h"})[1]
    bad = dv.verify(cand("calculation", {"expression": "1+1", "claimed": "3"}), CFG)
    assert "not verified" in dv.train_eligibility(c, bad, roadmap, frozen=set())[1]


def test_frozen_hash_list_is_loaded() -> None:
    assert len(dv.frozen_hashes()) == 243


# ---- P1-08 Atlas records --------------------------------------------------------------------------

def test_atlas_records_stay_verified_and_never_train_eligible(tmp_path: Path) -> None:
    d, _ = run(make_backend("always_abstain"), "dev", runs_dir=tmp_path)
    recs = records_from_run(d, "2026-10-01T00:00:00Z")
    assert recs
    for rec in recs:
        r = dv.verify_atlas_record(rec)
        assert r.status == "verified"
        ok, why = dv.train_eligibility({"split": rec["split"], "content_hash": rec["content_hash"]}, r)
        assert not ok and "evaluation" in why
    assert dv.verify_atlas_record({**recs[0], "verification_method": None}).status == "unverified"


# ---- benchmark with pre-registered criteria -------------------------------------------------------

@pytest.mark.parametrize("seed", [2026, 7])
def test_bench_meets_preregistered_criteria(seed: int) -> None:
    rep = dv.run_bench(seed=seed, n=20)
    assert rep["criteria"] == {"false_verified": 0, "status_accuracy": 1.0}
    assert rep["passed"], rep["mismatches"]
    assert rep["false_verified"] == 0 and rep["train_eligible"] == 0
    assert all(rep["confusion_expected_to_got"][s][s] > 0 for s in dv.STATUSES)


def test_cli_check_writes_new_file_and_refuses_overwrite(tmp_path: Path) -> None:
    src = tmp_path / "c.jsonl"
    src.write_text(json.dumps(cand("calculation", {"expression": "2*3", "claimed": "6"}), ensure_ascii=False) + "\n",
                   encoding="utf-8")
    out = tmp_path / "r.jsonl"
    cmd = [sys.executable, str(ROOT / "data_pipeline/atlas/verify.py"), "check", str(src), "--out", str(out)]
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    assert p.returncode == 0, p.stderr
    row = json.loads(out.read_text(encoding="utf-8"))
    assert row["status"] == "verified" and row["train_eligible"] is False and "G2" in row["train_block_reason"]
    assert subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT).returncode != 0
