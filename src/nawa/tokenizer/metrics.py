"""P3-02 measurement of tokenizer candidates on code-generated held-out text.

Reported per candidate: compression (bytes/token, chars/token, tokens/word) on Arabic, English, code,
Arabic-English mixed and rare Unicode; sequence length for fixed-size Arabic documents; morpheme-boundary
precision/recall/F1 on derived Arabic words with known segmentation; token inflation on noisy Arabic
(tashkeel, tatweel, typos, letter repeats, Arabizi); byte-fallback share; and correctness: exact
round-trip everywhere, deterministic training, save/load identity.

The correctness checks are pass/fail criteria. The comparative numbers are evidence for P3-03, which
needs a licensed real corpus before any choice (ADR-0006); this module never ranks or selects.

    python -m nawa.tokenizer.metrics --out-dir <new dir>
"""

from __future__ import annotations

import argparse
import json
import statistics
import tempfile
import time
from pathlib import Path
from typing import Any

from nawa.config import load_yaml
from nawa.tokenizer import Tokenizer, fingerprint, load, save
from nawa.tokenizer import corpus as C
from nawa.tokenizer.bpe import BPETokenizer
from nawa.tokenizer.byte import ByteTokenizer
from nawa.tokenizer.unigram import UnigramTokenizer

REPO = Path(__file__).resolve().parents[3]
CONFIG = REPO / "configs" / "tokenizer.yaml"
CRITERIA = {"roundtrip_rate": 1.0, "deterministic_training": True, "save_load_identical": True,
            "vocab_within_target": True, "learned_beats_bytes_on_arabic": True}


def load_config(path: Path = CONFIG) -> dict[str, Any]:
    cfg = load_yaml(path)
    if cfg.get("schema_version") != 1:
        raise ValueError(f"{path}: unsupported schema_version")
    return cfg


def train_candidate(spec: dict[str, Any], texts: list[str], vocab_size: int) -> Tokenizer:
    if spec["type"] == "byte":
        return ByteTokenizer()
    cls = {"bpe": BPETokenizer, "unigram": UnigramTokenizer}[spec["type"]]
    return cls.train(texts, vocab_size, pretok=spec["pretok"], name=spec["name"])


def token_char_boundaries(tok: Tokenizer, text: str) -> set[int]:
    """Character offsets where a token ends (excluding the end of text). Ends inside a character are skipped."""
    ids = tok.encode(text)
    raw = [tok.decode([i]).encode("utf-8") if _decodable(tok, i) else None for i in ids]
    data = text.encode("utf-8")
    char_at_byte = {}
    b = 0
    for ci, ch in enumerate(text):
        char_at_byte[b] = ci
        b += len(ch.encode("utf-8"))
    out, pos = set(), 0
    for i, r in zip(ids, raw):
        pos += len(r) if r is not None else _token_len(tok, i)
        if pos < len(data) and pos in char_at_byte:
            out.add(char_at_byte[pos])
    return out


def _decodable(tok: Tokenizer, i: int) -> bool:
    try:
        tok.decode([i])
        return True
    except UnicodeDecodeError:
        return False


def _token_len(tok: Tokenizer, i: int) -> int:
    if isinstance(tok, BPETokenizer):
        return len(tok.token_bytes[i])
    if isinstance(tok, UnigramTokenizer):
        return 1 if i < 256 else len(tok.piece_of[i - 256].encode("utf-8"))
    return 1


def compression(tok: Tokenizer, docs: list[str]) -> dict[str, float]:
    ids = [tok.encode(d) for d in docs]
    n_tok = sum(len(x) for x in ids)
    n_bytes = sum(len(d.encode("utf-8")) for d in docs)
    n_chars = sum(len(d) for d in docs)
    n_words = sum(len(d.split()) for d in docs)
    fallback = sum(1 for x in ids for i in x if i < 256)
    rt = sum(tok.decode(x) == d for x, d in zip(ids, docs)) / len(docs)
    return {"bytes_per_token": round(n_bytes / n_tok, 4), "chars_per_token": round(n_chars / n_tok, 4),
            "tokens_per_word": round(n_tok / n_words, 4), "byte_token_share": round(fallback / n_tok, 4),
            "roundtrip_rate": rt}


def morphology(tok: Tokenizer, words: list[C.Word]) -> dict[str, float]:
    tp = fp = fn = 0
    for w in words:
        gold = w.boundaries()
        pred = token_char_boundaries(tok, w.text)
        tp += len(gold & pred)
        fp += len(pred - gold)
        fn += len(gold - pred)
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return {"boundary_precision": round(p, 4), "boundary_recall": round(r, 4),
            "boundary_f1": round(2 * p * r / (p + r), 4) if p + r else 0.0}


