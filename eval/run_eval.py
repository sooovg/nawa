#!/usr/bin/env python
"""Run the NAWA evaluation (P1-07). Examples:

    python eval/run_eval.py --model oracle --split dev
    python eval/run_eval.py --model hf:<local snapshot dir> --split dev --latency --save-report
    NAWA_ROLE=eval python eval/run_eval.py --model hf:<dir> --split frozen --frozen-dir <private dir> --save-report

--save-report copies the aggregate report (no item text) to eval/reports/ and appends to experiments/log.jsonl.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from nawa.evaluation.report import render_markdown
from nawa.evaluation.runner import DTYPES, REPO, make_backend, run
from nawa.evaluation.schema import SUITES


def append_experiment(report: dict, task_id: str, conclusion: str) -> str:
    log = REPO / "experiments" / "log.jsonl"
    n = sum(1 for l in log.read_text(encoding="utf-8").splitlines() if l.strip()) if log.exists() else 0
    L = report["lineage"]
    entry = {"experiment_id": f"EXP-{n + 1:04d}", "task_id": task_id, "track": "B", "git_commit": L["git"]["commit"],
             "data_revision": f"eval/{L['split']}", "data_sha256": L["split_sha256"], "config_hash": L["config_hash"],
             "seed": None, "hardware": L["hardware"], "software": {"python": L["python"], **{k: v for k, v in L["backend_info"].items() if k in ("torch", "transformers")}},
             "model": L["model"], "model_revision": L["model_revision"], "run_id": report["run_id"],
             "metrics": {"summary": report["summary"], "targets": report["targets"]},
             "failure_cases": [], "artifact": f"eval/reports/{report['run_id']}.json", "conclusion": conclusion,
             "next_action": "P1-06 fix targets from dev baselines"}
    with log.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry["experiment_id"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="oracle | always_abstain | hf:<local model dir>")
    ap.add_argument("--split", choices=["dev", "calib", "frozen"], default="dev")
    ap.add_argument("--suites", default="all", help="comma-separated suite names or 'all'")
    ap.add_argument("--frozen-dir", type=Path)
    ap.add_argument("--batch-size", type=int, default=8)
    ap.add_argument("--threads", type=int)
    ap.add_argument("--dtype", choices=DTYPES, default="float32", help="hf backend weights dtype (recorded in lineage)")
    ap.add_argument("--limit", type=int, help="first N items per suite (smoke tests only; never for reported numbers)")
    ap.add_argument("--latency", action="store_true", help="add a batch=1 latency probe (T4 evidence)")
    ap.add_argument("--save-report", action="store_true")
    ap.add_argument("--task-id", default="P1-04")
    ap.add_argument("--conclusion", default="baseline measurement")
    a = ap.parse_args()
    names = list(SUITES) if a.suites == "all" else a.suites.split(",")
    if a.save_report and a.limit:
        sys.exit("refusing --save-report with --limit: reported numbers must use the full split")
    backend = make_backend(a.model, batch_size=a.batch_size, threads=a.threads, dtype=a.dtype)
    out_dir, report = run(backend, a.split, names, frozen_dir=a.frozen_dir, latency=a.latency, limit=a.limit)
    print(render_markdown(report))
    print(f"run dir: {out_dir}")
    if a.save_report:
        dest = REPO / "eval" / "reports" / f"{report['run_id']}.json"
        dest.parent.mkdir(exist_ok=True)
        shutil.copy(out_dir / "report.json", dest)
        print("saved", dest.relative_to(REPO), append_experiment(report, a.task_id, a.conclusion))


if __name__ == "__main__":
    main()
