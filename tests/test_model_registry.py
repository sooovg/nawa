"""Open-weight model registry checks (ADR-0003 D2)."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
REG = yaml.safe_load((ROOT / "configs" / "model_registry.yaml").read_text(encoding="utf-8"))
SIX = ("need", "why_not_others", "nawa_part", "affects_final_product", "license", "license_limits", "fallback")
PSEUDO = {"oracle", "always_abstain"}


def entries() -> dict[tuple[str, str], dict]:
    return {(m["repo_id"], m["revision"]): m for m in REG["models"]}


def test_default_is_do_not_use() -> None:
    assert REG["default"] == "do_not_use"
    assert REG["policy_adr"] == "ADR-0003"


def test_every_entry_answers_the_six_questions() -> None:
    for m in REG["models"]:
        for key in SIX:
            assert key in m and m[key] not in (None, ""), (m["repo_id"], key)
        assert len(m["revision"]) == 40, m["repo_id"]
        assert m["status"] in {"used", "superseded", "rejected"}, m["repo_id"]
        assert m["track"] == "B", "open weights stay in Track B unless an ADR moves them"
        assert m["affects_final_product"] is False, "affecting the product requires an owner ADR"


def test_no_duplicate_entries() -> None:
    keys = [(m["repo_id"], m["revision"]) for m in REG["models"]]
    assert len(keys) == len(set(keys))


def test_every_reported_model_is_registered() -> None:
    reg = entries()
    for p in sorted((ROOT / "eval" / "reports").glob("*.json")):
        L = json.loads(p.read_text(encoding="utf-8"))["lineage"]
        if L["model"] in PSEUDO:
            continue
        key = (L["model"], L["model_revision"])
        assert key in reg, f"{p.name}: {key} is not justified in configs/model_registry.yaml"
        assert reg[key]["status"] in {"used", "superseded"}, p.name


def test_superseded_reports_are_marked_in_the_reports_readme() -> None:
    readme = (ROOT / "eval" / "reports" / "README.md").read_text(encoding="utf-8")
    reg = entries()
    for p in sorted((ROOT / "eval" / "reports").glob("*.json")):
        L = json.loads(p.read_text(encoding="utf-8"))["lineage"]
        if reg.get((L["model"], L["model_revision"]), {}).get("status") == "superseded":
            assert f"`{p.name}`" in readme and "SUPERSEDED" in readme, p.name
