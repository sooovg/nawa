"""R-03 tests: multi-model development review harness (ADR-0003 D1).

Tests the framework for using external models as development tools:
- Role registry and validation
- Model registry (register, require, roles)
- Review records (create, log, query)
- Disagreement records (create, resolve)
- Payload safety checks (secrets, frozen refs, forbidden paths)
- Decision gate (no single-model decisions)
"""

from __future__ import annotations

import json
import os
import tempfile

import pytest

from nawa.review import (
    DisagreementRecord,
    ModelEntry,
    ModelRegistry,
    PayloadCheck,
    ReviewLog,
    ReviewRecord,
    ReviewRole,
    can_decide,
    check_payload,
    make_review,
)

# ---- ReviewRole ----------------------------------------------------------------------------------

def test_review_role_from_str():
    assert ReviewRole.from_str("reviewer") == ReviewRole.REVIEWER
    assert ReviewRole.from_str("designer") == ReviewRole.DESIGNER
    assert ReviewRole.from_str("tester") == ReviewRole.TESTER
    assert ReviewRole.from_str("error_hunter") == ReviewRole.ERROR_HUNTER
    assert ReviewRole.from_str("doc_writer") == ReviewRole.DOC_WRITER


def test_review_role_from_str_invalid():
    with pytest.raises(ValueError, match="unknown review role"):
        ReviewRole.from_str("admin")


def test_review_role_values():
    roles = [r.value for r in ReviewRole]
    assert roles == ["reviewer", "designer", "tester", "error_hunter", "doc_writer"]


# ---- ModelEntry / ModelRegistry -----------------------------------------------------------------

def test_model_entry_creation():
    entry = ModelEntry(
        model_id="provider/model-a",
        provider="provider",
        roles=frozenset({"reviewer", "tester"}),
        authorized_by="owner",
        date_added="2026-09-30",
    )
    assert entry.model_id == "provider/model-a"
    assert entry.has_role("reviewer")
    assert entry.has_role(ReviewRole.TESTER)
    assert not entry.has_role("designer")


def test_model_entry_round_trip():
    entry = ModelEntry(
        model_id="provider/model-a",
        provider="provider",
        roles=frozenset({"reviewer", "tester"}),
        authorized_by="owner",
        date_added="2026-09-30",
        notes="test model",
    )
    d = entry.to_dict()
    assert d["roles"] == ["reviewer", "tester"]
    restored = ModelEntry.from_dict(d)
    assert restored.model_id == entry.model_id
    assert restored.roles == entry.roles


def test_model_registry_empty_by_default():
    reg = ModelRegistry()
    assert reg.list_models() == []
    assert not reg.has_model("any/model")


def test_model_registry_register_and_get():
    reg = ModelRegistry()
    entry = ModelEntry(
        model_id="provider/model-a",
        provider="provider",
        roles=frozenset({"reviewer"}),
        authorized_by="owner",
        date_added="2026-09-30",
    )
    reg.register(entry)
    assert reg.has_model("provider/model-a")
    assert reg.get("provider/model-a") is entry


def test_model_registry_duplicate_rejected():
    reg = ModelRegistry()
    entry = ModelEntry(
        model_id="provider/model-a",
        provider="provider",
        roles=frozenset({"reviewer"}),
        authorized_by="owner",
        date_added="2026-09-30",
    )
    reg.register(entry)
    with pytest.raises(ValueError, match="already registered"):
        reg.register(entry)


def test_model_registry_require_model_unregistered():
    reg = ModelRegistry()
    with pytest.raises(ValueError, match="not registered"):
        reg.require_model("unregistered/model")


def test_model_registry_require_role_not_authorized():
    reg = ModelRegistry()
    entry = ModelEntry(
        model_id="provider/model-a",
        provider="provider",
        roles=frozenset({"reviewer"}),
        authorized_by="owner",
        date_added="2026-09-30",
    )
    reg.register(entry)
    with pytest.raises(ValueError, match="not registered for role"):
        reg.require_role("provider/model-a", ReviewRole.DESIGNER)


def test_model_registry_require_role_authorized():
    reg = ModelRegistry()
    entry = ModelEntry(
        model_id="provider/model-a",
        provider="provider",
        roles=frozenset({"reviewer", "designer"}),
        authorized_by="owner",
        date_added="2026-09-30",
    )
    reg.register(entry)
    result = reg.require_role("provider/model-a", ReviewRole.DESIGNER)
    assert result.model_id == "provider/model-a"


