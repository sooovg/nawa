"""P1-06: target definitions are complete, internal, unloosened, and not anchored before P1-06a (ADR-0004)."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml

from nawa.evaluation.report import compare
from nawa.evaluation.targets import TARGETS, TargetsError, load_targets, validate

ROOT = Path(__file__).resolve().parents[1]


def data() -> dict:
    return yaml.safe_load(TARGETS.read_text(encoding="utf-8"))


def test_targets_file_is_valid_and_definitions_fixed() -> None:
    d = load_targets()
    assert d["status"] == "definitions_fixed" and d["baseline_reference"] is None
    for tid in ("T1", "T2", "T5"):
        assert d["targets"][tid]["status"] == "DEFINED" and d["targets"][tid]["reference"] == "model_only_core"
    assert d["targets"]["T3"]["status"] == "OPTIONAL"


@pytest.mark.parametrize("tid,key,bad", [
    ("T1", "min_relative_reduction", 0.49), ("T2", "min_abstention_recall", 0.79),
    ("T2", "max_answerable_relative_drop", 0.06), ("T4", "max_memory_gb", 3.5), ("T5", "max_relative_drop", 0.04),
])
def test_loosening_any_threshold_is_rejected(tid: str, key: str, bad: float) -> None:
    d = data()
    d["targets"][tid][key] = bad
    with pytest.raises(TargetsError):
        validate(d)


def test_raising_a_threshold_is_allowed() -> None:
    d = data()
    d["targets"]["T1"]["min_relative_reduction"] = 0.6
    validate(d)


def test_anchor_before_p1_06a_is_rejected() -> None:
    d = data()
    d["targets"]["T1"]["anchor"] = {"run_id": "x", "value": 0.4}
    with pytest.raises(TargetsError):
        validate(d)


@pytest.mark.parametrize("mutate", [
    lambda d: d["targets"]["T1"].update(reference="optional_indicator"),   # gate target without internal reference
    lambda d: d["targets"]["T2"].pop("direction"),
    lambda d: d["evaluation_source"]["splits"].update(calibrate="frozen"),   # tuning on frozen
    lambda d: d["targets"]["T1"].pop("guard"),
    lambda d: d["targets"]["T3"].update(status="DEFINED"),
    lambda d: d["targets"].pop("T6"),
])
def test_definition_drift_is_rejected(mutate) -> None:
    d = copy.deepcopy(data())
    mutate(d)
    with pytest.raises(TargetsError):
        validate(d)


def test_recorded_trivial_references_match_a_fresh_run(tmp_path) -> None:
    from nawa.evaluation.runner import make_backend, run
    rec = data()["trivial_references"]
    for name in ("oracle", "always_abstain"):
        _, rep = run(make_backend(name), "dev", runs_dir=tmp_path)
        assert rep["targets"] == rec[name]["dev"], name


def test_always_abstain_cannot_pass_t1_through_the_guard() -> None:
    """A reference that hallucinates 40%; a candidate that always abstains has 0% hallucination (raw T1 pass)
    but loses all answerable accuracy, so the guarded T1 fails (ADR-0004 D3)."""
    ref = {"targets": {"T1_hallucination_rate": 0.40, "T2_abstention_recall": 0.3, "T2_answerable_accuracy": 0.80,
                       "T5_regression_general_accuracy": 0.60}}
    abstain = {"targets": {"T1_hallucination_rate": 0.0, "T2_abstention_recall": 1.0, "T2_answerable_accuracy": 0.0,
                           "T5_regression_general_accuracy": 0.0}}
    c = compare(abstain, ref)
    assert c["T1"]["pass_unguarded"] is True and c["T1"]["pass"] is False
    assert c["T2"]["pass"] is False and c["T5"]["pass"] is False


def test_success_criteria_and_targets_agree_on_reference_types() -> None:
    sc = (ROOT / "SUCCESS_CRITERIA.md").read_text(encoding="utf-8")
    for tid, t in data()["targets"].items():
        row = next(line for line in sc.splitlines() if line.startswith(f"| {tid} |"))
        assert f"`{t['reference']}`" in row, (tid, row)
