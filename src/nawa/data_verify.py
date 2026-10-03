"""Independent verification of data candidates (ROADMAP P2-02, ADR-0005).

Rule (ROADMAP P2-02): no example enters training before an *independent* check: a calculation,
an execution, a licensed source, or an expert review. This module is that check. It is code only
(ADR-0005 D2): it ingests no external data, produces no training data, never reads the frozen
split, and uploads nothing.

A candidate is a dict::

    {"id": "...", "claim": "...", "method": "calculation|execution|licensed_source|expert_review",
     "producer": "<who/what made the claim>", "evidence": {...},
     "split": null|"dev"|"calib"|"frozen", "content_hash": null|"<sha256>"}

Statuses (same words as the Atlas, AGENTS.md §9):

* ``verified``   — the independent check ran and the claim holds;
* ``rejected``   — the check ran and the claim is false;
* ``unverified`` — the check could not be run or is not independent (missing evidence, producer
  checking itself, unapproved license, a model posing as an expert...). Never guessed.

Training eligibility (:func:`train_eligibility`) is a separate, stricter decision: a verified
candidate is still blocked while G2 is not DONE in ROADMAP §2.1, when it comes from an evaluation
split, or when its content hash is a frozen item hash (``eval/frozen_item_hashes.txt``).

    python -m nawa.data_verify check candidates.jsonl --out results.jsonl
    python -m nawa.data_verify bench --seed 2026
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import operator
import random
import re
from dataclasses import asdict, dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Any, Callable

from nawa.config import load_yaml
from nawa.evaluation.normalize import normalize, normalize_digits
from nawa.evaluation.sandbox import run_python

REPO = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO / "configs" / "verification.yaml"
ROADMAP_PATH = REPO / "ROADMAP.md"
FROZEN_HASHES_PATH = REPO / "eval" / "frozen_item_hashes.txt"

STATUSES = ("verified", "rejected", "unverified")
EVAL_SPLITS = ("dev", "calib", "frozen")


@dataclass
class VerificationResult:
    candidate_id: str
    method: str
    status: str
    reason: str
    evidence: dict[str, Any] = field(default_factory=dict)
    verifier_version: str = ""

    def __post_init__(self) -> None:
        if self.status not in STATUSES:
            raise ValueError(f"status {self.status!r} not in {STATUSES}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    cfg = load_yaml(path)
    if cfg.get("schema_version") != 1:
        raise ValueError(f"{path}: unsupported schema_version {cfg.get('schema_version')!r}")
    return cfg


# ---------------------------------------------------------------------------------------------------
# calculation: a safe exact evaluator (no eval(), no names, no calls)
# ---------------------------------------------------------------------------------------------------

_BINOPS: dict[type, Callable[[Any, Any], Any]] = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod, ast.Pow: operator.pow,
}
_UNOPS: dict[type, Callable[[Any], Any]] = {ast.UAdd: operator.pos, ast.USub: operator.neg}
_ARABIC_OPS = str.maketrans({"×": "*", "÷": "/", "−": "-", "٫": ".", "٪": "%"})


class CalcError(ValueError):
    """The expression is not a plain arithmetic expression the verifier accepts."""


def _to_fraction(text: str) -> Fraction:
    t = normalize_digits(str(text)).strip().translate(_ARABIC_OPS).replace(",", "")
    try:
        return Fraction(t)
    except (ValueError, ZeroDivisionError) as e:
        raise CalcError(f"not a number: {text!r}") from e


def safe_eval(expression: str, max_exponent: int = 64, max_chars: int = 512) -> Fraction:
    """Evaluate + - * / // % ** and parentheses over exact rationals. Anything else is refused."""
    expr = normalize_digits(expression).translate(_ARABIC_OPS)
    if len(expr) > max_chars:
        raise CalcError("expression too long")
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as e:
        raise CalcError(f"not an expression: {expression!r}") from e

    def ev(node: ast.AST) -> Fraction:
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return Fraction(str(node.value))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _UNOPS:
            return _UNOPS[type(node.op)](ev(node.operand))
        if isinstance(node, ast.BinOp) and type(node.op) in _BINOPS:
            left, right = ev(node.left), ev(node.right)
            if isinstance(node.op, ast.Pow):
                if right.denominator != 1 or abs(right) > max_exponent:
                    raise CalcError("exponent must be an integer within the configured bound")
            if isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod)) and right == 0:
                raise CalcError("division by zero")
            return Fraction(_BINOPS[type(node.op)](left, right))
        raise CalcError(f"forbidden syntax: {type(node).__name__}")

    return ev(tree)


