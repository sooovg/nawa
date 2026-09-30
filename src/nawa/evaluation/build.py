"""Build evaluation splits deterministically (P1-02 dev/calib; P1-03 frozen).

    python -m nawa.evaluation.build --split dev --out eval/build
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path

from nawa.evaluation import suites
from nawa.evaluation.schema import SUITES, Item

# Public seeds: dev/calib are reproducible by anyone from Git. Frozen NEVER uses a public seed (P1-03).
SEEDS = {"dev": 1001, "calib": 2002}
SIZES = {  # n passed to generate(); abstention n = twin pairs (2 items each)
    "dev":    {"faithfulness": 30, "abstention": 15, "factual": 30, "reasoning_math": 30, "code": 20,
               "tool_use": 24, "robustness": 24, "arabic": 30, "regression_general": 25},
    "calib":  {"faithfulness": 15, "abstention": 8, "factual": 15, "reasoning_math": 15, "code": 10,
               "tool_use": 12, "robustness": 12, "arabic": 18, "regression_general": 15},
    "frozen": {"faithfulness": 30, "abstention": 15, "factual": 30, "reasoning_math": 30, "code": 20,
               "tool_use": 24, "robustness": 24, "arabic": 30, "regression_general": 25},
}


def _select(name: str, items: list[Item], n: int, exclude: set[str]) -> list[Item]:
    """Drop excluded/duplicate items, keep twin pairs together and tool labels balanced, take n units."""
    seen: set[str] = set()
    if name == "abstention":
        groups: dict[str, list[Item]] = {}
        for it in items:
            groups.setdefault(it.meta["twin_id"], []).append(it)
        out = []
        for g in groups.values():
            hs = {i.content_hash() for i in g}
            if hs & (exclude | seen):
                continue
            seen |= hs
            out.extend(g)
            if len(out) == 2 * n:
                return out
        raise ValueError(f"{name}: not enough unique twin pairs")
    cap = n // 4 if name == "tool_use" else None
    per_label: dict[str, int] = {}
    out = []
    for it in items:
        h = it.content_hash()
        if h in exclude or h in seen:
            continue
        if cap is not None:
            lab = it.gold["label"]
            if per_label.get(lab, 0) >= cap:
                continue
            per_label[lab] = per_label.get(lab, 0) + 1
        seen.add(h)
        out.append(it)
        if len(out) == n:
            return out
    raise ValueError(f"{name}: only {len(out)} unique items, need {n}")


def build_split(split: str, seed: int | str, factual_bank: list[dict] | None = None,
                exclude: set[str] | None = None) -> dict[str, list[Item]]:
    """Build one split. `exclude` holds content hashes of earlier splits (calib excludes dev; frozen excludes both)."""
    exclude = exclude or set()
    out: dict[str, list[Item]] = {}
    for name in SUITES:
        rng = random.Random(f"{seed}:{name}")
        mod = suites.get(name)
        n = SIZES[split][name]
        if name == "factual":
            out[name] = _select(name, mod.generate(rng, n, split, bank=factual_bank), n, exclude)
        else:
            out[name] = _select(name, mod.generate(rng, n * 3, split), n, exclude)
    return out


def hashes(items: dict[str, list[Item]]) -> set[str]:
    return {i.content_hash() for its in items.values() for i in its}


def build_public() -> dict[str, dict[str, list[Item]]]:
    """dev then calib (calib excludes dev). Deterministic from public seeds."""
    dev = build_split("dev", SEEDS["dev"])
    calib = build_split("calib", SEEDS["calib"], exclude=hashes(dev))
    return {"dev": dev, "calib": calib}


def write_split(items: dict[str, list[Item]], out_dir: Path) -> dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    digests = {}
    for name, its in items.items():
        path = out_dir / f"{name}.jsonl"
        data = "".join(it.to_json() + "\n" for it in its).encode("utf-8")
        path.write_bytes(data)
        digests[f"{name}.jsonl"] = hashlib.sha256(data).hexdigest()
    return digests


def read_split(split_dir: Path) -> dict[str, list[Item]]:
    out = {}
    for path in sorted(split_dir.glob("*.jsonl")):
        out[path.stem] = [Item.from_dict(json.loads(l)) for l in path.read_text(encoding="utf-8").splitlines() if l]
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=sorted(SEEDS), required=True)
    ap.add_argument("--out", default="eval/build")
    a = ap.parse_args()
    items = build_public()[a.split]
    digests = write_split(items, Path(a.out) / a.split)
    for k, v in sorted(digests.items()):
        print(f"{v}  {a.split}/{k}  ({len(items[k.removesuffix('.jsonl')])} items)")


if __name__ == "__main__":
    main()