def test_model_registry_round_trip():
    reg = ModelRegistry()
    reg.register(ModelEntry(
        model_id="provider/a",
        provider="provider",
        roles=frozenset({"reviewer"}),
        authorized_by="owner",
        date_added="2026-09-30",
    ))
    reg.register(ModelEntry(
        model_id="provider/b",
        provider="provider",
        roles=frozenset({"tester", "error_hunter"}),
        authorized_by="owner",
        date_added="2026-09-30",
    ))
    d = reg.to_dict()
    restored = ModelRegistry.from_dict(d)
    assert len(restored.list_models()) == 2
    assert restored.has_model("provider/a")
    assert restored.has_model("provider/b")


# ---- ReviewRecord --------------------------------------------------------------------------------

def test_review_record_creation():
    r = ReviewRecord(
        experiment_id="EXP-0100",
        model_id="provider/model-a",
        role=ReviewRole.REVIEWER,
        artifact="src/nawa/model/decoder.py",
        review_date="2026-09-30",
        findings=["issue with init"],
        recommendations=["use different init"],
        conclusion="minor issue",
    )
    assert r.experiment_id == "EXP-0100"
    assert r.role == ReviewRole.REVIEWER
    assert len(r.findings) == 1


def test_review_record_round_trip():
    r = ReviewRecord(
        experiment_id="EXP-0100",
        model_id="provider/model-a",
        role=ReviewRole.DESIGNER,
        artifact="configs/base_model.yaml",
        review_date="2026-09-30",
        findings=["config too small"],
        recommendations=["increase d_model"],
        accepted=["increase d_model"],
        rejected=["change to GELU"],
        conclusion="config is reference, not final",
    )
    d = r.to_dict()
    restored = ReviewRecord.from_dict(d)
    assert restored.experiment_id == r.experiment_id
    assert restored.role == r.role
    assert restored.findings == r.findings
    assert restored.accepted == r.accepted


def test_make_review_with_today_date():
    from datetime import date
    r = make_review(
        experiment_id="EXP-0100",
        model_id="provider/model-a",
        role="reviewer",
        artifact="src/nawa/training/trainer.py",
        findings=["missing feature X"],
    )
    assert r.review_date == date.today().isoformat()
    assert r.role == ReviewRole.REVIEWER


# ---- DisagreementRecord -------------------------------------------------------------------------

def test_disagreement_creation():
    d = DisagreementRecord(
        disagreement_id="DIS-001",
        artifact="src/nawa/model/decoder.py",
        positions=[
            {"model": "provider/a", "position": "use RoPE"},
            {"model": "provider/b", "position": "use ALiBi"},
        ],
    )
    assert d.disagreement_id == "DIS-001"
    assert not d.resolved
    assert d.resolution == "deferred"


def test_disagreement_resolve():
    d = DisagreementRecord(
        disagreement_id="DIS-001",
        artifact="src/nawa/model/decoder.py",
        positions=[
            {"model": "provider/a", "position": "use RoPE"},
            {"model": "provider/b", "position": "use ALiBi"},
        ],
    )
    d.resolve("measurement", "RoPE tested better on XOR")
    assert d.resolved
    assert d.resolution == "measurement"
    assert d.resolution_note == "RoPE tested better on XOR"


def test_disagreement_resolve_invalid_method():
    d = DisagreementRecord(
        disagreement_id="DIS-001",
        artifact="test",
        positions=[],
    )
    with pytest.raises(ValueError, match="resolution method"):
        d.resolve("vote", "")


def test_disagreement_deferred_is_not_resolved():
    d = DisagreementRecord(
        disagreement_id="DIS-001",
        artifact="test",
        positions=[],
    )
    d.resolve("deferred", "waiting for more data")
    assert not d.resolved
    assert d.resolution == "deferred"


# ---- ReviewLog -----------------------------------------------------------------------------------

def test_review_log_add_review():
    log = ReviewLog()
    r = make_review("EXP-001", "provider/a", "reviewer", "src/nawa/model.py")
    log.add_review(r)
    assert len(log.reviews) == 1
    assert log.get_reviews_for_artifact("src/nawa/model.py") == [r]


def test_review_log_add_disagreement():
    log = ReviewLog()
    d = DisagreementRecord("DIS-001", "artifact", [
        {"model": "a", "position": "yes"},
        {"model": "b", "position": "no"},
    ])
    log.add_disagreement(d)
    assert len(log.disagreements) == 1
    assert log.get_disagreements(resolved=False) == [d]


def test_review_log_resolve_disagreement():
    log = ReviewLog()
    d = DisagreementRecord("DIS-001", "artifact", [
        {"model": "a", "position": "yes"},
        {"model": "b", "position": "no"},
    ])
    log.add_disagreement(d)
    log.resolve_disagreement("DIS-001", "test", "test passed")
    assert log.disagreements[0].resolved
    assert log.get_disagreements(resolved=False) == []


def test_review_log_resolve_not_found():
    log = ReviewLog()
    with pytest.raises(ValueError, match="not found"):
        log.resolve_disagreement("DIS-999", "test", "")


