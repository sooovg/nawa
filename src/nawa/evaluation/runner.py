"""Evaluation runner (P1-07): generate predictions for a split, score them, and write lineage.

Backends:
  oracle          gold answers (sanity check of the pipeline; must score 100%)
  always_abstain  always answers "غير موجود في السياق" (shows why T2 pairs recall with answerable accuracy)
  hf:<path>       a local Hugging Face causal LM, greedy decoding on CPU. Open-weight models need a
                  configs/model_registry.yaml entry first (ADR-0003); NAWA's own checkpoints use the same path.

Predictions go to eval/runs/<run_id>/ (git-ignored). Only aggregate reports go into Git (eval/reports/).
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import resource
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from nawa.evaluation import suites
from nawa.evaluation.build import build_public
from nawa.evaluation.schema import SUITES, Item

REPO = Path(__file__).resolve().parents[3]
ABSTAIN = "غير موجود في السياق"
DTYPES = ("float32", "bfloat16")  # bfloat16 to fit larger models in RAM; recorded in lineage + config_hash


def load_items(split: str, frozen_dir: Path | None = None) -> dict[str, list[Item]]:
    if split == "frozen":
        from nawa.evaluation import frozen
        if frozen_dir is None:
            raise ValueError("--frozen-dir is required for the frozen split (Eval role only)")
        return frozen.load(frozen_dir)  # role-guarded and hash-verified
    return build_public()[split]


def split_digest(items: dict[str, list[Item]]) -> str:
    h = hashlib.sha256()
    for name in sorted(items):
        for it in items[name]:
            h.update(it.to_json().encode("utf-8") + b"\n")
    return h.hexdigest()


def git_state() -> dict:
    def run(*a):
        return subprocess.run(["git", *a], cwd=REPO, capture_output=True, text=True).stdout.strip()
    return {"commit": run("rev-parse", "HEAD"), "dirty": bool(run("status", "--porcelain", "--untracked-files=no"))}


@dataclass
class Backend:
    name: str
    revision: str | None = None
    info: dict = field(default_factory=dict)

    def generate(self, items: list[Item]) -> list[tuple[str, dict]]:
        raise NotImplementedError


class OracleBackend(Backend):
    def generate(self, items):
        return [(suites.get(it.suite).oracle(it), {}) for it in items]


class AbstainBackend(Backend):
    def generate(self, items):
        return [(ABSTAIN, {}) for _ in items]


class HFBackend(Backend):
    """Greedy decoding with a local transformers model. Imports torch lazily (not needed in CI)."""

    def __init__(self, path: str, batch_size: int = 8, threads: int | None = None, dtype: str = "float32"):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        if threads:
            torch.set_num_threads(threads)
        self.torch = torch
        self.tok = AutoTokenizer.from_pretrained(path)
        self.tok.padding_side = "left"
        if self.tok.pad_token is None:
            self.tok.pad_token = self.tok.eos_token
        if dtype not in DTYPES:
            raise ValueError(f"dtype must be one of {DTYPES}")
        self.model = AutoModelForCausalLM.from_pretrained(path, torch_dtype=getattr(torch, dtype))
        self.model.eval()
        self.batch_size = batch_size
        cfg = json.loads((Path(path) / "config.json").read_text())
        rev = Path(path).name if len(Path(path).name) == 40 else None
        parts = [x for x in Path(path).parts if x.startswith("models--")]
        name = parts[0][len("models--"):].replace("--", "/") if parts else (cfg.get("_name_or_path") or str(path))
        super().__init__(name=name, revision=rev,
                         info={"path": str(path), "dtype": dtype, "params": sum(p.numel() for p in self.model.parameters()),
                               "batch_size": batch_size, "threads": torch.get_num_threads(),
                               "torch": torch.__version__, "transformers": __import__("transformers").__version__})

    def _prompt(self, it: Item) -> str:
        kw = {"enable_thinking": False} if "qwen3" in self.name.lower() else {}
        return self.tok.apply_chat_template(it.messages, tokenize=False, add_generation_prompt=True, **kw)

    def generate(self, items):
        torch = self.torch
        prompts = [self._prompt(it) for it in items]
        order = sorted(range(len(items)), key=lambda i: (items[i].max_new_tokens, len(prompts[i])))
        out: list = [None] * len(items)
        for s in range(0, len(order), self.batch_size):
            idx = order[s:s + self.batch_size]
            enc = self.tok([prompts[i] for i in idx], return_tensors="pt", padding=True, add_special_tokens=False)
            mnt = max(items[i].max_new_tokens for i in idx)
            t0 = time.perf_counter()
            with torch.inference_mode():
                gen = self.model.generate(**enc, max_new_tokens=mnt, do_sample=False, num_beams=1,
                                          pad_token_id=self.tok.pad_token_id, temperature=None, top_p=None, top_k=None)
            dt = time.perf_counter() - t0
            new = gen[:, enc["input_ids"].shape[1]:]
            for j, i in enumerate(idx):
                ids = new[j].tolist()
                n_tok = sum(1 for t in ids if t != self.tok.pad_token_id)
                text = self.tok.decode(ids, skip_special_tokens=True).strip()
                out[i] = (text, {"new_tokens": n_tok, "batch_seconds": round(dt, 3), "batch_size": len(idx),
                                 "truncated": n_tok >= items[i].max_new_tokens})
        return out

    def latency_probe(self, items: list[Item], n: int = 8, max_new_tokens: int = 32) -> dict:
        """Single-stream (batch=1) latency and throughput for T4. OD-06 decides the target hardware."""
        torch = self.torch
        firsts, rates = [], []
        for it in items[:n]:
            enc = self.tok([self._prompt(it)], return_tensors="pt", add_special_tokens=False)
            with torch.inference_mode():
                t0 = time.perf_counter()
                self.model.generate(**enc, max_new_tokens=1, do_sample=False, pad_token_id=self.tok.pad_token_id)
                t1 = time.perf_counter()
                g = self.model.generate(**enc, max_new_tokens=max_new_tokens, min_new_tokens=max_new_tokens,
                                        do_sample=False, pad_token_id=self.tok.pad_token_id)
                t2 = time.perf_counter()
            firsts.append(t1 - t0)
            rates.append((g.shape[1] - enc["input_ids"].shape[1]) / (t2 - t1))
        firsts.sort(); rates.sort()
        return {"probe_items": len(firsts), "first_token_s_median": round(firsts[len(firsts) // 2], 3),
                "decode_tokens_per_s_median": round(rates[len(rates) // 2], 2), "batch_size": 1,
                "max_new_tokens": max_new_tokens}


def make_backend(spec: str, batch_size: int = 8, threads: int | None = None, dtype: str = "float32") -> Backend:
    if spec == "oracle":
        return OracleBackend("oracle")
    if spec == "always_abstain":
        return AbstainBackend("always_abstain")
    if spec.startswith("hf:"):
        return HFBackend(spec[3:], batch_size=batch_size, threads=threads, dtype=dtype)
    raise ValueError(f"unknown backend {spec}")


def slug(s: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in s.split("/")[-1].lower()).strip("-")


def run(backend: Backend, split: str, suite_names: list[str] | None = None, frozen_dir: Path | None = None,
        runs_dir: Path | None = None, latency: bool = False, limit: int | None = None) -> tuple[Path, dict]:
    from nawa.evaluation.report import build_report
    items = load_items(split, frozen_dir)
    names = suite_names or list(SUITES)
    if limit:
        items = {k: v[:limit] for k, v in items.items()}
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"{split}-{slug(backend.name)}-{stamp}"
    out_dir = (runs_dir or REPO / "eval" / "runs") / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    records = []
    for name in names:
        its = items[name]
        t_s = time.time()
        gens = backend.generate(its)
        mod = suites.get(name)
        for it, (text, gmeta) in zip(its, gens):
            records.append({"id": it.id, "suite": name, "output": text, "score": mod.score(it, text),
                            "meta": {k: v for k, v in it.meta.items() if k != "license"},
                            "answerable": it.gold.get("answerable"), "gen": gmeta})
        print(f"[{run_id}] {name}: {len(its)} items in {time.time() - t_s:.1f}s", flush=True)
    with (out_dir / "predictions.jsonl").open("w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    lineage = {
        "run_id": run_id, "split": split, "suites": names, "limit": limit,
        "split_sha256": split_digest({k: items[k] for k in names}),
        "model": backend.name, "model_revision": backend.revision, "backend_info": backend.info,
        "decoding": {"do_sample": False, "num_beams": 1, "max_new_tokens": "per item", "dtype": backend.info.get("dtype")},
        "git": git_state(), "created_utc": stamp, "wall_seconds": round(time.time() - t0, 1),
        "peak_rss_mb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1),
        "hardware": {"machine": platform.machine(), "cpus": os.cpu_count(), "gpu": None,
                     "processor": platform.processor() or platform.machine()},
        "python": platform.python_version(),
    }
    if latency and isinstance(backend, HFBackend):
        lineage["latency"] = backend.latency_probe(items["faithfulness"])
    lineage["config_hash"] = hashlib.sha256(json.dumps(
        {k: lineage[k] for k in ("split", "suites", "limit", "model", "model_revision", "decoding")},
        sort_keys=True).encode()).hexdigest()[:16]
    (out_dir / "lineage.json").write_text(json.dumps(lineage, ensure_ascii=False, indent=2), encoding="utf-8")
    report = build_report(records, lineage)
    (out_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_dir, report
