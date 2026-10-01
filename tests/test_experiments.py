"""P4-06: the P4 experiment record and its validator (ADR-0007)."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from nawa import experiments as ex

ROOT = Path(__file__).resolve().parents[1]
OPEN = ex.Policy(od03_open=True, p4_08_done=False)


def valid() -> dict:
    return ex.synthetic_valid_record(3, 2026)


def test_committed_log_is_valid_under_current_roadmap_policy() -> None:
    errs = ex.validate_log((ROOT / "experiments/log.jsonl").read_text(encoding="utf-8").splitlines(),
                           ex.Policy.from_roadmap())
    assert errs == []


def test_policy_reads_od03_open_and_p4_08_blocked_from_roadmap() -> None:
    assert ex.Policy.from_roadmap() == ex.Policy(od03_open=True, p4_08_done=False)


def test_required_fields_cover_agents_section_8() -> None:
    agents_8 = {"experiment_id", "track", "purpose", "git_commit", "data_repo_id", "data_revision", "data_sha256",
                "base_model_repo_id", "config_hash", "seed", "hardware", "training_steps", "gpu_hours",
                "metrics", "failure_cases", "artifact", "conclusion", "next_action"}
    assert agents_8 <= set(ex.REQUIRED_P4_FIELDS)
    assert {"software", "base_model_revision", "task_id"} <= set(ex.REQUIRED_P4_FIELDS)


def test_valid_record_passes() -> None:
    assert ex.validate_p4(valid(), OPEN) == []


@pytest.mark.parametrize("name", sorted(ex.mutations()))
def test_each_rule_violation_is_rejected(name: str) -> None:
    rec = copy.deepcopy(valid())
    ex.mutations()[name](rec)
    assert ex.validate_p4(rec, OPEN), name


def test_improvement_claim_on_synthetic_data_is_rejected_with_reason() -> None:
    rec = valid()
    rec["claims"].append({"type": "improvement", "text": "ternary beats dense"})
    assert any("synthetic" in e for e in ex.validate_p4(rec, OPEN))


def test_real_data_rejected_while_od03_open_and_allowed_only_after() -> None:
    rec = valid()
    rec["data_kind"] = "real"
    assert any("OD-03" in e for e in ex.validate_p4(rec, OPEN))
    assert not any("OD-03" in e for e in ex.validate_p4(rec, ex.Policy(od03_open=False)))


def test_artifact_rejected_until_p4_08_done() -> None:
    rec = valid()
    rec["artifact"] = {"repo_id": "vuuuv/nawa-core", "revision": "dev"}
    assert ex.validate_p4(rec, OPEN)
    assert ex.validate_p4(rec, ex.Policy(p4_08_done=True)) == []


def test_passed_is_rederived_not_trusted() -> None:
    rec = valid()
    rec["metrics"]["loss"] = 5.0           # criterion loss <= 2.0 now fails, record still says passed
    assert any("passed" in e for e in ex.validate_p4(rec, OPEN))
    rec["passed"], rec["status"] = False, "FAILED"
    assert ex.validate_p4(rec, OPEN) == []  # a recorded failure is a valid record


def test_append_refuses_invalid_and_duplicate(tmp_path: Path) -> None:
    log = tmp_path / "log.jsonl"
    ex.append(valid(), log, OPEN)
    with pytest.raises(ex.RecordError):
        ex.append(valid(), log, OPEN)       # duplicate id
    bad = ex.synthetic_valid_record(4, 2026)
    bad["claims"].append({"type": "adoption", "text": "adopt"})
    with pytest.raises(ex.RecordError):
        ex.append(bad, log, OPEN)
    assert len(log.read_text(encoding="utf-8").splitlines()) == 1


def test_log_ids_must_ascend(tmp_path: Path) -> None:
    a, b = ex.synthetic_valid_record(5, 1), ex.synthetic_valid_record(2, 1)
    errs = ex.validate_log([json.dumps(a), json.dumps(b)], OPEN)
    assert any("ascending" in e for e in errs)


def test_config_hash_matches_decoder_convention() -> None:
    torch = pytest.importorskip("torch")  # noqa: F841
    from nawa.model import DecoderConfig
    cfg = DecoderConfig.from_yaml(ROOT / "configs/base_model.yaml")
    assert ex.config_hash(cfg.to_dict()) == cfg.config_hash()


def test_bench_meets_registered_criteria() -> None:
    res = ex.bench(2026)
    assert all(ex.evaluate_criteria(ex.BENCH_CRITERIA, res).values()), res
    assert res["mutation_types"] == len(ex.mutations()) >= 20


def test_smoke_run_is_deterministic_and_builds_a_valid_record() -> None:
    pytest.importorskip("torch")
    run = ex.smoke_run(seed=11)
    assert run.metrics["rerun_identical"] is True
    rec = run.build("EXP-9999", OPEN)
    assert ex.validate_p4(rec, OPEN) == []
    assert rec["data_kind"] == "synthetic" and rec["artifact"] is None and rec["track"] == "S"
    assert not any(c["type"] in ("improvement", "adoption") for c in rec["claims"])


def test_recorded_p4_06_experiment_reproduces() -> None:
    """EXP-0024 (P4-06): re-running the smoke part gives the same data, loss and weight hashes."""
    pytest.importorskip("torch")
    recs = [json.loads(l) for l in (ROOT / "experiments/log.jsonl").read_text(encoding="utf-8").splitlines()]
    rec = next(r for r in recs if r.get("task_id") == "P4-06")
    cfg = {k: v for k, v in rec["config"].items() if k != "bench"}
    fresh = ex._smoke_once(rec["seed"], cfg)
    for key in ("data_sha256", "model_config_hash", "parameters"):          # exact everywhere
        assert fresh[key] == rec["metrics"][key], key
    for key in ("initial_val_loss", "final_val_loss"):                      # float kernels differ across builds
        assert abs(fresh[key] - rec["metrics"][key]) <= 1e-3, key
    if ex.software() == rec["software"] and ex.hardware()["machine"] == rec["hardware"]["machine"]:
        assert fresh["final_weights_sha256"] == rec["metrics"]["final_weights_sha256"]
        assert fresh["final_val_loss"] == rec["metrics"]["final_val_loss"]