def test_review_log_has_multiple_models():
    log = ReviewLog()
    log.add_review(make_review("EXP-1", "provider/a", "reviewer", "file.py"))
    assert not log.has_multiple_models_reviewed("file.py")
    log.add_review(make_review("EXP-2", "provider/b", "reviewer", "file.py"))
    assert log.has_multiple_models_reviewed("file.py")


def test_review_log_get_reviews_by_model():
    log = ReviewLog()
    log.add_review(make_review("EXP-1", "provider/a", "reviewer", "file1.py"))
    log.add_review(make_review("EXP-2", "provider/a", "reviewer", "file2.py"))
    log.add_review(make_review("EXP-3", "provider/b", "reviewer", "file3.py"))
    a_reviews = log.get_reviews_by_model("provider/a")
    assert len(a_reviews) == 2
    b_reviews = log.get_reviews_by_model("provider/b")
    assert len(b_reviews) == 1


def test_review_log_summary():
    log = ReviewLog()
    log.add_review(make_review("EXP-1", "provider/a", "reviewer", "file1.py"))
    log.add_review(make_review("EXP-2", "provider/b", "reviewer", "file2.py"))
    log.add_disagreement(DisagreementRecord("DIS-1", "file1.py", []))
    s = log.summary()
    assert s["total_reviews"] == 2
    assert s["total_disagreements"] == 1
    assert s["unresolved_disagreements"] == 1
    assert s["artifacts_reviewed"] == 2
    assert s["models_used"] == ["provider/a", "provider/b"]


def test_review_log_persistence():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "review_log.jsonl")
        log = ReviewLog(path)
        log.add_review(make_review("EXP-1", "provider/a", "reviewer", "file.py"))
        log.add_disagreement(DisagreementRecord("DIS-1", "file.py", []))

        # New log loads from file
        log2 = ReviewLog(path)
        log2.load()
        assert len(log2.reviews) == 1
        assert len(log2.disagreements) == 1
        assert log2.reviews[0].artifact == "file.py"


# ---- Payload safety checks -----------------------------------------------------------------------

def test_check_payload_safe():
    result = check_payload("This is a normal code review payload about model architecture.")
    assert result.safe
    assert result.violations == []


def test_check_payload_detects_hf_token():
    result = check_payload("Use this token: hf_aBcDeFgHiJkLm")
    assert not result.safe
    assert len(result.violations) > 0


def test_check_payload_detects_github_pat():
    result = check_payload("ghp_aBcDeFgHiJkLm")
    assert not result.safe


def test_check_payload_detects_openai_key():
    result = check_payload("sk-aBcDeFgHiJkLm")
    assert not result.safe


def test_check_payload_detects_frozen_reference():
    result = check_payload("Check eval/frozen_item_hashes.txt for the hash")
    assert not result.safe
    assert any("frozen" in v for v in result.violations)


def test_check_payload_detects_env_file():
    result = check_payload("Load credentials from .env file")
    assert not result.safe


def test_check_payload_detects_credential_assignment():
    result = check_payload('password: "supersecret123"')
    assert not result.safe


def test_check_payload_dict():
    result = check_payload({"code": "x = 1", "token": "hf_aBcDeFgHiJkLm"})
    assert not result.safe


def test_check_payload_list():
    result = check_payload(["normal string", "another string"])
    assert result.safe


# ---- Decision gate -------------------------------------------------------------------------------

def test_can_decide_no_reviews():
    log = ReviewLog()
    can, reason = can_decide("file.py", log)
    assert not can
    assert "no model" in reason


def test_can_decide_single_model_no_check():
    log = ReviewLog()
    log.add_review(make_review("EXP-1", "provider/a", "reviewer", "file.py"))
    can, reason = can_decide("file.py", log)
    assert not can
    assert "single model" in reason


def test_can_decide_single_model_with_check():
    log = ReviewLog()
    log.add_review(make_review("EXP-1", "provider/a", "reviewer", "file.py"))
    can, reason = can_decide("file.py", log, deterministic_check_passed=True)
    assert can
    assert "deterministic check" in reason


def test_can_decide_multiple_models():
    log = ReviewLog()
    log.add_review(make_review("EXP-1", "provider/a", "reviewer", "file.py"))
    log.add_review(make_review("EXP-2", "provider/b", "reviewer", "file.py"))
    can, reason = can_decide("file.py", log)
    assert can
    assert "multiple models" in reason


def test_can_decide_same_model_twice_does_not_count():
    log = ReviewLog()
    log.add_review(make_review("EXP-1", "provider/a", "reviewer", "file.py"))
    log.add_review(make_review("EXP-2", "provider/a", "reviewer", "file.py"))
    can, reason = can_decide("file.py", log)
    assert not can
    assert "single model" in reason
