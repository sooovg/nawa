"""Foundation checks for the NAWA repository (ROADMAP P0-05, AGENTS.md §2.6, §4, §11)."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 5 * 1024 * 1024  # AGENTS.md §4: no file larger than 5MB in Git

REQUIRED_FILES = [
    "AGENTS.md",
    "ROADMAP.md",
    "README.md",
    "PROJECT_CHARTER.md",
    "ARCHITECTURE.md",
    "SUCCESS_CRITERIA.md",
    "SECURITY.md",
    "CONTRIBUTING.md",
    "LICENSE",
    "pyproject.toml",
    "Makefile",
    ".gitignore",
    ".pre-commit-config.yaml",
    "configs/hf_repos.yaml",
]
REQUIRED_DIRS = [
    "configs", "src", "training", "eval", "tests",
    "scripts", "docs", "experiments", "data_pipeline",
]
FORBIDDEN_SUFFIXES = {
    ".safetensors", ".bin", ".pt", ".pth", ".ckpt", ".gguf",
    ".parquet", ".sqlite", ".db", ".onnx", ".h5",
}
ALLOWED_JSONL = {"experiments/log.jsonl"}
REQUIRED_GITIGNORE = [
    ".env", "*.safetensors", "*.bin", "*.pt", "*.pth", "*.ckpt",
    "*.gguf", "*.parquet", "*.jsonl", "checkpoints/", "data/raw/",
]
# Known credential formats. Patterns only — never real values.
SECRET_PATTERNS = {
    "github_classic": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
    "github_fine_grained": re.compile(r"\bgithub_pat_[A-Za-z0-9_]{50,}\b"),
    "huggingface": re.compile(r"\bhf_[A-Za-z0-9]{30,}\b"),
    "aws_access_key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "private_key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "openai": re.compile(r"\bsk-[A-Za-z0-9_-]{32,}\b"),
}


def tracked_files() -> list[Path]:
    """Files git would commit (tracked + untracked-not-ignored)."""
    try:
        out = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            cwd=ROOT, check=True, capture_output=True,
        ).stdout.decode()
        return [ROOT / p for p in out.split("\0") if p and (ROOT / p).is_file()]
    except (FileNotFoundError, subprocess.CalledProcessError):
        return [p for p in ROOT.rglob("*") if p.is_file() and ".git" not in p.parts]


@pytest.mark.parametrize("rel", REQUIRED_FILES)
def test_required_file_exists(rel: str) -> None:
    path = ROOT / rel
    assert path.is_file(), f"missing required file: {rel}"
    assert path.stat().st_size > 0, f"required file is empty: {rel}"


@pytest.mark.parametrize("rel", REQUIRED_DIRS)
def test_required_dir_exists(rel: str) -> None:
    assert (ROOT / rel).is_dir(), f"missing required directory: {rel}/"


def test_governance_files_are_at_root_with_canonical_names() -> None:
    assert (ROOT / "AGENTS.md").read_text(encoding="utf-8").startswith("# NAWA — AGENTS.md")
    assert (ROOT / "ROADMAP.md").read_text(encoding="utf-8").startswith("# NAWA — ROADMAP.md")
    # No duplicate copies under legacy names (AGENTS.md §2.1: no parallel versions).
    for legacy in ("NAWA-AGENTS.md", "NAWA-ROADMAP.md", "STATUS.md"):
        assert not (ROOT / legacy).exists(), f"unexpected duplicate/parallel file: {legacy}"


def test_no_large_files() -> None:
    big = [str(p.relative_to(ROOT)) for p in tracked_files() if p.stat().st_size > MAX_BYTES]
    assert not big, f"files over 5MB must go to Hugging Face, not Git: {big}"


def test_no_weight_or_dataset_files() -> None:
    bad = []
    for p in tracked_files():
        rel = p.relative_to(ROOT).as_posix()
        if p.suffix in FORBIDDEN_SUFFIXES or (p.suffix == ".jsonl" and rel not in ALLOWED_JSONL):
            bad.append(rel)
    assert not bad, f"weights/datasets must not be committed to Git: {bad}"


def test_no_env_files_committed() -> None:
    bad = [p.name for p in tracked_files() if p.name == ".env" or (p.name.startswith(".env.") and p.name != ".env.example")]
    assert not bad, f".env files must never be committed: {bad}"


def test_no_secrets_in_tracked_files() -> None:
    hits = []
    for p in tracked_files():
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for name, pat in SECRET_PATTERNS.items():
            if pat.search(text):
                hits.append(f"{p.relative_to(ROOT)}: {name}")
    assert not hits, f"possible secrets found: {hits}"


def test_gitignore_blocks_artifacts_and_secrets() -> None:
    lines = {l.strip() for l in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()}
    missing = [pat for pat in REQUIRED_GITIGNORE if pat not in lines]
    assert not missing, f".gitignore is missing: {missing}"


def test_roadmap_has_status_sections() -> None:
    text = (ROOT / "ROADMAP.md").read_text(encoding="utf-8")
    for heading in ("## 2.1 حالة البوابات", "## 2.2 سجل المهام", "# 12. سجل التغييرات"):
        assert heading in text, f"ROADMAP.md missing section: {heading}"
