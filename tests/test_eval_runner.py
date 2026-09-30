"""P1-07: runner, report, targets, and the reproduce command (CI runs without torch)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from nawa.evaluation.report import compare, render_markdown, wilson
from nawa.evaluation.runner import make_backend, run

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def oracle_report(tmp_path_factory):
    return run(make_backend("oracle"), "dev", runs_dir=tmp_path_factory.mktemp("runs"))


def test_oracle_pipeline_scores_100(oracle_report) -> None:
    out_dir, rep = oracle_report
    assert rep["summary"]["macro_accuracy"] == 1.0
    assert rep["summary"]["items"] == 243
    assert rep["targets"]["T1_hallucination_rate"] == 0.0
    assert rep["targets"]["T6_citation_accuracy"] == 1.0
    assert {"predictions.jsonl", "lineage.json", "report.json"} <= {p.name for p in out_dir.iterdir()}
    L = rep["lineage"]
    for k in ("split_sha256", "git", "config_hash", "hardware", "model", "created_utc"):
        assert k in L


def test_report_contains_no_item_text(oracle_report) -> None:
    out_dir, rep = oracle_report
    text = json.dumps(rep, ensure_ascii=False)
    first = json.loads((out_dir / "predictions.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert first["output"] not in text and "messages" not in text and "بلدة" not in text


def test_report_rerenders_from_saved_predictions(oracle_report) -> None:
    out_dir, rep = oracle_report
    r = subprocess.run([sys.executable, str(ROOT / "eval" / "report.py"), str(out_dir)], capture_output=True, text=True)
    assert r.returncode == 0
    again = json.loads(r.stdout)
    assert again["suites"] == rep["suites"] and again["summary"] == rep["summary"]
    assert "macro accuracy" in render_markdown(rep)


def test_always_abstain_cannot_game_t2(tmp_path) -> None:
    _, rep = run(make_backend("always_abstain"), "dev", ["abstention", "faithfulness"], runs_dir=tmp_path)
    ab = rep["suites"]["abstention"]
    assert ab["abstention_recall"]["value"] == 1.0 and ab["answerable_accuracy"]["value"] == 0.0
    _, base = run(make_backend("oracle"), "dev", ["abstention", "faithfulness"], runs_dir=tmp_path)
    assert compare(rep, base)["T2"]["pass"] is False


def test_compare_relative_targets() -> None:
    base = {"targets": {"T1_hallucination_rate": 0.40, "T2_abstention_recall": 0.3, "T2_answerable_accuracy": 0.80,
                        "T5_regression_general_accuracy": 0.60}}
    good = {"targets": {"T1_hallucination_rate": 0.20, "T2_abstention_recall": 0.85, "T2_answerable_accuracy": 0.77,
                        "T5_regression_general_accuracy": 0.59}}
    c = compare(good, base)
    assert c["T1"]["pass"] and c["T2"]["pass"] and c["T5"]["pass"]
    bad = {"targets": {"T1_hallucination_rate": 0.21, "T2_abstention_recall": 0.85, "T2_answerable_accuracy": 0.75,
                       "T5_regression_general_accuracy": 0.58}}
    c = compare(bad, base)
    assert not c["T1"]["pass"] and not c["T2"]["pass"] and not c["T5"]["pass"]


def test_wilson_interval() -> None:
    lo, hi = wilson(15, 30)
    assert 0.31 < lo < 0.34 and 0.66 < hi < 0.69
    assert wilson(0, 0) is None


def test_targets_match_roadmap_numbers() -> None:
    t = yaml.safe_load((ROOT / "eval" / "targets.yaml").read_text(encoding="utf-8"))["targets"]
    assert t["T1"]["min_relative_reduction"] == 0.50
    assert t["T2"]["min_abstention_recall"] == 0.80 and t["T2"]["max_answerable_relative_drop"] == 0.05
    assert t["T4"]["max_memory_gb"] == 3.0
    assert t["T5"]["max_relative_drop"] == 0.03
    assert t["T3"]["status"] == "OPTIONAL"  # ADR-0003: not a gate condition


def test_frozen_run_requires_eval_role(monkeypatch, tmp_path) -> None:
    from nawa.evaluation.frozen import RoleError
    monkeypatch.delenv("NAWA_ROLE", raising=False)
    with pytest.raises(RoleError):
        run(make_backend("oracle"), "frozen", frozen_dir=tmp_path, runs_dir=tmp_path)


def test_save_report_refuses_limit() -> None:
    r = subprocess.run([sys.executable, str(ROOT / "eval" / "run_eval.py"), "--model", "oracle", "--limit", "1",
                        "--save-report"], capture_output=True, text=True)
    assert r.returncode != 0 and "refusing" in r.stderr


def test_make_repro_target_is_implemented() -> None:
    mk = (ROOT / "Makefile").read_text(encoding="utf-8")
    lines = mk.split("\nrepro:", 1)[1].splitlines()[1:]
    block = "\n".join(x for x in lines[:next(i for i, x in enumerate(lines) if not x.startswith("\t"))])
    assert "not_implemented" not in block and "run_eval.py" in block