def _check_calculation(ev: dict[str, Any], cfg: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    if not ev.get("expression") or ev.get("claimed") in (None, ""):
        return "unverified", "calculation needs evidence.expression and evidence.claimed", {}
    c = cfg.get("calculation", {})
    try:
        value = safe_eval(ev["expression"], c.get("max_exponent", 64), c.get("max_expression_chars", 512))
        claimed = _to_fraction(ev["claimed"])
    except CalcError as e:
        return "unverified", f"calculation could not run: {e}", {}
    tol = Fraction(str(ev.get("tolerance", 0)))
    out = {"computed": str(value), "claimed": str(claimed), "tolerance": str(tol)}
    if abs(value - claimed) <= tol:
        return "verified", "exact recomputation matches the claimed value", out
    return "rejected", "exact recomputation differs from the claimed value", out


# ---------------------------------------------------------------------------------------------------
# execution: run the code with independently authored tests in the sandbox
# ---------------------------------------------------------------------------------------------------

def _check_execution(ev: dict[str, Any], producer: str, cfg: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    code, tests, author = ev.get("code"), ev.get("tests"), ev.get("tests_author")
    if not code or not tests or not author:
        return "unverified", "execution needs evidence.code, evidence.tests and evidence.tests_author", {}
    if author == producer:
        return "unverified", "tests written by the producer are not an independent check", {}
    if "assert" not in tests:
        return "unverified", "tests contain no assertion", {}
    r = run_python(code + "\n\n" + tests, timeout=float(cfg.get("execution", {}).get("timeout_seconds", 10)))
    out = {"returncode": r.returncode, "timed_out": r.timed_out, "stderr_tail": r.stderr[-300:]}
    if r.ok:
        return "verified", "independent tests pass in the sandbox", out
    return "rejected", "independent tests fail or time out in the sandbox", out


# ---------------------------------------------------------------------------------------------------
# licensed_source: the claim's answer must be in a verbatim quote from a hashed, licensed source
# ---------------------------------------------------------------------------------------------------

def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _check_licensed_source(ev: dict[str, Any], cfg: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    need = ("source_id", "source_text", "source_sha256", "license", "quote", "answer")
    missing = [k for k in need if not ev.get(k)]
    if missing:
        return "unverified", f"licensed_source needs evidence fields {missing}", {}
    out = {"source_id": ev["source_id"], "license": ev["license"]}
    if sha256_text(ev["source_text"]) != ev["source_sha256"]:
        return "unverified", "source text does not match its sha256 (tampered or wrong revision)", out
    approved = cfg.get("approved_licenses") or []
    if ev["license"] not in approved:
        return "unverified", f"license {ev['license']!r} is not approved (OD-03; configs/verification.yaml)", out
    quote, source, answer = normalize(ev["quote"]), normalize(ev["source_text"]), normalize(ev["answer"])
    if not quote or quote not in source:
        return "rejected", "the quote is not found verbatim in the source", out
    if not answer or not re.search(rf"(?<!\w){re.escape(answer)}(?!\w)", quote):
        return "rejected", "the quote does not contain the claimed answer", out
    return "verified", "answer found in a verbatim quote of a hashed source with an approved license", out


# ---------------------------------------------------------------------------------------------------
# expert_review: a named human, not the producer, not a model
# ---------------------------------------------------------------------------------------------------

def _check_expert_review(ev: dict[str, Any], producer: str, cfg: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    reviewer, decision, when = ev.get("reviewer"), ev.get("decision"), ev.get("date")
    if not reviewer or decision not in ("accept", "reject") or not when:
        return "unverified", "expert_review needs evidence.reviewer, evidence.decision (accept|reject), evidence.date", {}
    prefix = cfg.get("expert_reviewer_prefix", "human:")
    out = {"reviewer": reviewer, "decision": decision, "date": when}
    if not reviewer.startswith(prefix) or len(reviewer) <= len(prefix):
        return "unverified", (f"expert reviewer must be a named human ({prefix}<id>); a model or automation "
                              "is a hypothesis, not a verification (ADR-0003 D4)"), out
    if reviewer in (producer, prefix + producer) or reviewer[len(prefix):] == producer:
        return "unverified", "the producer cannot review its own claim", out
    if decision == "accept":
        return "verified", "accepted by an independent human expert", out
    return "rejected", "rejected by an independent human expert", out


# ---------------------------------------------------------------------------------------------------
# entry points
# ---------------------------------------------------------------------------------------------------

def verify(candidate: dict[str, Any], cfg: dict[str, Any] | None = None) -> VerificationResult:
    cfg = cfg if cfg is not None else load_config()
    cid = str(candidate.get("id") or "")
    method = candidate.get("method") or ""
    producer = candidate.get("producer") or ""
    ev = candidate.get("evidence") or {}
    version = cfg.get("verifier_version", "")
    if not cid or not producer:
        return VerificationResult(cid, method, "unverified", "candidate needs id and producer", {}, version)
    if candidate.get("split") == "frozen":
        return VerificationResult(cid, method, "unverified",
                                  "frozen items are private and never verified as data (P1-03)", {}, version)
    if method not in cfg.get("methods", ()):
        return VerificationResult(cid, method, "unverified", f"unknown method {method!r}", {}, version)
    if method == "calculation":
        status, reason, out = _check_calculation(ev, cfg)
    elif method == "execution":
        status, reason, out = _check_execution(ev, producer, cfg)
    elif method == "licensed_source":
        status, reason, out = _check_licensed_source(ev, cfg)
    else:
        status, reason, out = _check_expert_review(ev, producer, cfg)
    return VerificationResult(cid, method, status, reason, out, version)


def gate_status(gate: str, roadmap: Path = ROADMAP_PATH) -> str:
    """Status of a gate in ROADMAP §2.1 (the single source of truth, AGENTS.md §2.1)."""
    text = roadmap.read_text(encoding="utf-8")
    m = re.search(rf"^\| {re.escape(gate)} [^|]*\| ([A-Z_]+) \|", text, flags=re.M)
    if not m:
        raise ValueError(f"gate {gate} not found in {roadmap}")
    return m.group(1)


def frozen_hashes(path: Path = FROZEN_HASHES_PATH) -> set[str]:
    return {line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}


def train_eligibility(candidate: dict[str, Any], result: VerificationResult,
                      roadmap: Path = ROADMAP_PATH, frozen: set[str] | None = None) -> tuple[bool, str]:
    """May this candidate enter training? Every condition must hold; the first failing one is reported."""
    if result.status != "verified":
        return False, f"not verified ({result.status}): unverified examples never enter training (AGENTS.md §9)"
    if candidate.get("split") in EVAL_SPLITS:
        return False, "derived from an evaluation split: training on it would leak the evaluation set (G1/G2)"
    h = candidate.get("content_hash")
    if h and h in (frozen if frozen is not None else frozen_hashes()):
        return False, "content hash matches a frozen item (leakage into frozen, G2)"
    # P7-06: changing knowledge must never enter a training manifest
    from nawa.memory.mutability import mutability_reasons
    m_reasons = mutability_reasons(candidate)
    if m_reasons:
        return False, f"{'/'.join(m_reasons)}: changing or unknown knowledge is not train-eligible (P7-06)"
    g2 = gate_status("G2", roadmap)
    if g2 != "DONE":
        return False, f"G2 is {g2}: no training data before G2 closes (ADR-0005 D2)"
    return True, "verified, not evaluation-derived, no frozen hash, mutability ok, G2 closed"


def verify_atlas_record(rec: dict[str, Any]) -> VerificationResult:
    """Re-express a P1-08 Atlas record in P2-02 terms, without re-running anything.

    P1-08 records carry their own deterministic re-scoring. They stay ``verified`` only if that
    method is recorded; they are always evaluation-derived, so :func:`train_eligibility` blocks them.
    """
    method = "deterministic_rescore (P1-08)"
    ok = rec.get("status") == "verified" and str(rec.get("verification_method") or "").startswith("deterministic:")
    status = "verified" if ok else "unverified"
    reason = ("P1-08 deterministic re-scoring is recorded" if ok
              else "no recorded deterministic verification on the Atlas record")
    return VerificationResult(str(rec.get("id")), method, status, reason, {"suite": rec.get("suite")}, "p1-08")


# ---------------------------------------------------------------------------------------------------
# synthetic benchmark (EXP record): known-truth candidates, pre-registered criteria
# ---------------------------------------------------------------------------------------------------

# Registered before the first run, not tuned afterwards.
CRITERIA = {"false_verified": 0, "status_accuracy": 1.0}
BENCH_LICENSE = "NAWA-synthetic-bench (code-generated, test fixture only)"


def bench_candidates(seed: int = 2026, n: int = 20) -> list[tuple[dict[str, Any], str]]:
    """(candidate, expected_status) pairs generated by code. No external data."""
    rng = random.Random(seed)
    out: list[tuple[dict[str, Any], str]] = []

    def add(kind: str, i: int, cand: dict[str, Any], expected: str) -> None:
        cand.setdefault("producer", "bench-producer")
        cand["id"] = f"BENCH-{kind}-{i:03d}"
        out.append((cand, expected))

    for i in range(n):
        a, b, c = rng.randint(2, 999), rng.randint(2, 999), rng.randint(2, 30)
        expr = f"({a} + {b}) * {c} - {a} // {c}"
        truth = (a + b) * c - a // c
        add("calc-ok", i, {"method": "calculation", "claim": expr,
                           "evidence": {"expression": expr, "claimed": str(truth)}}, "verified")
        add("calc-bad", i, {"method": "calculation", "claim": expr,
                            "evidence": {"expression": expr, "claimed": str(truth + rng.choice([-7, -1, 1, 3, 10]))}},
            "rejected")
        ar = normalize_digits(str(a)).translate(str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩"))
        add("calc-ar", i, {"method": "calculation", "claim": f"{ar} × {c}",
                           "evidence": {"expression": f"{ar} × {c}", "claimed": str(a * c)}}, "verified")
        add("calc-unsafe", i, {"method": "calculation", "claim": "x",
                               "evidence": {"expression": f"__import__('os').getpid() + {a}", "claimed": "1"}},
            "unverified")

    for i in range(n // 4):
        k = rng.randint(2, 9)
        good = f"def f(x):\n    return x * {k}\n"
        bad = f"def f(x):\n    return x * {k} + 1\n"
        tests = f"assert f(3) == {3 * k}\nassert f(0) == 0\n"
        add("exec-ok", i, {"method": "execution", "evidence": {"code": good, "tests": tests, "tests_author": "bench-tests"}},
            "verified")
        add("exec-bad", i, {"method": "execution", "evidence": {"code": bad, "tests": tests, "tests_author": "bench-tests"}},
            "rejected")
        add("exec-self", i, {"method": "execution",
                             "evidence": {"code": good, "tests": tests, "tests_author": "bench-producer"}}, "unverified")

    for i in range(n // 2):
        city, river = rng.randint(1, 500), rng.randint(1, 60)
        text = f"في هذا النص الاصطناعي تقع المدينة رقم {city} على النهر رقم {river}، وعدد جسورها {rng.randint(2, 40)}."
        quote = f"تقع المدينة رقم {city} على النهر رقم {river}"
        base = {"source_id": f"synthetic-{i}", "source_text": text, "source_sha256": sha256_text(text),
                "license": BENCH_LICENSE, "quote": quote, "answer": str(river)}
        add("src-ok", i, {"method": "licensed_source", "evidence": dict(base)}, "verified")
        add("src-wrong-answer", i, {"method": "licensed_source", "evidence": {**base, "answer": str(river + 61)}},
            "rejected")
        add("src-fake-quote", i, {"method": "licensed_source",
                                  "evidence": {**base, "quote": f"تقع المدينة رقم {city} على النهر رقم {river + 61}",
                                               "answer": str(river + 61)}}, "rejected")
        add("src-tampered", i, {"method": "licensed_source", "evidence": {**base, "source_text": text + " "}},
            "unverified")
        add("src-unlicensed", i, {"method": "licensed_source", "evidence": {**base, "license": "unknown"}},
            "unverified")

    for i in range(n // 4):
        rev = {"reviewer": f"human:reviewer-{i}", "date": "2026-10-01"}
        add("exp-accept", i, {"method": "expert_review", "evidence": {**rev, "decision": "accept"}}, "verified")
        add("exp-reject", i, {"method": "expert_review", "evidence": {**rev, "decision": "reject"}}, "rejected")
        add("exp-model", i, {"method": "expert_review",
                             "evidence": {"reviewer": "model:provider/x", "decision": "accept", "date": "2026-10-01"}},
            "unverified")
        add("exp-self", i, {"method": "expert_review",
                            "evidence": {"reviewer": "human:bench-producer", "decision": "accept", "date": "2026-10-01"}},
            "unverified")
    return out


def run_bench(seed: int = 2026, n: int = 20) -> dict[str, Any]:
    cfg = load_config()
    cfg = {**cfg, "approved_licenses": [BENCH_LICENSE]}  # fixture-only license, never written to the config
    pairs = bench_candidates(seed, n)
    confusion: dict[str, dict[str, int]] = {s: {t: 0 for t in STATUSES} for s in STATUSES}
    mismatches = []
    eligible = 0
    for cand, expected in pairs:
        res = verify(cand, cfg)
        confusion[expected][res.status] += 1
        if res.status != expected:
            mismatches.append({"id": cand["id"], "expected": expected, "got": res.status, "reason": res.reason})
        eligible += train_eligibility(cand, res)[0]
    total = len(pairs)
    false_verified = sum(confusion[e]["verified"] for e in STATUSES if e != "verified")
    acc = (total - len(mismatches)) / total
    passed = false_verified <= CRITERIA["false_verified"] and acc >= CRITERIA["status_accuracy"]
    return {"seed": seed, "n": n, "total": total, "status_accuracy": acc, "false_verified": false_verified,
            "train_eligible": eligible, "confusion_expected_to_got": confusion, "mismatches": mismatches,
            "criteria": CRITERIA, "passed": passed}


def main() -> None:
    ap = argparse.ArgumentParser(prog="python -m nawa.data_verify")
    sub = ap.add_subparsers(dest="cmd", required=True)
    chk = sub.add_parser("check")
    chk.add_argument("path", type=Path)
    chk.add_argument("--out", type=Path, required=True)
    bn = sub.add_parser("bench")
    bn.add_argument("--seed", type=int, default=2026)
    bn.add_argument("--n", type=int, default=20)
    a = ap.parse_args()
    if a.cmd == "bench":
        print(json.dumps(run_bench(a.seed, a.n), ensure_ascii=False, indent=2))
        return
    if a.out.exists():
        raise SystemExit(f"{a.out} exists; results are written to a new file, never overwritten")
    cfg = load_config()
    with a.path.open(encoding="utf-8") as fh:
        cands = [json.loads(line) for line in fh if line.strip()]
    a.out.parent.mkdir(parents=True, exist_ok=True)
    counts = {s: 0 for s in STATUSES}
    with a.out.open("w", encoding="utf-8") as fh:
        for c in cands:
            r = verify(c, cfg)
            ok, why = train_eligibility(c, r)
            counts[r.status] += 1
            fh.write(json.dumps({**r.to_dict(), "train_eligible": ok, "train_block_reason": None if ok else why},
                                ensure_ascii=False, sort_keys=True) + "\n")
    print(f"{len(cands)} candidates -> {a.out}: {counts}")


if __name__ == "__main__":
    main()
