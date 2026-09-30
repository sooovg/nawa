"""Failure Atlas (AGENTS.md §9, ROADMAP P1-08): schema, validation, and ingestion from evaluation runs.

Every record carries the AGENTS.md §9 fields plus provenance. A record is `verified` only when its
`verified_truth` was checked by an independent deterministic method: the suite's reference answer
(`oracle`) is re-scored by the same scorer and must be correct, and the bad output must score as wrong.

Records derived from evaluation items are NEVER training-eligible (`train_eligible: false`): training on
them would leak the evaluation set (G1: no train/eval leakage; G2: zero known leakage into frozen).
Their `content_hash` lets the data pipeline (P2-05) exclude them. The frozen split is refused outright:
its items are private (P1-03) and must not be copied into Git.

    python -m nawa.atlas ingest --run eval/runs/<run_id> --out data_pipeline/atlas/incoming/<name>.jsonl
    python -m nawa.atlas validate data_pipeline/atlas/incoming/*.jsonl
    python -m nawa.atlas digest data_pipeline/atlas/incoming/*.jsonl

Records are data, so they are NOT committed to Git (tests/test_repository_structure.py; data lives on HF). Git pins
each batch in data_pipeline/atlas/manifest.yaml by a content digest over the deterministic fields, and CI
re-creates the batch from a fresh run and checks the digest. Upload to the private HF repo `nawa-data` is P2-08
(after data rights, OD-03).
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from nawa.evaluation import suites
from nawa.evaluation.taxonomy import load_taxonomy

REPO = Path(__file__).resolve().parents[2]
INCOMING = REPO / "data_pipeline" / "atlas" / "incoming"

REQUIRED = ("id", "category", "prompt", "bad_output", "model", "model_revision", "verified_truth",
            "verification_method", "source", "license", "reviewer", "status")
PROVENANCE = ("secondary_categories", "run_id", "split", "suite", "item_id", "content_hash", "git_commit",
              "train_eligible", "train_block_reason", "created_utc", "scorer_default_category")
STATUSES = ("unverified", "verified", "rejected")
EVAL_DERIVED_BLOCK = "derived from an evaluation item: training on it would leak the evaluation set (G1/G2)"


class AtlasError(ValueError):
    """An Atlas record breaks AGENTS.md §9 or the P1-08 rules."""


def record_id(model: str, item_id: str, bad_output: str) -> str:
    h = hashlib.sha256(f"{model}\x00{item_id}\x00{bad_output}".encode("utf-8")).hexdigest()
    return f"ATL-{h[:12]}"


def validate_record(r: dict[str, Any]) -> None:
    missing = [k for k in REQUIRED + PROVENANCE if k not in r]
    if missing:
        raise AtlasError(f"{r.get('id')}: missing {missing}")
    tax = load_taxonomy()
    if r["category"] not in tax:
        raise AtlasError(f"{r['id']}: category {r['category']!r} not in docs/failure_taxonomy.md")
    bad = [c for c in r["secondary_categories"] if c not in tax or c == r["category"]]
    if bad:
        raise AtlasError(f"{r['id']}: bad secondary categories {bad}")
    if r["status"] not in STATUSES:
        raise AtlasError(f"{r['id']}: status {r['status']!r}")
    if r["split"] == "frozen":
        raise AtlasError(f"{r['id']}: frozen items are private and never enter the Atlas in Git (P1-03)")
    if r["status"] == "verified" and not (r["verified_truth"] and r["verification_method"]):
        raise AtlasError(f"{r['id']}: verified needs verified_truth and verification_method")
    if r["train_eligible"] and r["status"] != "verified":
        raise AtlasError(f"{r['id']}: unverified examples never enter training (AGENTS.md §9)")
    if r["split"] in ("dev", "calib") and (r["train_eligible"] or not r["train_block_reason"]):
        raise AtlasError(f"{r['id']}: eval-derived records must be train_eligible=false with a reason")
    if r["id"] != record_id(r["model"], r["item_id"], r["bad_output"]):
        raise AtlasError(f"{r['id']}: id does not match its content")


def _prompt_text(messages: list[dict[str, str]]) -> str:
    return "\n\n".join(f"[{m['role']}]\n{m['content']}" for m in messages)


def records_from_run(run_dir: Path, created_utc: str) -> list[dict[str, Any]]:
    """Turn every failed item of an evaluation run into an Atlas record, verified by re-scoring the gold."""
    from nawa.evaluation.runner import build_public
    lineage = json.loads((run_dir / "lineage.json").read_text(encoding="utf-8"))
    split = lineage["split"]
    if split == "frozen":
        raise AtlasError("refusing to ingest a frozen run into the Atlas (private items, P1-03)")
    if lineage.get("limit"):
        raise AtlasError("refusing a --limit smoke run: the Atlas takes complete runs only")
    items = {it.id: it for its in build_public()[split].values() for it in its}
    out = []
    with (run_dir / "predictions.jsonl").open(encoding="utf-8") as fh:
        preds = [json.loads(line) for line in fh]
    for p in preds:
        if p["score"]["correct"]:
            continue
        it = items[p["id"]]
        mod = suites.get(p["suite"])
        truth = mod.oracle(it)
        truth_ok = mod.score(it, truth)["correct"]
        bad_is_wrong = not mod.score(it, p["output"])["correct"]
        verified = truth_ok and bad_is_wrong
        cat = p["score"]["failure"]
        if cat is None:  # do not invent a category (docs/failure_taxonomy.md rule 2)
            raise AtlasError(f"{it.id}: failed item without a taxonomy id; add one to the scorer first")
        default = p["score"].get("failure_suite_default")
        rec = {
            "id": record_id(lineage["model"], it.id, p["output"]),
            "category": cat,
            "prompt": _prompt_text(it.messages),
            "bad_output": p["output"],
            "model": lineage["model"],
            "model_revision": lineage.get("model_revision") or f"git:{lineage['git']['commit'][:12]}",
            "verified_truth": truth if verified else None,
            "verification_method": (f"deterministic: suites.{p['suite']}.score re-scores the reference answer "
                                    f"(oracle) as correct and the bad output as wrong") if verified else None,
            "source": f"eval/{split}/{it.id} (NAWA-authored synthetic suite, P1-02)",
            "license": it.meta.get("license"),
            "reviewer": "automated:deterministic-scorer (no human review yet)",
            "status": "verified" if verified else "unverified",
            "secondary_categories": [],
            # The suite scorer's own default before abstention attribution. Traceability only: an abstention on
            # a math item is NOT also a calculation error, so this is not a secondary category.
            "scorer_default_category": default,
            "run_id": lineage["run_id"],
            "split": split,
            "suite": p["suite"],
            "item_id": it.id,
            "content_hash": it.content_hash(),
            "git_commit": lineage["git"]["commit"],
            "train_eligible": False,
            "train_block_reason": EVAL_DERIVED_BLOCK,
            "created_utc": created_utc,
        }
        validate_record(rec)
        out.append(rec)
    return out


DIGEST_FIELDS = ("id", "category", "status", "verified_truth", "bad_output", "suite", "item_id", "content_hash",
                 "model", "split", "train_eligible")


def digest(recs: list[dict[str, Any]]) -> str:
    """Content digest over the fields that do not depend on when or at which commit the run happened."""
    h = hashlib.sha256()
    for r in sorted(recs, key=lambda x: x["id"]):
        h.update(json.dumps({k: r[k] for k in DIGEST_FIELDS}, ensure_ascii=False, sort_keys=True).encode("utf-8") + b"\n")
    return h.hexdigest()


def read(paths: Iterable[Path]) -> list[dict[str, Any]]:
    recs = []
    for path in paths:
        with Path(path).open(encoding="utf-8") as fh:
            recs += [json.loads(line) for line in fh if line.strip()]
    return recs


def validate_all(recs: list[dict[str, Any]]) -> None:
    seen = set()
    for r in recs:
        validate_record(r)
        if r["id"] in seen:
            raise AtlasError(f"duplicate record {r['id']}")
        seen.add(r["id"])


def main() -> None:
    ap = argparse.ArgumentParser(prog="python -m nawa.atlas")
    sub = ap.add_subparsers(dest="cmd", required=True)
    ing = sub.add_parser("ingest")
    ing.add_argument("--run", type=Path, required=True)
    ing.add_argument("--out", type=Path, required=True)
    ing.add_argument("--created-utc", required=True)
    val = sub.add_parser("validate")
    val.add_argument("paths", type=Path, nargs="+")
    dig = sub.add_parser("digest")
    dig.add_argument("paths", type=Path, nargs="+")
    a = ap.parse_args()
    if a.cmd == "ingest":
        recs = records_from_run(a.run, a.created_utc)
        if a.out.exists():
            raise SystemExit(f"{a.out} exists; the Atlas is append-only by new files, never overwritten")
        a.out.parent.mkdir(parents=True, exist_ok=True)
        with a.out.open("w", encoding="utf-8") as fh:
            for r in recs:
                fh.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
        ver = sum(r["status"] == "verified" for r in recs)
        print(f"{len(recs)} records ({ver} verified) -> {a.out}\ndigest {digest(recs)}")
    elif a.cmd == "digest":
        print(digest(read(a.paths)))
    else:
        recs = read(a.paths)
        validate_all(recs)
        print(f"{len(recs)} records valid")


if __name__ == "__main__":
    main()
