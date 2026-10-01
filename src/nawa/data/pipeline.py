"""P2-05 pipeline: clean -> PII redaction -> language/quality -> license -> decontamination -> dedup ->
provenance stamp. Nothing is silently deleted: every input ends in `kept` or in `dropped` with a reason.
Dropped entries carry the id and reason only (no text), so PII never reaches a report.

    python -m nawa.data.pipeline run in.jsonl --out-dir <dir>
    python -m nawa.data.pipeline bench --seed 2026

Input records: {"id", "text", "source", "license", "domain", "date"}.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import string
from collections import Counter
from pathlib import Path
from typing import Any

from nawa.data import load_config
from nawa.data.clean import BIDI_CONTROLS, ZERO_WIDTH, clean_text
from nawa.data.decontam import ContaminationIndex, eval_texts
from nawa.data.dedup import dedup
from nawa.data.pii import find_pii, iban_ok, luhn_ok, redact, saudi_id_ok
from nawa.data.provenance import INPUT_FIELDS, license_status, text_hash, validate_output
from nawa.data_verify import load_config as load_verification_config

TRAIN_BLOCK = ("cleaned only: training needs P2-02 verification and G2 closed (ADR-0005 D2); "
               "P2-02 train_eligibility() decides")


def approved_licenses() -> list[str]:
    return list(load_verification_config().get("approved_licenses") or [])


def run(records: list[dict[str, Any]], cfg: dict[str, Any] | None = None, approved: list[str] | None = None,
        index: ContaminationIndex | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    approved = approved_licenses() if approved is None else approved
    dc = cfg["decontamination"]
    index = index or ContaminationIndex.build(dc["ngram_words"], dc["public_splits"])
    q, dd, cl = cfg["quality"], cfg["dedup"], cfg["clean"]
    kept: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    pii_counts: Counter[str] = Counter()
    clean_counts: Counter[str] = Counter()
    seen_ids: set[str] = set()

    def drop(rid: Any, reason: str, detail: str = "") -> None:
        dropped.append({"id": rid, "reason": reason, "detail": detail})

    for r in records:
        missing = [k for k in INPUT_FIELDS if not r.get(k)]
        if missing:
            drop(r.get("id"), "invalid_input", f"missing {missing}")
            continue
        if r["id"] in seen_ids:
            drop(r["id"], "invalid_input", "duplicate id")
            continue
        seen_ids.add(r["id"])
        c = clean_text(r["text"], cl["remove_tatweel"])
        clean_counts.update(c.changes)
        if len(c.text) < cl["min_chars"]:
            drop(r["id"], "too_short")
            continue
        text, spans = redact(c.text, cfg["pii"]["types"])
        pii_counts.update(s.type for s in spans)
        qual = quality_of(text, q, c.flags)
        if qual["score"] < q["min_score"]:
            drop(r["id"], "low_quality", ",".join(qual["flags"]))
            continue
        ok, why = license_status(r["license"], approved)
        if not ok:
            drop(r["id"], "license", why)
            continue
        bad, why = index.check(text, r.get("content_hash"))
        if bad:
            drop(r["id"], "contaminated", why)
            continue
        kept.append({
            "id": r["id"], "text": text, "source": r["source"], "license": r["license"], "domain": r["domain"],
            "date": r["date"], "language": language_of(text), "quality": qual, "hash": text_hash(text),
            "processing_version": cfg["processing_version"],
            "steps": {"clean": c.changes, "pii": dict(Counter(s.type for s in spans))},
            "train_eligible": False, "train_block_reason": TRAIN_BLOCK,
        })
    res = dedup([(k["id"], k["text"]) for k in kept], dd["shingle_words"], dd["num_perm"], dd["bands"],
                dd["jaccard_threshold"], dd["seed"])
    final = []
    for k in kept:
        if k["id"] in res.duplicate_of:
            drop(k["id"], "duplicate", f"{res.kind[k['id']]} of {res.duplicate_of[k['id']]} (J={res.similarity[k['id']]})")
        else:
            validate_output(k, cfg["processing_version"], cfg["languages"])
            final.append(k)
    stats = {"input": len(records), "kept": len(final), "dropped": dict(Counter(d["reason"] for d in dropped)),
             "pii_redacted": dict(pii_counts), "clean_changes": dict(clean_counts),
             "processing_version": cfg["processing_version"]}
    return {"kept": final, "dropped": dropped, "stats": stats}


def quality_of(text: str, q: dict[str, Any], flags: list[str]) -> dict[str, Any]:
    from nawa.data.quality import quality
    r = quality(text, q["max_repeated_line_ratio"], q["max_symbol_ratio"], q["max_char_run"], flags)
    return {"score": r.score, "flags": r.flags, "stats": r.stats}


def language_of(text: str) -> str:
    from nawa.data.quality import language
    return language(text)


# ---------------------------------------------------------------------------------------------------
# Synthetic benchmark with known labels (EXP record). Pre-registered criteria, not tuned afterwards.
# ---------------------------------------------------------------------------------------------------

CRITERIA = {"pii_recall_min": 1.0, "pii_false_positive_docs_max": 0, "dedup_recall_min": 0.95,
            "dedup_precision_min": 1.0, "decontam_recall_min": 1.0, "decontam_false_positive_max": 0,
            "quality_recall_min": 1.0, "quality_false_positive_max": 0, "license_exact": True,
            "invisible_controls_left_max": 0}
BENCH_LICENSE = "NAWA-synthetic-bench (code-generated, test fixture only)"
_LETTERS = "ابتثجحخدذرزسشصضطظعغفقكلمنهوي"


def _vocab(rng: random.Random, size: int = 3000) -> list[str]:
    words: set[str] = set()
    while len(words) < size:
        words.add("".join(rng.choice(_LETTERS) for _ in range(rng.randint(3, 7))))
    return sorted(words)


def _doc(rng: random.Random, vocab: list[str], lo: int = 60, hi: int = 90) -> str:
    return " ".join(rng.choice(vocab) for _ in range(rng.randint(lo, hi)))


def _ar_digits(s: str) -> str:
    return s.translate(str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩"))


def fake_pii(kind: str, rng: random.Random) -> str:
    """Valid-format synthetic PII values (checksums pass). Generated at run time, never stored."""
    if kind == "email":
        return f"user{rng.randint(100, 999)}@example.org"
    if kind == "phone":
        return f"+966 5{rng.randint(0, 9)} {rng.randint(100, 999)} {rng.randint(1000, 9999)}"
    if kind == "ipv4":
        return f"10.{rng.randint(0, 255)}.{rng.randint(0, 255)}.{rng.randint(1, 254)}"
    if kind == "secret":
        alphabet = string.ascii_letters + string.digits
        return "hf_" + "".join(rng.choice(alphabet) for _ in range(34))
    if kind == "card":
        while True:
            n = "4" + "".join(str(rng.randint(0, 9)) for _ in range(15))
            if luhn_ok(n):
                return " ".join(n[i:i + 4] for i in range(0, 16, 4))
    if kind == "national_id":
        while True:
            n = rng.choice("12") + "".join(str(rng.randint(0, 9)) for _ in range(9))
            if saudi_id_ok(n):
                return _ar_digits(n) if rng.random() < 0.5 else n
    if kind == "iban":
        while True:
            body = "".join(str(rng.randint(0, 9)) for _ in range(22))
            chk = 98 - int("".join(str(int(c, 36)) for c in body + "SA00")) % 97
            iban = f"SA{chk:02d}{body}"
            if iban_ok(iban):
                return " ".join(iban[i:i + 4] for i in range(0, len(iban), 4))
    raise ValueError(kind)


PII_KINDS = ("email", "phone", "ipv4", "secret", "card", "national_id", "iban")


def bench_corpus(seed: int = 2026, n_base: int = 200, n_each: int = 20) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rng = random.Random(seed)
    vocab = _vocab(rng)
    recs: list[dict[str, Any]] = []
    labels: dict[str, Any] = {"pii": {}, "dup": set(), "contam": set(), "lowq": set(), "unlicensed": set(),
                              "controls": set(), "base": set()}

    def add(kind: str, i: int, text: str, license_: str = BENCH_LICENSE) -> str:
        rid = f"{kind}-{i:04d}"
        recs.append({"id": rid, "text": text, "source": f"synthetic:{kind}", "license": license_,
                     "domain": "synthetic", "date": "2026-10-01"})
        return rid

    base = []
    for i in range(n_base):
        t = _doc(rng, vocab)
        base.append(t)
        labels["base"].add(add("base", i, t))
    for i in range(n_each):
        src = base[i]
        labels["dup"].add(add("exact", i, "  " + src.replace(" ", "  ") + "\n"))
        words = src.split()
        j = rng.randrange(len(words))
        words[j] = rng.choice(vocab)
        labels["dup"].add(add("near", i, " ".join(words)))
    dev = [t for t in eval_texts(("dev",)) if len(t.split()) >= 14]
    for i in range(n_each):
        sl = rng.choice(dev).split()
        k = rng.randrange(0, len(sl) - 12 + 1)
        labels["contam"].add(add("contam", i, _doc(rng, vocab, 30, 40) + " " + " ".join(sl[k:k + 12]) + " " +
                                 _doc(rng, vocab, 30, 40)))
    for i in range(n_each):
        junk = rng.choice(["#$%&*@!" * 20 + " " + _doc(rng, vocab, 5, 8),
                           "\n".join([_doc(rng, vocab, 6, 8)] * 8),
                           _doc(rng, vocab, 20, 30) + " " + "ههههه" * 10])
        labels["lowq"].add(add("lowq", i, junk))
    for i in range(n_each):
        labels["unlicensed"].add(add("unlic", i, _doc(rng, vocab), license_="unknown"))
    for i in range(n_each):
        words = _doc(rng, vocab).split()
        for _ in range(4):
            p = rng.randrange(len(words))
            words[p] = rng.choice(BIDI_CONTROLS + ZERO_WIDTH) + words[p]
        labels["controls"].add(add("ctrl", i, " ".join(words)))
    for kind in PII_KINDS:
        for i in range(n_each):
            words = _doc(rng, vocab).split()
            p = rng.randrange(1, len(words) - 1)
            value = fake_pii(kind, rng)
            words.insert(p, value)
            rid = add(f"pii-{kind}", i, " ".join(words))
            labels["pii"][rid] = kind
    return recs, labels


def run_bench(seed: int = 2026) -> dict[str, Any]:
    recs, lab = bench_corpus(seed)
    out = run(recs, approved=[BENCH_LICENSE])
    kept = {k["id"]: k for k in out["kept"]}
    reason = {d["id"]: d["reason"] for d in out["dropped"]}
    m: dict[str, Any] = {}
    per = {}
    for kind in PII_KINDS:
        ids = [r for r, k in lab["pii"].items() if k == kind]
        per[kind] = sum(1 for r in ids if r in kept and kept[r]["steps"]["pii"].get(kind) == 1) / len(ids)
    m["pii_recall"] = per
    # No PII span on records without injected PII (base, dup, ctrl). Re-run detection on raw text.
    clean_ids = lab["base"] | lab["dup"] | lab["controls"] | lab["unlicensed"]
    m["pii_false_positive_docs"] = sum(1 for r in recs if r["id"] in clean_ids and find_pii(r["text"]))
    dup_found = {r for r, why in reason.items() if why == "duplicate"}
    m["dedup_recall"] = len(dup_found & lab["dup"]) / len(lab["dup"])
    m["dedup_precision"] = len(dup_found & lab["dup"]) / len(dup_found) if dup_found else 1.0
    con = {r for r, why in reason.items() if why == "contaminated"}
    m["decontam_recall"] = len(con & lab["contam"]) / len(lab["contam"])
    m["decontam_false_positive"] = len(con - lab["contam"])
    low = {r for r, why in reason.items() if why == "low_quality"}
    m["quality_recall"] = len(low & lab["lowq"]) / len(lab["lowq"])
    m["quality_false_positive"] = len(low - lab["lowq"])
    lic = {r for r, why in reason.items() if why == "license"}
    m["license_exact"] = lic == lab["unlicensed"]
    left = 0
    for r in lab["controls"]:
        if r in kept:
            left += sum(kept[r]["text"].count(c) for c in BIDI_CONTROLS + ZERO_WIDTH)
    m["invisible_controls_left"] = left
    m["controls_kept"] = sum(1 for r in lab["controls"] if r in kept)
    c = CRITERIA
    passed = (min(per.values()) >= c["pii_recall_min"] and m["pii_false_positive_docs"] <= c["pii_false_positive_docs_max"]
              and m["dedup_recall"] >= c["dedup_recall_min"] and m["dedup_precision"] >= c["dedup_precision_min"]
              and m["decontam_recall"] >= c["decontam_recall_min"]
              and m["decontam_false_positive"] <= c["decontam_false_positive_max"]
              and m["quality_recall"] >= c["quality_recall_min"]
              and m["quality_false_positive"] <= c["quality_false_positive_max"]
              and m["license_exact"] == c["license_exact"]
              and m["invisible_controls_left"] <= c["invisible_controls_left_max"]
              and m["controls_kept"] == len(lab["controls"]))
    digest = hashlib.sha256(json.dumps([r["text"] for r in recs], ensure_ascii=False).encode()).hexdigest()[:16]
    return {"seed": seed, "corpus_records": len(recs), "corpus_digest": digest, "stats": out["stats"],
            "metrics": m, "criteria": CRITERIA, "passed": passed}


def main() -> None:
    ap = argparse.ArgumentParser(prog="python -m nawa.data.pipeline")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("path", type=Path)
    r.add_argument("--out-dir", type=Path, required=True)
    b = sub.add_parser("bench")
    b.add_argument("--seed", type=int, default=2026)
    a = ap.parse_args()
    if a.cmd == "bench":
        rep = run_bench(a.seed)
        rep["stats"].pop("clean_changes", None)
        print(json.dumps(rep, ensure_ascii=False, indent=2))
        return
    if a.out_dir.exists() and any(a.out_dir.iterdir()):
        raise SystemExit(f"{a.out_dir} is not empty; outputs go to a new directory, never overwritten")
    with a.path.open(encoding="utf-8") as fh:
        recs = [json.loads(line) for line in fh if line.strip()]
    out = run(recs)
    a.out_dir.mkdir(parents=True, exist_ok=True)
    for name in ("kept", "dropped"):
        with (a.out_dir / f"{name}.jsonl").open("w", encoding="utf-8") as fh:
            for x in out[name]:
                fh.write(json.dumps(x, ensure_ascii=False, sort_keys=True) + "\n")
    (a.out_dir / "stats.json").write_text(json.dumps(out["stats"], ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out["stats"], ensure_ascii=False))


if __name__ == "__main__":
    main()
