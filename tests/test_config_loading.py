"""Config loading checks (ROADMAP P0-06)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from nawa.config import HF_REPO_KEYS, ConfigError, load_hf_repos, load_yaml

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_TYPES = {
    "data": "dataset", "eval": "dataset", "core": "model", "practical_baseline": "model",
    "verifier": "model", "gguf": "model", "adapters": "model", "demo": "space",
}


def test_all_yaml_configs_parse() -> None:
    files = sorted((ROOT / "configs").glob("*.yaml"))
    assert files, "configs/ has no yaml files"
    for f in files:
        assert isinstance(yaml.safe_load(f.read_text(encoding="utf-8")), dict), f


def test_hf_repos_loads_and_is_complete() -> None:
    cfg = load_hf_repos()
    owner = cfg["owner"]
    assert set(cfg["repos"]) == set(HF_REPO_KEYS)
    for key in HF_REPO_KEYS:
        assert cfg["repos"][key] == f"{owner}/nawa-{key.replace('_', '-')}"
        assert cfg["repo_types"][key] == EXPECTED_TYPES[key]


def test_hf_policy_keeps_everything_private() -> None:
    policy = load_hf_repos()["policy"]
    assert policy["all_private_until_release_gate"] is True
    assert policy["public_release_requires_owner_approval"] is True
    assert policy.get("default_upload_revision") == "dev"


def test_hf_repos_has_no_credential_keys() -> None:
    """No key anywhere in the parsed config may look like a credential."""
    forbidden = ("token", "password", "secret", "api_key")

    def walk(node: object) -> list[str]:
        found: list[str] = []
        if isinstance(node, dict):
            for k, v in node.items():
                if any(f in str(k).lower() for f in forbidden):
                    found.append(str(k))
                found += walk(v)
        elif isinstance(node, list):
            for item in node:
                found += walk(item)
        return found

    assert walk(load_hf_repos()) == []


def test_loader_rejects_invalid_config(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("owner: x\nrepos: {data: 'someone-else/data'}\npolicy: {}\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_hf_repos(bad)
    with pytest.raises(ConfigError):
        load_yaml(tmp_path / "missing.yaml")
