"""Load and validate eval/targets.yaml (P1-06: target definitions; ADR-0004).

A target is *defined* when its metric, evaluation source, direction, threshold kind, and reference type are fixed.
Numbers that need the first text-trained NAWA core stay null until P1-06a. This module refuses a file that
drifts from those rules, so later agents cannot silently change a definition.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

REPO = Path(__file__).resolve().parents[3]
TARGETS = REPO / "eval" / "targets.yaml"

TARGET_IDS = ("T1", "T2", "T3", "T4", "T5", "T6")
REQUIRED_FIELDS = ("description", "metric", "direction", "threshold_kind", "reference", "anchor", "status")
STATUSES = {"DEFINED", "DEFINED_PARTIAL", "OPTIONAL", "ANCHORED"}
FILE_STATUSES = ("provisional", "definitions_fixed", "anchored")
GATE_REFERENCE_TYPES = {"model_only_core", "previous_release", "absolute", "hardware_target"}

# ROADMAP §1.3 numbers. They may only be raised (T1/T2 recall) or tightened (drops/memory), never loosened.
FLOORS = {
    ("T1", "min_relative_reduction"): (0.50, "min"),
    ("T2", "min_abstention_recall"): (0.80, "min"),
    ("T2", "max_answerable_relative_drop"): (0.05, "max"),
    ("T4", "max_memory_gb"): (3.0, "max"),
    ("T5", "max_relative_drop"): (0.03, "max"),
}


class TargetsError(ValueError):
    """eval/targets.yaml breaks a P1-06 definition rule."""


def load_targets(path: str | Path = TARGETS) -> dict[str, Any]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    validate(data)
    return data


def validate(data: dict[str, Any]) -> None:
    if data.get("status") not in FILE_STATUSES:
        raise TargetsError(f"status must be one of {FILE_STATUSES}")
    src = data.get("evaluation_source") or {}
    splits = src.get("splits") or {}
    if splits.get("calibrate") != "calib" or splits.get("gate") != "frozen" or splits.get("develop") != "dev":
        raise TargetsError("evaluation_source.splits must be develop=dev, calibrate=calib, gate=frozen")
    refs = data.get("reference_types") or {}
    targets = data.get("targets") or {}
    if tuple(targets) != TARGET_IDS:
        raise TargetsError(f"targets must be exactly {TARGET_IDS} in order")
    for tid, t in targets.items():
        missing = [f for f in REQUIRED_FIELDS if f not in t]
        if missing:
            raise TargetsError(f"{tid}: missing {missing}")
        if t["status"] not in STATUSES:
            raise TargetsError(f"{tid}: status {t['status']!r} not in {sorted(STATUSES)}")
        if t["reference"] not in refs:
            raise TargetsError(f"{tid}: reference {t['reference']!r} is not a declared reference type")
        if t["status"] != "OPTIONAL" and t["reference"] not in GATE_REFERENCE_TYPES:
            raise TargetsError(f"{tid}: a gate target must use an internal or absolute reference (ADR-0003)")
        if "suites" not in t and "evaluation_source_override" not in t:
            raise TargetsError(f"{tid}: needs suites or an evaluation_source_override")
        if data["status"] != "anchored" and t["anchor"] is not None:
            raise TargetsError(f"{tid}: anchor must stay null until P1-06a")
    for (tid, key), (floor, kind) in FLOORS.items():
        v = targets[tid].get(key)
        if not isinstance(v, (int, float)):
            raise TargetsError(f"{tid}.{key} must be a number")
        if (kind == "min" and v < floor) or (kind == "max" and v > floor):
            raise TargetsError(f"{tid}.{key}={v} loosens the ROADMAP §1.3 value {floor}; targets may only be tightened")
    if targets["T1"].get("guard") != "T2_answerable":
        raise TargetsError("T1 must carry guard T2_answerable (ADR-0004 D3: always-abstain must not pass T1)")
    if targets["T3"]["status"] != "OPTIONAL":
        raise TargetsError("T3 must stay OPTIONAL (ADR-0003)")
