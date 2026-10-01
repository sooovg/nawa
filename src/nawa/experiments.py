"""Experiment record for P4 and its validator (ROADMAP P4-06, ADR-0007, AGENTS.md §8).

Every P4 experiment appends one JSON line to ``experiments/log.jsonl``. The record carries the full configuration,
the results and the fingerprints needed to reproduce it, and the validator re-derives what it can instead of trusting
the record:

* ``config_hash`` is recomputed from the inline ``config``;
* ``passed`` is recomputed from ``criteria`` (registered before the run) and ``metrics``;
* ``data_kind`` must be ``synthetic`` or ``real``; ``real`` is rejected while OD-03 is OPEN (no real data before the
  licence decision), and a ``synthetic`` record may not carry an ``improvement`` or ``adoption`` claim (ADR-0007 D2);
* ``artifact`` must be null while P4-08 (HF upload) is not DONE, so nothing is uploaded under ADR-0007;
* ``track`` must be ``S`` (ADR-0007 limits P4 to Track S).

Records written before P4-06 (EXP-0001..EXP-0023) are kept as they are (history is not rewritten). They are checked
with the legacy rules only: well-formed JSON, unique ascending ``EXP-nnnn`` ids, a task id and a conclusion.

CLI::

    python -m nawa.experiments validate [experiments/log.jsonl]
    python -m nawa.experiments smoke --seed 42          # P4-06 harness smoke run (prints a record, appends nothing)
    python -m nawa.experiments bench --seed 2026        # validator benchmark (EXP-0024)
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
import platform
import re
import struct
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[2]
LOG_PATH = ROOT / "experiments" / "log.jsonl"
ROADMAP_PATH = ROOT / "ROADMAP.md"

SCHEMA_VERSION = "p4-record/v1"
DATA_KINDS = ("synthetic", "real")
CLAIM_TYPES = ("correctness", "evidence", "improvement", "adoption")
FORBIDDEN_ON_SYNTHETIC = ("improvement", "adoption")
STATUSES = ("PASSED", "FAILED", "ABORTED")
OPS = {"<=": lambda a, b: a <= b, "<": lambda a, b: a < b, ">=": lambda a, b: a >= b,
       ">": lambda a, b: a > b, "==": lambda a, b: a == b}

# AGENTS.md §8 fields, plus the P4-06 additions (schema, data_kind, config, criteria, passed, claims, reproduce).
REQUIRED_P4_FIELDS = (
    "experiment_id", "schema", "task_id", "track", "status", "purpose",
    "git_commit", "git_dirty", "source_tree_sha256",
    "data_kind", "data_repo_id", "data_revision", "data_sha256", "data_description",
    "base_model_repo_id", "base_model_revision",
    "config", "config_hash", "seed", "hardware", "software",
    "training_steps", "gpu_hours", "cost_usd",
    "criteria", "metrics", "passed", "claims", "failure_cases",
    "artifact", "reproduce", "conclusion", "next_action",
)

ID_RE = re.compile(r"^EXP-(\d{4})$")
HEX16 = re.compile(r"^[0-9a-f]{16}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{7,40}$")


class RecordError(ValueError):
    """Raised when an experiment record violates the P4-06 schema or rules."""


# ---- project state read from ROADMAP.md --------------------------------------------------------------------------
@dataclass(frozen=True)
class Policy:
    """The project state the validator depends on. Read from ROADMAP.md by default; tests pass it explicitly."""

    od03_open: bool = True          # OD-03 (licence of future data/weights) still OPEN -> no real data
    p4_08_done: bool = False        # P4-08 (HF upload of P4 checkpoints) not DONE -> artifact must be null

    @classmethod
    def from_roadmap(cls, path: Path = ROADMAP_PATH) -> "Policy":
        text = path.read_text(encoding="utf-8")
        od03 = re.search(r"^\| OD-03 \|[^\n]*\| (\w+)[^|\n]* \|\s*$", text, flags=re.M)
        p408 = re.search(r"^\| P4-08 \| (\w+) \|", text, flags=re.M)
        if not od03 or not p408:
            raise RecordError("ROADMAP.md: cannot read the OD-03 or P4-08 status rows")
        # Conservative: OD-03 counts as open unless the register says it was decided.
        return cls(od03_open=od03[1] not in {"RESOLVED", "ACCEPTED"}, p4_08_done=p408[1] == "DONE")


# ---- hashing helpers -----------------------------------------------------------------------------------------------
def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def config_hash(config: dict[str, Any]) -> str:
    """First 16 hex chars of sha256 over the canonical JSON (the same convention as ``DecoderConfig.config_hash``)."""
    return hashlib.sha256(canonical_json(config).encode("utf-8")).hexdigest()[:16]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def source_tree_sha256(root: Path = ROOT) -> str:
    """sha256 over the sorted (path, content) pairs of ``src/nawa/**/*.py``: identifies the exact code that ran,
    including uncommitted changes (``git_commit`` alone does not when ``git_dirty`` is true)."""
    h = hashlib.sha256()
    for p in sorted((root / "src" / "nawa").rglob("*.py")):
        h.update(p.relative_to(root).as_posix().encode("utf-8") + b"\0")
        h.update(p.read_bytes() + b"\0")
    return h.hexdigest()


def git_state(root: Path = ROOT) -> tuple[str, bool]:
    def run(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=True).stdout.strip()
    try:
        # Untracked files count: new, uncommitted code is still code that ran (found in EXP-0024 dry run).
        return run("rev-parse", "HEAD"), bool(run("status", "--porcelain", "--untracked-files=normal"))
    except (OSError, subprocess.CalledProcessError) as exc:  # pragma: no cover - only outside a git checkout
        raise RecordError(f"git state unavailable: {exc}") from exc


def hardware() -> dict[str, Any]:
    gpu = None
    try:
        import torch
        if torch.cuda.is_available():  # pragma: no cover - CI has no GPU
            gpu = torch.cuda.get_device_name(0)
    except ImportError:
        pass
    return {"machine": platform.machine(), "cpus": os.cpu_count(), "gpu": gpu}


def software() -> dict[str, Any]:
    out: dict[str, Any] = {"python": platform.python_version()}
    try:
        import torch
        out["torch"] = torch.__version__
    except ImportError:
        out["torch"] = None
    return out


# ---- criteria --------------------------------------------------------------------------------------------------------
def evaluate_criteria(criteria: dict[str, Any], metrics: dict[str, Any]) -> dict[str, bool]:
    """``criteria`` maps a metric name to ``{"op": "<=", "value": x}``. Each check is re-derived from ``metrics``."""
    if not isinstance(criteria, dict) or not criteria:
        raise RecordError("criteria must be a non-empty mapping registered before the run")
    out = {}
    for name, rule in criteria.items():
        if not isinstance(rule, dict) or set(rule) != {"op", "value"} or rule["op"] not in OPS:
            raise RecordError(f"criterion {name!r} must be {{'op': one of {sorted(OPS)}, 'value': ...}}")
        if name not in metrics:
            raise RecordError(f"criterion {name!r} has no metric of the same name")
        value = metrics[name]
        if isinstance(value, float) and not math.isfinite(value):
            out[name] = False
            continue
        try:
            out[name] = bool(OPS[rule["op"]](value, rule["value"]))
        except TypeError as exc:
            raise RecordError(f"criterion {name!r}: cannot compare {value!r} {rule['op']} {rule['value']!r}") from exc
    return out


# ---- validation ------------------------------------------------------------------------------------------------------
def is_p4_record(rec: dict[str, Any]) -> bool:
    return str(rec.get("task_id", "")).startswith("P4-") or rec.get("schema") == SCHEMA_VERSION


def validate_legacy(rec: dict[str, Any]) -> list[str]:
    errs = []
    if not ID_RE.match(str(rec.get("experiment_id", ""))):
        errs.append("experiment_id must look like EXP-nnnn")
    if not rec.get("task_id"):
        errs.append("task_id is required")
    if rec.get("track") not in ("S", "B", "meta", None):
        errs.append(f"track {rec.get('track')!r} not in S/B/meta/null")
    if not isinstance(rec.get("conclusion"), str) or not rec["conclusion"].strip():
        errs.append("conclusion is required")
    return errs


def validate_p4(rec: dict[str, Any], policy: Policy) -> list[str]:
    """Return every violation (empty list = valid). Never raises for a malformed record."""
    errs = [f"missing field {f!r}" for f in REQUIRED_P4_FIELDS if f not in rec]
    if errs:
        return errs
    errs += validate_legacy(rec)
    if rec["schema"] != SCHEMA_VERSION:
        errs.append(f"schema must be {SCHEMA_VERSION!r}")
    if not re.match(r"^P4-0[2-7]a?$", str(rec["task_id"])):
        errs.append("task_id must be an unblocked P4 code task (P4-02..P4-07, ADR-0007)")
    if rec["track"] != "S":
        errs.append("track must be 'S' (ADR-0007 limits P4 to Track S)")
    if rec["status"] not in STATUSES:
        errs.append(f"status must be one of {STATUSES}")
    if not COMMIT_RE.match(str(rec["git_commit"])):
        errs.append("git_commit must be a 7-40 char hex commit")
    if not isinstance(rec["git_dirty"], bool):
        errs.append("git_dirty must be a bool")
    if not HEX64.match(str(rec["source_tree_sha256"])):
        errs.append("source_tree_sha256 must be 64 hex chars")
    # data
    if rec["data_kind"] not in DATA_KINDS:
        errs.append(f"data_kind must be one of {DATA_KINDS}")
    if rec["data_kind"] == "real" and policy.od03_open:
        errs.append("data_kind 'real' is not allowed while OD-03 is OPEN")
    if not HEX64.match(str(rec["data_sha256"])):
        errs.append("data_sha256 must be the 64-hex sha256 of the exact data used")
    if rec["data_kind"] == "synthetic" and (rec["data_repo_id"] is not None or rec["data_revision"] is not None):
        errs.append("synthetic data has no data_repo_id/data_revision (it is regenerated from code and seed)")
    if not isinstance(rec["data_description"], str) or not rec["data_description"].strip():
        errs.append("data_description is required (generator, seed, size)")
    if rec["base_model_repo_id"] is not None or rec["base_model_revision"] is not None:
        errs.append("base_model_repo_id/revision must be null: Track S loads no external weights")
    # config
    if not isinstance(rec["config"], dict) or not rec["config"]:
        errs.append("config must be the full inline configuration")
    elif rec["config_hash"] != config_hash(rec["config"]):
        errs.append("config_hash does not match the inline config")
    seeds = rec["seed"] if isinstance(rec["seed"], list) else [rec["seed"]]
    if not seeds or not all(isinstance(s, int) and not isinstance(s, bool) for s in seeds):
        errs.append("seed must be an int or a non-empty list of ints")
    for key in ("machine", "cpus", "gpu"):
        if not isinstance(rec["hardware"], dict) or key not in rec["hardware"]:
            errs.append(f"hardware.{key} is required")
    if not isinstance(rec["software"], dict) or "python" not in rec["software"]:
        errs.append("software.python is required")
    for key in ("training_steps", "gpu_hours", "cost_usd"):
        if not isinstance(rec[key], (int, float)) or isinstance(rec[key], bool) or rec[key] < 0:
            errs.append(f"{key} must be a non-negative number")
    if rec["gpu_hours"] or rec["cost_usd"]:
        errs.append("gpu_hours and cost_usd must be 0: ADR-0007 limits P4 to cpu_local work")
    # results
    if not isinstance(rec["metrics"], dict):
        errs.append("metrics must be a mapping")
    else:
        try:
            checks = evaluate_criteria(rec["criteria"], rec["metrics"])
            if rec["passed"] != all(checks.values()):
                errs.append(f"passed={rec['passed']!r} does not match the criteria re-evaluated on metrics {checks}")
            if rec["status"] in ("PASSED", "FAILED") and (rec["status"] == "PASSED") != rec["passed"]:
                errs.append("status and passed disagree")
        except RecordError as exc:
            errs.append(str(exc))
    if not isinstance(rec["claims"], list):
        errs.append("claims must be a list")
    else:
        for c in rec["claims"]:
            if not isinstance(c, dict) or c.get("type") not in CLAIM_TYPES or not str(c.get("text", "")).strip():
                errs.append(f"claim {c!r} must be {{'type': one of {CLAIM_TYPES}, 'text': ...}}")
            elif c["type"] in FORBIDDEN_ON_SYNTHETIC and rec["data_kind"] == "synthetic":
                errs.append(f"a {c['type']!r} claim is not allowed on synthetic data (ADR-0007 D2)")
            elif c["type"] == "adoption":
                errs.append("adoption is a gated technical decision (ROADMAP §4), not an experiment claim")
    if not isinstance(rec["failure_cases"], list):
        errs.append("failure_cases must be a list (empty if none)")
    if rec["artifact"] is not None and not policy.p4_08_done:
        errs.append("artifact must be null while P4-08 is not DONE (no upload under ADR-0007)")
    if not isinstance(rec["reproduce"], str) or not rec["reproduce"].strip():
        errs.append("reproduce must be the exact command")
    for key in ("purpose", "next_action"):
        if not isinstance(rec[key], str) or not rec[key].strip():
            errs.append(f"{key} is required")
    return errs


def validate_log(lines: Iterable[str], policy: Policy) -> list[str]:
    """Validate a whole log: JSON per line, unique ascending ids, legacy rules or P4 rules per record."""
    errs, last = [], 0
    seen: set[str] = set()
    for n, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError as exc:
            errs.append(f"line {n}: invalid JSON ({exc.msg})")
            continue
        if not isinstance(rec, dict):
            errs.append(f"line {n}: not an object")
            continue
        eid = str(rec.get("experiment_id", ""))
        m = ID_RE.match(eid)
        if eid in seen:
            errs.append(f"line {n}: duplicate {eid}")
        seen.add(eid)
        if m:
            if int(m[1]) <= last:
                errs.append(f"line {n}: {eid} is not ascending")
            last = max(last, int(m[1]))
        rule = validate_p4 if is_p4_record(rec) else (lambda r, _p: validate_legacy(r))
        errs += [f"line {n} ({eid}): {e}" for e in rule(rec, policy)]
    return errs


def next_id(path: Path = LOG_PATH) -> str:
    last = 0
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                m = ID_RE.match(json.loads(line).get("experiment_id", ""))
                last = max(last, int(m[1])) if m else last
    return f"EXP-{last + 1:04d}"


# ---- builder ---------------------------------------------------------------------------------------------------------
@dataclass
class P4Run:
    """Inputs of one P4 experiment. ``build`` fills the fingerprints and re-derives ``passed``."""

    task_id: str
    purpose: str
    config: dict[str, Any]
    seed: int | list[int]
    data_sha256: str
    data_description: str
    criteria: dict[str, Any]
    metrics: dict[str, Any]
    reproduce: str
    conclusion: str
    next_action: str
    data_kind: str = "synthetic"
    claims: list[dict[str, str]] = field(default_factory=list)
    failure_cases: list[str] = field(default_factory=list)
    training_steps: int = 0
    status: str | None = None   # None = derived from the criteria

    def build(self, experiment_id: str, policy: Policy | None = None, root: Path = ROOT) -> dict[str, Any]:
        commit, dirty = git_state(root)
        passed = all(evaluate_criteria(self.criteria, self.metrics).values())
        rec = {
            "experiment_id": experiment_id, "schema": SCHEMA_VERSION, "task_id": self.task_id, "track": "S",
            "status": self.status or ("PASSED" if passed else "FAILED"), "purpose": self.purpose,
            "git_commit": commit, "git_dirty": dirty, "source_tree_sha256": source_tree_sha256(root),
            "data_kind": self.data_kind, "data_repo_id": None, "data_revision": None,
            "data_sha256": self.data_sha256, "data_description": self.data_description,
            "base_model_repo_id": None, "base_model_revision": None,
            "config": self.config, "config_hash": config_hash(self.config), "seed": self.seed,
            "hardware": hardware(), "software": software(),
            "training_steps": self.training_steps, "gpu_hours": 0, "cost_usd": 0,
            "criteria": self.criteria, "metrics": self.metrics, "passed": passed, "claims": self.claims,
            "failure_cases": self.failure_cases, "artifact": None, "reproduce": self.reproduce,
            "conclusion": self.conclusion, "next_action": self.next_action,
        }
        errs = validate_p4(rec, policy or Policy.from_roadmap())
        if errs:
            raise RecordError("; ".join(errs))
        return rec


def append(rec: dict[str, Any], path: Path = LOG_PATH, policy: Policy | None = None) -> None:
    """Append a record after validating it together with the existing log (refuses to write an invalid log)."""
    policy = policy or Policy.from_roadmap()
    lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    errs = validate_log([*lines, json.dumps(rec, ensure_ascii=False)], policy)
    if errs:
        raise RecordError("; ".join(errs))
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


# ---- smoke run: one tiny reference-core training on a synthetic source -----------------------------------------------
SMOKE_CONFIG: dict[str, Any] = {
    "model": {"vocab_size": 29, "d_model": 32, "n_layers": 1, "n_heads": 2, "max_seq_len": 32},
    "train": {"steps": 150, "batch": 16, "seq_len": 32, "lr": 3e-3, "weight_decay": 0.01, "grad_clip": 1.0},
    "data": {"generator": "nawa.training.sanity.MarkovSource", "k": 29, "train_symbols": 60_000,
             "val_symbols": 8_000},
}
# Registered before the first run. Correctness of the record pipeline only; the losses are evidence, not a claim.
SMOKE_CRITERIA: dict[str, Any] = {
    "rerun_identical": {"op": "==", "value": True},
    "val_loss_finite": {"op": "==", "value": True},
    "loss_decreased": {"op": "==", "value": True},
}


def _smoke_once(seed: int, cfg: dict[str, Any]) -> dict[str, Any]:
    import torch

    from nawa import budget
    from nawa.model import DecoderConfig, NawaDecoder
    from nawa.training.sanity import MarkovSource, batches, heldout_loss

    decision = budget.check("cpu_local")
    if not decision.allowed:
        raise RecordError(f"budget guard refused the run: {decision.reason}")
    d, t = cfg["data"], cfg["train"]
    source = MarkovSource.make(k=d["k"], seed=seed)
    train = source.sample(d["train_symbols"], seed=seed + 1)
    val = source.sample(d["val_symbols"], seed=seed + 2)
    data_sha = sha256_bytes(_pack_ints(train.tolist()) + b"|" + _pack_ints(val.tolist()))
    torch.manual_seed(seed)
    model = NawaDecoder(DecoderConfig(**cfg["model"])).train()
    opt = torch.optim.AdamW(model.parameters(), lr=t["lr"], weight_decay=t["weight_decay"])
    g = torch.Generator().manual_seed(seed + 3)
    initial = heldout_loss(model, val, t["seq_len"])
    for _ in range(t["steps"]):
        x, y = batches(train, t["seq_len"], t["batch"], g)
        loss = model(x, targets=y).loss
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), t["grad_clip"])
        opt.step()
    final = heldout_loss(model, val, t["seq_len"])
    weights = sha256_bytes(b"".join(_pack_floats(p.detach().double().flatten().tolist())
                                    for p in model.parameters()))
    rates = source.entropy_rates()
    return {"data_sha256": data_sha, "initial_val_loss": round(initial, 6), "final_val_loss": round(final, 6),
            "final_weights_sha256": weights, "parameters": model.num_parameters(),
            "model_config_hash": DecoderConfig(**cfg["model"]).config_hash(),
            "entropy_nats": {k: round(v, 6) for k, v in rates.items()}}


def _pack_ints(values: list[int]) -> bytes:
    """int64 little-endian, independent of numpy and platform byte order."""
    return struct.pack(f"<{len(values)}q", *values)


def _pack_floats(values: list[float]) -> bytes:
    return struct.pack(f"<{len(values)}d", *values)


def smoke_run(seed: int = 42, cfg: dict[str, Any] | None = None) -> P4Run:
    """Train the same tiny model twice and record it. ``rerun_identical`` checks data, loss and weight hashes."""
    cfg = copy.deepcopy(cfg or SMOKE_CONFIG)
    a, b = _smoke_once(seed, cfg), _smoke_once(seed, cfg)
    metrics = {**a, "rerun_identical": a == b,
               "val_loss_finite": math.isfinite(a["final_val_loss"]),
               "loss_decreased": a["final_val_loss"] < a["initial_val_loss"]}
    return P4Run(
        task_id="P4-06",
        purpose="P4-06 harness smoke run: one tiny reference-core training on the P3-05 synthetic Markov source, run "
                "twice, recorded with the P4 schema. Checks the record pipeline, not any technique.",
        config=cfg, seed=seed, data_sha256=a["data_sha256"],
        data_description=f"synthetic: MarkovSource.make(k={cfg['data']['k']}, seed={seed}); train = sample("
                         f"{cfg['data']['train_symbols']}, seed={seed + 1}), val = sample("
                         f"{cfg['data']['val_symbols']}, seed={seed + 2}); int64 little-endian bytes (struct) hashed",
        criteria=SMOKE_CRITERIA, metrics=metrics, training_steps=cfg["train"]["steps"],
        reproduce=f"python -m nawa.experiments smoke --seed {seed}",
        claims=[{"type": "correctness", "text": "Same seed and config give identical data, loss and weight hashes; "
                                                "the record validates under the P4 schema."},
                {"type": "evidence", "text": "Loss values on a synthetic source are pipeline evidence only."}],
        conclusion="Record pipeline works end to end on a synthetic source; no technique is compared or adopted.",
        next_action="P4-05 (KV cache, greedy speculative decoding, compilation) using this record.",
    )


# ---- validator benchmark (EXP-0024) ----------------------------------------------------------------------------------
BENCH_CRITERIA: dict[str, Any] = {   # registered before the first run
    "legacy_records_valid_rate": {"op": "==", "value": 1.0},
    "valid_p4_accept_rate": {"op": "==", "value": 1.0},
    "violation_detection_rate": {"op": "==", "value": 1.0},
    "append_refuses_invalid": {"op": "==", "value": True},
}


def mutations() -> dict[str, Any]:
    """One corruption per rule. Each must be rejected by ``validate_p4``."""
    def setk(k: str, v: Any):
        return lambda r: r.__setitem__(k, v)
    def setm(k: str, v: Any):
        return lambda r: r["metrics"].__setitem__(k, v)
    return {
        "improvement_claim_on_synthetic": lambda r: r["claims"].append({"type": "improvement", "text": "x beats y"}),
        "adoption_claim": lambda r: r["claims"].append({"type": "adoption", "text": "adopt x"}),
        "real_data_while_od03_open": setk("data_kind", "real"),
        "unknown_data_kind": setk("data_kind", "mixed"),
        "artifact_uploaded": setk("artifact", {"repo_id": "vuuuv/nawa-core", "revision": "dev"}),
        "config_hash_mismatch": lambda r: r["config"].__setitem__("extra", 1),
        "passed_inconsistent": setk("passed", False),
        "status_inconsistent": setk("status", "FAILED"),
        "criterion_without_metric": lambda r: r["criteria"].__setitem__("ghost", {"op": "==", "value": 1}),
        "criteria_empty": setk("criteria", {}),
        "missing_field": lambda r: r.pop("reproduce"),
        "bad_commit": setk("git_commit", "not-a-commit"),
        "bad_data_hash": setk("data_sha256", "abc"),
        "synthetic_with_repo": setk("data_repo_id", "vuuuv/nawa-data"),
        "external_base_model": setk("base_model_repo_id", "someone/model"),
        "track_b": setk("track", "B"),
        "blocked_task": setk("task_id", "P4-01"),
        "gpu_hours": setk("gpu_hours", 1.5),
        "nan_metric_marked_pass": lambda r: (r["criteria"].__setitem__("loss", {"op": "<=", "value": 9.0}),
                                             r["metrics"].__setitem__("loss", float("nan"))),
        "bad_seed": setk("seed", "42"),
        "empty_reproduce": setk("reproduce", " "),
        "metric_flipped": setm("rerun_identical", False),
    }


def synthetic_valid_record(i: int, seed: int) -> dict[str, Any]:
    """A valid P4 record without running anything (fingerprints are drawn deterministically)."""
    h = lambda s: hashlib.sha256(f"{seed}:{i}:{s}".encode()).hexdigest()  # noqa: E731
    cfg = {"model": {"d_model": 16 * (1 + i % 4)}, "train": {"steps": 10 + i}}
    metrics = {"rerun_identical": True, "loss": 1.0 + (i % 7) / 10}
    rec = {
        "experiment_id": f"EXP-{9000 + i:04d}", "schema": SCHEMA_VERSION, "task_id": f"P4-0{2 + i % 6}",
        "track": "S", "status": "PASSED", "purpose": "bench", "git_commit": h("c")[:12], "git_dirty": bool(i % 2),
        "source_tree_sha256": h("src"), "data_kind": "synthetic", "data_repo_id": None, "data_revision": None,
        "data_sha256": h("d"), "data_description": "bench generator", "base_model_repo_id": None,
        "base_model_revision": None, "config": cfg, "config_hash": config_hash(cfg), "seed": [seed, i] if i % 3 else i,
        "hardware": {"machine": "x86_64", "cpus": 2, "gpu": None}, "software": {"python": "3"},
        "training_steps": i, "gpu_hours": 0, "cost_usd": 0,
        "criteria": {"rerun_identical": {"op": "==", "value": True}, "loss": {"op": "<=", "value": 2.0}},
        "metrics": metrics, "passed": True,
        "claims": [{"type": "correctness", "text": "ok"}] + ([{"type": "evidence", "text": "e"}] if i % 2 else []),
        "failure_cases": [], "artifact": None, "reproduce": "python -m x", "conclusion": "c", "next_action": "n",
    }
    return rec


def bench(seed: int = 2026, n: int = 30, log_path: Path = LOG_PATH) -> dict[str, Any]:
    import random
    import tempfile

    policy = Policy(od03_open=True, p4_08_done=False)
    legacy = [json.loads(l) for l in log_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    legacy = [r for r in legacy if not is_p4_record(r)]
    legacy_ok = sum(not validate_legacy(r) for r in legacy)
    rng = random.Random(seed)
    valid = [synthetic_valid_record(i, seed) for i in range(n)]
    accepted = sum(not validate_p4(r, policy) for r in valid)
    detected, total, missed = 0, 0, []
    for name, mutate in mutations().items():
        for rec in rng.sample(valid, k=min(5, n)):
            bad = copy.deepcopy(rec)
            mutate(bad)
            total += 1
            if validate_p4(bad, policy):
                detected += 1
            else:
                missed.append(name)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "log.jsonl"
        path.write_text(json.dumps(valid[0]) + "\n", encoding="utf-8")
        bad = copy.deepcopy(valid[1])
        bad["artifact"] = {"repo_id": "x"}
        try:
            append(bad, path, policy)
            refused = False
        except RecordError:
            refused = path.read_text(encoding="utf-8").count("\n") == 1
    return {"legacy_records": len(legacy), "legacy_records_valid_rate": legacy_ok / max(1, len(legacy)),
            "valid_p4_records": n, "valid_p4_accept_rate": accepted / n,
            "mutation_types": len(mutations()), "mutated_records": total,
            "violation_detection_rate": detected / total, "missed": sorted(set(missed)),
            "append_refuses_invalid": refused}


def p4_06_run(seed: int = 42, bench_seeds: tuple[int, ...] = (2026, 7)) -> P4Run:
    """The P4-06 experiment (EXP-0024): smoke run + validator benchmark on two seeds, one record."""
    run = smoke_run(seed)
    metrics, criteria = dict(run.metrics), dict(run.criteria)
    worst: dict[str, Any] = {}
    for b in bench_seeds:
        res = bench(b)
        metrics[f"bench_seed_{b}"] = res
        for k in BENCH_CRITERIA:
            worst[k] = min(worst.get(k, res[k]), res[k])
    metrics.update(worst)
    criteria.update(BENCH_CRITERIA)
    run.metrics, run.criteria = metrics, criteria
    run.config = {**run.config, "bench": {"seeds": list(bench_seeds), "n": 30, "mutation_types": len(mutations())}}
    run.purpose = ("P4-06: P4 experiment record schema and validator. (1) validator benchmark: legacy log, valid "
                   "records, one corruption per rule; (2) smoke run of the record pipeline on a synthetic source.")
    run.reproduce = f"python -m nawa.experiments record-p4-06 --seed {seed} --dry-run"
    run.failure_cases = [
        "First record attempt (not committed) said git_dirty=false although src/nawa/experiments.py was untracked: "
        "git_state ignored untracked files. Fixed to count them; the record was re-created. Criteria unchanged.",
        "Smoke loss falls only 3.382 -> 3.348 in 150 steps (H0 3.365, H2 2.378): the run checks the pipeline, it is "
        "not a learning test (P3-05 is).",
        "The validator benchmark was written by the same agent as the validator (no independent review: OD-10 open).",
    ]
    run.conclusion = ("Every P4 record rule is enforced by re-derivation (config hash, passed, data_kind policy, "
                      "no artifact, Track S); the pipeline runs end to end. No technique compared or adopted.")
    return run


# ---- CLI -------------------------------------------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m nawa.experiments")
    sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validate")
    v.add_argument("path", nargs="?", default=str(LOG_PATH))
    s = sub.add_parser("smoke")
    s.add_argument("--seed", type=int, default=42)
    b = sub.add_parser("bench")
    b.add_argument("--seed", type=int, default=2026)
    b.add_argument("--n", type=int, default=30)
    r = sub.add_parser("record-p4-06")
    r.add_argument("--seed", type=int, default=42)
    r.add_argument("--dry-run", action="store_true", help="print the record, do not append")
    args = ap.parse_args(argv)
    if args.cmd == "validate":
        errs = validate_log(Path(args.path).read_text(encoding="utf-8").splitlines(), Policy.from_roadmap())
        print("\n".join(errs) if errs else f"{args.path}: valid")
        return 1 if errs else 0
    if args.cmd == "smoke":
        rec = smoke_run(args.seed).build(next_id())
        print(json.dumps(rec, ensure_ascii=False, indent=1))
        return 0 if rec["passed"] else 1
    if args.cmd == "record-p4-06":
        rec = p4_06_run(args.seed).build(next_id())
        if not args.dry_run:
            append(rec)
        print(json.dumps(rec, ensure_ascii=False, indent=1))
        return 0 if rec["passed"] else 1
    res = bench(args.seed, args.n)
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0 if all(evaluate_criteria(BENCH_CRITERIA, res).values()) else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
