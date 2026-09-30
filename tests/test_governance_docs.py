"""Tie P0 documents to ROADMAP.md so they cannot drift silently (P0-02, P0-03, P0-04, P0-07a)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from nawa.budget import check, load_budget

ROOT = Path(__file__).resolve().parents[1]
ROADMAP = (ROOT / "ROADMAP.md").read_text(encoding="utf-8")


def _t_rows(text: str) -> dict[str, str]:
    return {m[1]: m[2] for m in re.finditer(r"^\| (T[1-6]) \|(.*)$", text, flags=re.M)}


def test_success_criteria_carries_every_roadmap_target_number() -> None:
    """P0-03: every number in ROADMAP §1.3 appears in the same T row of SUCCESS_CRITERIA.md."""
    sc = _t_rows((ROOT / "SUCCESS_CRITERIA.md").read_text(encoding="utf-8"))
    rm = _t_rows(ROADMAP[ROADMAP.index("## 1.3"):ROADMAP.index("# 2. الحالة الحالية")])
    assert set(rm) == set(sc) == {f"T{i}" for i in range(1, 7)}
    for t, row in rm.items():
        cells = row.split("|")[0]
        for num in re.findall(r"\d+(?:[–-]\d+)?", cells):
            assert num in sc[t], f"{t}: number {num} from ROADMAP missing in SUCCESS_CRITERIA"


def test_architecture_covers_roadmap_system_definition() -> None:
    """P0-02: every component of ROADMAP §1.1 is described in ARCHITECTURE.md."""
    arch = (ROOT / "ARCHITECTURE.md").read_text(encoding="utf-8")
    for comp in ("Core Model", "Tokenizer", "Router", "Experts", "Retrieval", "Tools", "Reasoning",
                 "Verification", "Abstention", "Memory", "Evaluation", "Runtime"):
        assert f"**{comp}**" in arch, comp
    assert "Core مقابل Runtime" in arch


def test_risk_register_is_well_formed() -> None:
    """P0-04: risks have ID, L, I, score = L*I, mitigation, and a status."""
    rows = re.findall(r"^\| (RISK-\d\d) \|([^|]+)\| (\d) \| (\d) \| (\d) \|([^|]+)\|([^|]+)\|([^|]+)\|$",
                      (ROOT / "RISK_REGISTER.md").read_text(encoding="utf-8"), flags=re.M)
    assert len(rows) >= 10
    ids = [r[0] for r in rows]
    assert len(ids) == len(set(ids))
    for rid, _desc, l, i, score, mitig, _task, status in rows:
        assert int(l) * int(i) == int(score), rid
        assert mitig.strip(), rid
        assert status.strip().split()[0] in {"OPEN", "MITIGATED", "ACCEPTED_TEMPORARY", "CLOSED"}, rid


def test_budget_denies_gpu_and_paid_work_until_owner_sets_caps() -> None:
    cfg = load_budget()
    assert cfg["caps"]["gpu_hours"] is None and cfg["caps"]["money_usd"] is None  # OD-05 still open
    assert cfg["stop_at_fraction"] == 0.8
    assert check("cpu_local").allowed
    assert not check("gpu", gpu_hours=1).allowed
    assert not check("paid_service", money_usd=1).allowed


def test_budget_enforces_80_percent_stop() -> None:
    cfg = {"caps": {"gpu_hours": 100, "money_usd": 10}, "spent": {"gpu_hours": 70, "money_usd": 0}, "stop_at_fraction": 0.8}
    assert check("gpu", gpu_hours=10, cfg=cfg).allowed
    assert not check("gpu", gpu_hours=11, cfg=cfg).allowed
    with pytest.raises(ValueError):
        check("quantum", cfg=cfg)