def noise(tok: Tokenizer, pairs: list[tuple[str, str, str]]) -> dict[str, Any]:
    by: dict[str, list[float]] = {}
    rt = 0
    for kind, clean, noisy in pairs:
        a, b = tok.encode(clean), tok.encode(noisy)
        rt += tok.decode(b) == noisy
        by.setdefault(kind, []).append(len(b) / len(a))
    return {"inflation": {k: round(statistics.mean(v), 4) for k, v in sorted(by.items())},
            "roundtrip_rate": rt / len(pairs)}


def seq_length(tok: Tokenizer, docs: list[str]) -> dict[str, float]:
    lens = sorted(len(tok.encode(d)) for d in docs)
    return {"mean": round(statistics.mean(lens), 2), "p95": lens[int(0.95 * (len(lens) - 1))], "max": lens[-1]}


def heldout(cfg: dict[str, Any]) -> dict[str, Any]:
    s, h = cfg["heldout_seed"], cfg["heldout"]
    n = h["docs_per_category"]
    seq = [d[: h["seq_chars"]] for d in C.arabic(s + 50, h["seq_docs"], sentences=40)]
    return {"categories": {"arabic": C.arabic(s, n), "english": C.english(s + 1, n), "code": C.code(s + 2, n),
                           "mixed": C.mixed(s + 3, n), "rare_unicode": C.rare_unicode(s + 4, n)},
            "morph": C.morph_words(s + 5, h["morph_words"]), "noisy": C.noisy_pairs(s + 6, h["noisy_pairs"]),
            "seq": seq}


def evaluate(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    train = C.training_corpus(cfg["train_seed"])
    ho = heldout(cfg)
    train_set = set(train)
    leaked = sum(d in train_set for docs in ho["categories"].values() for d in docs)
    results: dict[str, Any] = {}
    for spec in cfg["candidates"]:
        t0 = time.perf_counter()
        tok = train_candidate(spec, train, cfg["vocab_size"])
        secs = time.perf_counter() - t0
        again = train_candidate(spec, train, cfg["vocab_size"])
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "tok.json"
            save(tok, p)
            loaded = load(p)
        sample = ho["categories"]["arabic"][:10] + ho["categories"]["rare_unicode"][:10]
        same_io = fingerprint(loaded) == fingerprint(tok) and all(loaded.encode(x) == tok.encode(x) for x in sample)
        comp = {c: compression(tok, docs) for c, docs in ho["categories"].items()}
        nz = noise(tok, ho["noisy"])
        results[spec["name"]] = {
            "type": spec["type"], "pretok": spec.get("pretok"), "vocab_size": tok.vocab_size,
            "fingerprint": fingerprint(tok)[:16], "train_seconds": round(secs, 2),
            "deterministic_training": fingerprint(again) == fingerprint(tok), "save_load_identical": same_io,
            "compression": comp, "morphology": morphology(tok, ho["morph"]), "noise": nz,
            "seq_length_2000_chars": seq_length(tok, ho["seq"]),
            "roundtrip_rate": min([v["roundtrip_rate"] for v in comp.values()] + [nz["roundtrip_rate"]]),
        }
    byte_ar = results["byte"]["compression"]["arabic"]["bytes_per_token"] if "byte" in results else 1.0
    checks = {
        "roundtrip_rate": min(r["roundtrip_rate"] for r in results.values()),
        "deterministic_training": all(r["deterministic_training"] for r in results.values()),
        "save_load_identical": all(r["save_load_identical"] for r in results.values()),
        "vocab_within_target": all(r["vocab_size"] <= max(256, cfg["vocab_size"]) for r in results.values()),
        "learned_beats_bytes_on_arabic": all(r["compression"]["arabic"]["bytes_per_token"] > byte_ar
                                             for n, r in results.items() if r["type"] != "byte"),
    }
    passed = all(checks[k] == v if isinstance(v, bool) else checks[k] >= v for k, v in CRITERIA.items())
    return {"config": {k: cfg[k] for k in ("vocab_size", "train_seed", "heldout_seed")},
            "train_corpus": {"docs": len(train), "bytes": sum(len(t.encode("utf-8")) for t in train)},
            "heldout_docs_in_train": leaked, "results": results, "checks": checks, "criteria": CRITERIA,
            "passed": passed and leaked == 0,
            "selection": "none: P3-03 needs a licensed real corpus (ADR-0006, OD-03)"}


def main() -> None:
    ap = argparse.ArgumentParser(prog="python -m nawa.tokenizer.metrics")
    ap.add_argument("--out-dir", type=Path, default=None)
    a = ap.parse_args()
    rep = evaluate()
    text = json.dumps(rep, ensure_ascii=False, indent=2)
    if a.out_dir:
        if a.out_dir.exists() and any(a.out_dir.iterdir()):
            raise SystemExit(f"{a.out_dir} is not empty; reports go to a new directory")
        a.out_dir.mkdir(parents=True, exist_ok=True)
        (a.out_dir / "tokenizer_report.json").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
