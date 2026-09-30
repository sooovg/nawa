"""Aggregate per-item scores into suite metrics with 95% Wilson intervals (P1-07).

Reports contain aggregates only. They never include item text, so a frozen-split report may be
committed to Git while the frozen content stays private.
"""

from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[3]
TARGETS = REPO / "eval" / "targets.yaml"


def wilson(k: int, n: int, z: float = 1.96) -> list[float] | None:
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(max(0.0, c - h), 4), round(min(1.0, c + h), 4)]


def rate(flags: list[bool]) -> dict:
    k, n = sum(flags), len(flags)
    return {"value": round(k / n, 4) if n else None, "k": k, "n": n, "ci95": wilson(k, n)}


def build_report(records: list[dict], lineage: dict) -> dict:
    by_suite: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        by_suite[r["suite"]].append(r)
    suites_out = {}
    for name, rs in by_suite.items():
        s = [r["score"] for r in rs]
        m = {"accuracy": rate([x["correct"] for x in s])}
        if name in ("faithfulness", "factual"):
            m["hallucination_rate"] = rate([x["hallucinated"] for x in s])
            m["abstention_rate"] = rate([x["abstained"] for x in s])
        if name == "faithfulness":
            m["citation_accuracy"] = rate([bool(x.get("citation_correct")) for x in s])
        if name == "abstention":
            un = [r["score"] for r in rs if r["answerable"] is False]
            an = [r["score"] for r in rs if r["answerable"] is True]
            m["abstention_recall"] = rate([x["correct"] for x in un])
            m["hallucination_rate_unanswerable"] = rate([x["hallucinated"] for x in un])
            m["answerable_accuracy"] = rate([x["correct"] for x in an])
        for key in ("register", "kind"):
            groups = defaultdict(list)
            for r in rs:
                if key in r["meta"]:
                    groups[r["meta"][key]].append(r["score"]["correct"])
            if len(groups) > 1:
                m[f"accuracy_by_{key}"] = {g: rate(v) for g, v in sorted(groups.items())}
        m["failures"] = dict(sorted(Counter(x["failure"] for x in s if x["failure"]).items()))
        trunc = [r["gen"].get("truncated") for r in rs if "truncated" in r.get("gen", {})]
        if trunc:
            m["truncated_rate"] = rate(trunc)
        suites_out[name] = m
    accs = [m["accuracy"]["value"] for m in suites_out.values()]
    halluc = [x["score"]["hallucinated"] for x in records if x["suite"] in ("faithfulness", "factual")]
    summary = {"macro_accuracy": round(sum(accs) / len(accs), 4) if accs else None,
               "hallucination_rate_T1": rate(halluc),
               "items": len(records)}
    gen = [r["gen"] for r in records if r.get("gen")]
    if gen:
        toks = sum(g.get("new_tokens", 0) for g in gen)
        summary["generated_tokens"] = toks
        summary["throughput_tokens_per_s_batched"] = round(toks / lineage["wall_seconds"], 2) if lineage.get("wall_seconds") else None
    return {"run_id": lineage["run_id"], "summary": summary, "suites": suites_out,
            "targets": target_view(suites_out, summary), "lineage": lineage}


def target_view(suites_out: dict, summary: dict) -> dict:
    """Raw target-metric values. Pass/fail against a baseline is computed by `compare` (T1, T2, T5 are relative)."""
    ab = suites_out.get("abstention", {})
    return {
        "T1_hallucination_rate": summary["hallucination_rate_T1"]["value"],
        "T2_abstention_recall": ab.get("abstention_recall", {}).get("value"),
        "T2_answerable_accuracy": ab.get("answerable_accuracy", {}).get("value"),
        "T5_regression_general_accuracy": suites_out.get("regression_general", {}).get("accuracy", {}).get("value"),
        "T6_citation_accuracy": suites_out.get("faithfulness", {}).get("citation_accuracy", {}).get("value"),
        "T6_claim_accuracy": suites_out.get("faithfulness", {}).get("accuracy", {}).get("value"),
    }


def compare(candidate: dict, baseline: dict, targets_path: Path = TARGETS) -> dict:
    """Evaluate T1/T2/T5 of a candidate against a baseline report, using eval/targets.yaml."""
    t = yaml.safe_load(targets_path.read_text(encoding="utf-8"))["targets"]
    c, b = candidate["targets"], baseline["targets"]
    out = {}
    if b["T1_hallucination_rate"]:
        red = 1 - c["T1_hallucination_rate"] / b["T1_hallucination_rate"]
        out["T1"] = {"relative_reduction": round(red, 4), "pass": red >= t["T1"]["min_relative_reduction"]}
    if b["T2_answerable_accuracy"]:
        drop = 1 - c["T2_answerable_accuracy"] / b["T2_answerable_accuracy"]
        out["T2"] = {"abstention_recall": c["T2_abstention_recall"], "answerable_relative_drop": round(drop, 4),
                     "pass": c["T2_abstention_recall"] >= t["T2"]["min_abstention_recall"]
                     and drop <= t["T2"]["max_answerable_relative_drop"]}
    if b["T5_regression_general_accuracy"]:
        drop = 1 - c["T5_regression_general_accuracy"] / b["T5_regression_general_accuracy"]
        out["T5"] = {"relative_drop": round(drop, 4), "pass": drop <= t["T5"]["max_relative_drop"]}
    return out


def fmt(m: dict | None) -> str:
    if not m or m.get("value") is None:
        return "—"
    lo, hi = m["ci95"]
    return f"{m['value'] * 100:.1f}% [{lo * 100:.0f}–{hi * 100:.0f}] (n={m['n']})"


def render_markdown(report: dict) -> str:
    L = report["lineage"]
    lines = [f"### {L['model']} — {L['split']}", "",
             f"- run: `{report['run_id']}` · git `{L['git']['commit'][:7]}`{' (dirty)' if L['git']['dirty'] else ''}"
             f" · revision `{(L.get('model_revision') or '—')[:12]}` · split sha256 `{L['split_sha256'][:12]}`",
             f"- wall {L['wall_seconds']}s · peak RSS {L['peak_rss_mb']} MB · CPUs {L['hardware']['cpus']} · GPU none", ""]
    if "latency" in L:
        lat = L["latency"]
        lines.insert(-1, f"- latency (batch=1): first token median {lat['first_token_s_median']}s · decode {lat['decode_tokens_per_s_median']} tok/s")
    lines += ["| suite | accuracy (95% CI) | extra |", "|---|---|---|"]
    for name, m in report["suites"].items():
        extra = []
        for k in ("hallucination_rate", "citation_accuracy", "abstention_recall", "answerable_accuracy"):
            if k in m:
                extra.append(f"{k}: {fmt(m[k])}")
        lines.append(f"| {name} | {fmt(m['accuracy'])} | {'; '.join(extra)} |")
    s = report["summary"]
    lines += ["", f"macro accuracy: {s['macro_accuracy'] * 100:.1f}% · T1 hallucination rate: {fmt(s['hallucination_rate_T1'])}", ""]
    return "\n".join(lines)


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description="Re-render a report from a run directory")
    ap.add_argument("run_dir")
    ap.add_argument("--markdown", action="store_true")
    a = ap.parse_args()
    d = Path(a.run_dir)
    records = [json.loads(l) for l in (d / "predictions.jsonl").read_text(encoding="utf-8").splitlines() if l]
    lineage = json.loads((d / "lineage.json").read_text(encoding="utf-8"))
    rep = build_report(records, lineage)
    print(render_markdown(rep) if a.markdown else json.dumps(rep, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
