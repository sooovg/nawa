"""P1-08: Failure Atlas schema, verified ingestion from eval runs, and correct abstention attribution."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from nawa.atlas import INCOMING, AtlasError, read, record_id, records_from_run, validate_all, validate_record
from nawa.evaluation import suites
from nawa.evaluation.runner import build_public, make_backend, run

TS = "2026-09-30T00:00:00Z"


@pytest.fixture(scope="module")
def abstain_run(tmp_path_factory) -> Path:
    d, _ = run(make_backend("always_abstain"), "dev", runs_dir=tmp_path_factory.mktemp("runs"))
    return d


def _item(suite: str, answerable: bool | None = None):
    for it in build_public()["dev"][suite]:
        if answerable is None or it.gold.get("answerable") is answerable:
            return it
    raise LookupError(suite)


def test_abstention_on_answerable_item_is_over_abstention_not_suite_default() -> None:
    it = _item("reasoning_math")
    raw = suites.get("reasoning_math").score(it, "غير موجود في السياق")
    assert raw["failure"] == "FT-03"  # the scorer's default, which was wrong for an abstention
    s = suites.attribute_abstention(raw, "غير موجود في السياق", it.gold.get("answerable"))
    assert s["failure"] == "FT-13" and s["failure_suite_default"] == "FT-03"
    assert s["abstained"] and not s["hallucinated"] and s["correct"] is False


def test_attribution_leaves_other_cases_alone() -> None:
    it = _item("reasoning_math")
    mod = suites.get("reasoning_math")
    wrong = mod.score(it, "الجواب: 999999")
    assert suites.attribute_abstention(wrong, "الجواب: 999999", None) == wrong  # a real calculation error
    right = mod.score(it, mod.oracle(it))
    assert suites.attribute_abstention(right, mod.oracle(it), None) == right
    un = _item("abstention", answerable=False)
    guess = suites.get("abstention").score(un, "لا أعرف")
    assert suites.attribute_abstention(guess, "لا أعرف", False) == guess  # unanswerable twin: suite decides


def test_ingest_verifies_every_failure_and_blocks_training(abstain_run: Path) -> None:
    preds = [json.loads(line) for line in (abstain_run / "predictions.jsonl").open(encoding="utf-8")]
    recs = records_from_run(abstain_run, TS)
    assert len(recs) == sum(not p["score"]["correct"] for p in preds) > 0
    validate_all(recs)
    assert all(r["status"] == "verified" and r["verified_truth"] for r in recs)
    assert all(r["train_eligible"] is False and r["train_block_reason"] for r in recs)
    assert {r["category"] for r in recs} == {"FT-13"}  # always_abstain only over-abstains


def test_oracle_run_gives_no_failures(tmp_path) -> None:
    d, _ = run(make_backend("oracle"), "dev", runs_dir=tmp_path)
    assert records_from_run(d, TS) == []


def test_frozen_and_limited_runs_are_refused(abstain_run: Path, tmp_path) -> None:
    for patch in ({"split": "frozen"}, {"limit": 3}):
        d = tmp_path / next(iter(patch))
        d.mkdir()
        lin = json.loads((abstain_run / "lineage.json").read_text(encoding="utf-8"))
        lin.update(patch)
        (d / "lineage.json").write_text(json.dumps(lin), encoding="utf-8")
        (d / "predictions.jsonl").write_text("", encoding="utf-8")
        with pytest.raises(AtlasError):
            records_from_run(d, TS)


@pytest.mark.parametrize("mutate", [
    lambda r: r.update(category="FT-99"),
    lambda r: r.update(train_eligible=True),
    lambda r: r.update(split="frozen"),
    lambda r: r.update(verified_truth=None),
    lambda r: r.update(bad_output=r["bad_output"] + "x"),     # id no longer matches the content
    lambda r: r.update(status="maybe"),
    lambda r: r.pop("license"),
    lambda r: r.update(secondary_categories=[r["category"]]),
])
def test_invalid_records_are_rejected(abstain_run: Path, mutate) -> None:
    r = copy.deepcopy(records_from_run(abstain_run, TS)[0])
    mutate(r)
    with pytest.raises(AtlasError):
        validate_record(r)


def test_manifest_batch_is_reproduced_exactly(abstain_run: Path) -> None:
    """Records are not in Git; the manifest pins them by digest, and a fresh run must reproduce it exactly."""
    import yaml
    from nawa.atlas import REPO, digest
    man = yaml.safe_load((REPO / "data_pipeline" / "atlas" / "manifest.yaml").read_text(encoding="utf-8"))
    batch = next(b for b in man["batches"] if b["model"] == "always_abstain" and b["split"] == "dev")
    recs = records_from_run(abstain_run, TS)
    assert len(recs) == batch["records"] and sum(r["status"] == "verified" for r in recs) == batch["verified"]
    assert sum(r["train_eligible"] for r in recs) == batch["train_eligible"]
    assert digest(recs) == batch["digest"]
    local = sorted(INCOMING.glob("*.jsonl"))  # present on the machine that ingested; absent in CI
    if local:
        on_disk = read(local)
        validate_all(on_disk)
        assert all(r["id"] == record_id(r["model"], r["item_id"], r["bad_output"]) for r in on_disk)
