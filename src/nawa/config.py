"""Minimal, dependency-light config loading for NAWA (bootstrap)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "configs"

HF_REPO_KEYS = (
    "data",
    "eval",
    "core",
    "practical_baseline",
    "verifier",
    "gguf",
    "adapters",
    "demo",
)
HF_REPO_TYPES = {"model", "dataset", "space"}


class ConfigError(ValueError):
    """Raised when a config file is missing or structurally invalid."""


def load_yaml(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.is_absolute():
        p = REPO_ROOT / p
    if not p.is_file():
        raise ConfigError(f"config not found: {p}")
    with p.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ConfigError(f"config must be a mapping: {p}")
    return data


def load_hf_repos(path: str | Path = CONFIG_DIR / "hf_repos.yaml") -> dict[str, Any]:
    """Load and validate configs/hf_repos.yaml."""
    cfg = load_yaml(path)
    owner = cfg.get("owner")
    if not isinstance(owner, str) or not owner:
        raise ConfigError("hf_repos.yaml: 'owner' must be a non-empty string")
    repos = cfg.get("repos") or {}
    types = cfg.get("repo_types") or {}
    missing = [k for k in HF_REPO_KEYS if k not in repos]
    if missing:
        raise ConfigError(f"hf_repos.yaml: missing repos {missing}")
    for key in HF_REPO_KEYS:
        repo_id = repos[key]
        if not isinstance(repo_id, str) or not repo_id.startswith(f"{owner}/nawa-"):
            raise ConfigError(f"hf_repos.yaml: repos.{key}={repo_id!r} must be '{owner}/nawa-*'")
        if types.get(key) not in HF_REPO_TYPES:
            raise ConfigError(f"hf_repos.yaml: repo_types.{key} must be one of {sorted(HF_REPO_TYPES)}")
    policy = cfg.get("policy") or {}
    if policy.get("all_private_until_release_gate") is not True:
        raise ConfigError("hf_repos.yaml: policy.all_private_until_release_gate must be true")
    if policy.get("public_release_requires_owner_approval") is not True:
        raise ConfigError("hf_repos.yaml: policy.public_release_requires_owner_approval must be true")
    return cfg
