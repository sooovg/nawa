"""Budget guard (ROADMAP P0-07a). Denies GPU or paid work until the owner sets caps."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from nawa.config import CONFIG_DIR, ConfigError, load_yaml

WORK_KINDS = {"cpu_local", "gpu", "paid_service"}


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str


def load_budget(path: str | Path = CONFIG_DIR / "budget.yaml") -> dict[str, Any]:
    cfg = load_yaml(path)
    for key in ("caps", "spent", "stop_at_fraction"):
        if key not in cfg:
            raise ConfigError(f"budget.yaml: missing '{key}'")
    frac = cfg["stop_at_fraction"]
    if not isinstance(frac, (int, float)) or not 0 < frac <= 0.8:
        raise ConfigError("budget.yaml: stop_at_fraction must be in (0, 0.8] (AGENTS.md §13)")
    return cfg


def check(kind: str, gpu_hours: float = 0.0, money_usd: float = 0.0, cfg: dict[str, Any] | None = None) -> Decision:
    """Return whether a unit of work may run under the current budget."""
    if kind not in WORK_KINDS:
        raise ValueError(f"unknown work kind {kind!r}; expected one of {sorted(WORK_KINDS)}")
    cfg = cfg or load_budget()
    if kind == "cpu_local" and gpu_hours == 0 and money_usd == 0:
        return Decision(True, "zero-cost local CPU work")
    caps, spent, frac = cfg["caps"], cfg["spent"], cfg["stop_at_fraction"]
    for name, req in (("gpu_hours", gpu_hours), ("money_usd", money_usd)):
        needs = req > 0 or (name == "gpu_hours" and kind == "gpu") or (name == "money_usd" and kind == "paid_service")
        if not needs:
            continue
        cap = caps.get(name)
        if cap is None:
            return Decision(False, f"{name} cap not set by owner (OD-05)")
        if float(spent.get(name, 0.0)) + req > frac * float(cap):
            return Decision(False, f"{name} would exceed {int(frac * 100)}% of cap; owner approval required")
    return Decision(True, "within budget")
