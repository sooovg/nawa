"""Frozen evaluation split (P1-03). Only the Eval role may build, read, or verify it.

- Built from a SECRET random seed that is used once and never stored, plus a private factual bank.
  Git therefore holds no means to regenerate frozen: the artifact itself, pinned by hash, is the reference.
- Excludes every dev/calib item (content_hash).
- Written outside the repository and uploaded only to the private HF repo `vuuuv/nawa-eval`.
- Git keeps `eval/FROZEN.sha256` (file digests) and `eval/frozen_item_hashes.txt` (per-item content
  hashes, used for leakage and decontamination checks, and revealing nothing about content).

    NAWA_ROLE=eval python -m nawa.evaluation.frozen build  --bank <private.yaml> --out <dir outside repo>
    NAWA_ROLE=eval python -m nawa.evaluation.frozen verify --dir <dir>
"""

from __future__ import annotations

import argparse
import hashlib
import os
import secrets
import sys
from pathlib import Path

import yaml

from nawa.evaluation.build import build_public, build_split, hashes, read_split, write_split

REPO = Path(__file__).resolve().parents[3]
FROZEN_SHA = REPO / "eval" / "FROZEN.sha256"
ITEM_HASHES = REPO / "eval" / "frozen_item_hashes.txt"
FROZEN_VERSION = "v1"


class RoleError(PermissionError):
    pass


def require_eval_role() -> None:
    if os.environ.get("NAWA_ROLE") != "eval":
        raise RoleError("frozen split is restricted to the Eval role (set NAWA_ROLE=eval); AGENTS.md §10")


def _inside_repo(p: Path) -> bool:
    try:
        p.resolve().relative_to(REPO)
        return True
    except ValueError:
        return False


def build(bank_path: Path, out_dir: Path) -> dict[str, str]:
    require_eval_role()
    if _inside_repo(out_dir):
        raise ValueError("frozen output must be outside the Git repository")
    bank = yaml.safe_load(Path(bank_path).read_text(encoding="utf-8"))["items"]
    public = build_public()
    exclude = hashes(public["dev"]) | hashes(public["calib"])
    seed = secrets.token_hex(32)  # used once, never written anywhere
    items = build_split("frozen", seed, factual_bank=bank, exclude=exclude)
    del seed
    digests = write_split(items, out_dir / "frozen")
    FROZEN_SHA.write_text(
        f"# NAWA frozen eval {FROZEN_VERSION} — sha256 of files in HF vuuuv/nawa-eval (private), path frozen/{FROZEN_VERSION}/\n"
        + "".join(f"{v}  frozen/{FROZEN_VERSION}/{k}\n" for k, v in sorted(digests.items())), encoding="utf-8")
    ITEM_HASHES.write_text("".join(f"{h}\n" for h in sorted(hashes(items))), encoding="utf-8")
    return digests


def expected_digests() -> dict[str, str]:
    out = {}
    for line in FROZEN_SHA.read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#"):
            digest, path = line.split("  ", 1)
            out[Path(path).name] = digest
    return out


def verify(split_dir: Path) -> None:
    require_eval_role()
    exp = expected_digests()
    got = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path(split_dir).glob("*.jsonl"))}
    if got != exp:
        raise ValueError(f"frozen digests mismatch: {sorted(set(got.items()) ^ set(exp.items()))}")
    items = read_split(Path(split_dir))
    if hashes(items) != set(ITEM_HASHES.read_text(encoding="utf-8").split()):
        raise ValueError("frozen item hashes mismatch")


def load(split_dir: Path):
    """Verified read for the Eval role."""
    verify(split_dir)
    return read_split(Path(split_dir))


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build"); b.add_argument("--bank", required=True); b.add_argument("--out", required=True)
    v = sub.add_parser("verify"); v.add_argument("--dir", required=True)
    a = ap.parse_args()
    try:
        if a.cmd == "build":
            for k, d in sorted(build(Path(a.bank), Path(a.out)).items()):
                print(d, k)
        else:
            verify(Path(a.dir)); print("frozen OK")
    except RoleError as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main()
