"""P1-03: frozen split is pinned, private, disjoint from public splits, and role-guarded."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest
import yaml

from nawa.evaluation import frozen
from nawa.evaluation.build import build_public, hashes
from nawa.evaluation.schema import SUITES

ROOT = Path(__file__).resolve().parents[1]
HEX = re.compile(r"^[0-9a-f]{64}$")


def test_frozen_sha_covers_every_suite() -> None:
    exp = frozen.expected_digests()
    assert set(exp) == {f"{s}.jsonl" for s in SUITES}
    assert all(HEX.match(d) for d in exp.values())


def test_item_hashes_well_formed_and_match_manifest() -> None:
    hs = frozen.ITEM_HASHES.read_text(encoding="utf-8").split()
    man = yaml.safe_load((ROOT / "eval" / "frozen_manifest.yaml").read_text(encoding="utf-8"))
    assert len(hs) == len(set(hs)) == man["total_items"] == sum(man["items"].values())
    assert all(HEX.match(h) for h in hs)
    assert man["private"] is True and man["repo_id"] == "vuuuv/nawa-eval"


def test_no_leakage_between_public_splits_and_frozen() -> None:
    fz = set(frozen.ITEM_HASHES.read_text(encoding="utf-8").split())
    pub = build_public()
    assert not (hashes(pub["dev"]) | hashes(pub["calib"])) & fz


def test_no_frozen_content_committed() -> None:
    out = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=ROOT,
                         capture_output=True, text=True).stdout.split()
    assert not [p for p in out if "frozen" in p and p.endswith((".jsonl", ".json", ".yaml")) and p != "eval/frozen_manifest.yaml"]
    assert not [p for p in out if "factual_frozen_bank" in p]


def test_role_guard(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("NAWA_ROLE", raising=False)
    with pytest.raises(frozen.RoleError):
        frozen.verify(tmp_path)
    with pytest.raises(frozen.RoleError):
        frozen.build(tmp_path / "bank.yaml", tmp_path)
    monkeypatch.setenv("NAWA_ROLE", "eval")
    with pytest.raises(ValueError):
        frozen.build(tmp_path / "bank.yaml", ROOT / "eval")  # output inside repo is refused
