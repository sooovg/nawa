"""Preference pairs: grounded answer versus hallucinated answer (ROADMAP P2-04, ADR-0005).

Scope now (ADR-0005): the schema, the builder, and the checker. Real pairs need real model outputs
(P2-01 or P5); `from_model_outputs` is the entry point for them and is tested only on fixed strings.
The synthetic builder derives pairs from P2-03 abstention twins, so every rejected answer has a known,
deterministically checkable failure from `docs/failure_taxonomy.md`:

* answerable prompt: FT-07 entity conflation (the distractor's value, citing the distractor sentence),
  FT-01 fabricated source (the right value citing a sentence that does not exist), FT-12 unsupported
  citation (the right value citing a sentence that does not support it), FT-13 over-abstention,
  FT-02 wrong number (numeric attributes only).
* unanswerable prompt: FT-14 missed abstention (the distractor's value), FT-14 invented value.

`check_pair` re-derives everything from the prompt and gold, so a mislabeled or swapped pair fails.
Nothing here is training data: every pair is `train_eligible: false`.

    python -m nawa.data.preference bench --seed 2026
"""

from __future__ import annotations

import argparse
import json
import random
import re
from pathlib import Path
from typing import Any

from nawa.data import twins as tw
from nawa.evaluation.normalize import contains, is_abstention

REPO = Path(__file__).resolve().parents[3]
PROCESSING_VERSION = "p2-04.1"
SOURCE = "synthetic:p2-04-from-p2-03-twins"
TRAIN_BLOCK = "preference pairs: not verified by a P2-02 method and G2 is open (ADR-0005 D2)"
NUMERIC = {"built", "length"}


def taxonomy_codes(path: Path = REPO / "docs" / "failure_taxonomy.md") -> set[str]:
    return set(re.findall(r"^\| (FT-\d\d) \|", path.read_text(encoding="utf-8"), flags=re.M))


def _context(rec: dict[str, Any]) -> list[str]:
    return tw.parse_user(tw._msg(rec, "user"))[0]


def _cites(text: str) -> list[int]:
    return [int(x) for x in re.findall(r"\[(\d+)\]", text)]


def judge(response: str, prompt_rec: dict[str, Any]) -> dict[str, Any]:
    """Deterministic grading of one response to a twin prompt: correct, or the first failure that applies."""
    g = prompt_rec["gold"]
    ctx = _context(prompt_rec)
    answerable = prompt_rec["kind"] == "answerable"
    cites = _cites(response)
    abst = is_abstention(response)
    if not answerable:
        if abst and not cites and not contains(response, g["distractor_value"]):
            return {"correct": True, "failure": None}
        return {"correct": False, "failure": "FT-14"}
    if abst:
        return {"correct": False, "failure": "FT-13"}
    if contains(response, g["distractor_value"]) and not contains(response, g["answer"]):
        return {"correct": False, "failure": "FT-07"}
    if not contains(response, g["answer"]):
        return {"correct": False, "failure": "FT-02" if g["attr"] in NUMERIC else "FT-12"}
    if not cites:
        return {"correct": False, "failure": "FT-12"}
    if any(not 1 <= k <= len(ctx) for k in cites):
        return {"correct": False, "failure": "FT-01"}
    if not any(g["entity"] in ctx[k - 1] and contains(ctx[k - 1], g["answer"]) for k in cites):
        return {"correct": False, "failure": "FT-12"}
    return {"correct": True, "failure": None}


def _pair(prompt_rec: dict[str, Any], chosen: str, rejected: str, failure: str, n: int) -> dict[str, Any]:
    return {
        "id": f"{prompt_rec['id']}-p{n}", "twin_id": prompt_rec["twin_id"], "prompt_id": prompt_rec["id"],
        "prompt": [m for m in prompt_rec["messages"] if m["role"] != "assistant"],
        "gold": prompt_rec["gold"], "kind": prompt_rec["kind"],
        "chosen": chosen, "rejected": rejected, "rejected_failure": failure,
        "source": SOURCE, "license": tw.LICENSE, "processing_version": PROCESSING_VERSION,
        "train_eligible": False, "train_block_reason": TRAIN_BLOCK,
    }


def _wrong_number(rng: random.Random, value: str, context: list[str]) -> str:
    """A nearby number that appears nowhere in the context, so the failure is FT-02 and not FT-07
    (EXP-0020: a random offset once equalled the distractor's value)."""
    v = int(value)
    while True:
        w = str(v + rng.choice([-1, 1]) * rng.randint(1, 9))
        if not any(contains(s, w) for s in context):
            return w


def build_from_twins(rng: random.Random, a: dict[str, Any], u: dict[str, Any]) -> list[dict[str, Any]]:
    g = a["gold"]
    ctx = _context(a)
    k = g["support"]
    dk = next(i for i, s in enumerate(ctx, start=1) if g["distractor"] in s and contains(s, g["distractor_value"]))
    other = next(i for i, s in enumerate(ctx, start=1) if i not in (k, dk))
    chosen_a, chosen_u = tw._msg(a, "assistant"), tw._msg(u, "assistant")
    rejected = [
        (a, chosen_a, f"{g['distractor_value']} [{dk}]", "FT-07"),
        (a, chosen_a, f"{g['answer']} [{len(ctx) + rng.randint(1, 5)}]", "FT-01"),
        (a, chosen_a, f"{g['answer']} [{other}]", "FT-12"),
        (a, chosen_a, chosen_u, "FT-13"),
        (u, chosen_u, f"{g['distractor_value']} [{dk}]", "FT-14"),
        (u, chosen_u, f"{g['answer']}", "FT-14"),  # the value that was removed: a guess from nowhere
    ]
    if g["attr"] in NUMERIC:
        rejected.append((a, chosen_a, f"{_wrong_number(rng, g['answer'], ctx)} [{k}]", "FT-02"))
    return [_pair(p, c, r, f, i) for i, (p, c, r, f) in enumerate(rejected)]


def _prompt_rec(pair: dict[str, Any]) -> dict[str, Any]:
    return {"id": pair["prompt_id"], "kind": pair["kind"], "gold": pair["gold"], "messages": pair["prompt"]}


def check_pair(pair: dict[str, Any], codes: set[str] | None = None) -> list[str]:
    codes = taxonomy_codes() if codes is None else codes
    p: list[str] = []
    for k in ("id", "prompt", "chosen", "rejected", "rejected_failure", "source", "license", "processing_version"):
        if not pair.get(k):
            p.append(f"missing {k}")
    if p:
        return p
    if pair["rejected_failure"] not in codes:
        p.append(f"unknown failure code {pair['rejected_failure']}")
    if pair["chosen"].strip() == pair["rejected"].strip():
        p.append("chosen equals rejected")
    if [m["role"] for m in pair["prompt"]][-1:] != ["user"]:
        p.append("prompt must end with a user turn")
    pr = _prompt_rec(pair)
    c, r = judge(pair["chosen"], pr), judge(pair["rejected"], pr)
    if not c["correct"]:
        p.append(f"chosen is not correct ({c['failure']})")
    if r["correct"]:
        p.append("rejected is correct")
    elif r["failure"] != pair["rejected_failure"]:
        p.append(f"rejected failure is {r['failure']}, labeled {pair['rejected_failure']}")
    if pair.get("train_eligible") is not False:
        p.append("pair marked train_eligible")
    return p


def from_model_outputs(prompt_rec: dict[str, Any], outputs: list[tuple[str, str]]) -> dict[str, Any] | None:
    """Real-output entry point (P2-01/P5). `outputs` is [(model_id, text)]. Returns a pair only when one
    output is judged correct and another fails; the first of each in input order. Otherwise None, never a guess."""
    good = [(m, t) for m, t in outputs if judge(t, prompt_rec)["correct"]]
    bad = [(m, t, judge(t, prompt_rec)["failure"]) for m, t in outputs if not judge(t, prompt_rec)["correct"]]
    if not good or not bad:
        return None
    pair = _pair(prompt_rec, good[0][1], bad[0][1], bad[0][2], 0)
    pair.update(source="model_output", chosen_model=good[0][0], rejected_model=bad[0][0])
    return pair


def build(n: int, seed: int) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    out: list[dict[str, Any]] = []
    for a, u in tw.pairs(tw.build(n, seed)):
        out.extend(build_from_twins(rng, a, u))
    return out


# Pre-registered criteria (set before the first run of this benchmark).
CRITERIA = {"valid_pass_rate": 1.0, "corruption_catch_rate": 1.0, "eval_scorer_chosen_correct": 1.0,
            "eval_scorer_rejected_wrong": 1.0, "model_output_selection_accuracy": 1.0,
            "eval_ngram_overlap_pairs": 0, "train_eligible_pairs": 0}


def corruptions(pair: dict[str, Any]) -> dict[str, dict[str, Any]]:
    other = {"FT-07": "FT-02", "FT-01": "FT-07", "FT-12": "FT-01", "FT-13": "FT-14", "FT-14": "FT-13", "FT-02": "FT-12"}
    return {
        "swapped": {**pair, "chosen": pair["rejected"], "rejected": pair["chosen"]},
        "wrong_label": {**pair, "rejected_failure": other[pair["rejected_failure"]]},
        "unknown_code": {**pair, "rejected_failure": "FT-99"},
        "identical": {**pair, "rejected": pair["chosen"]},
        "train_eligible": {**pair, "train_eligible": True},
        "no_license": {**pair, "license": ""},
    }


def _eval_score(pair: dict[str, Any], text: str) -> bool:
    from nawa.evaluation.schema import Item
    from nawa.evaluation.suites import abstention

    g, ans = pair["gold"], pair["kind"] == "answerable"
    item = Item(suite="abstention", split="dev", messages=pair["prompt"],
                gold={"answerable": ans, "answers": [g["answer"]] if ans else [],
                      "distractor_answers": [g["distractor_value"]], "support": g["support"]})
    return bool(abstention.score(item, text)["correct"])


def run_bench(seed: int = 2026, n: int = 200) -> dict[str, Any]:
    from nawa.data import load_config
    from nawa.data.decontam import ContaminationIndex

    codes = taxonomy_codes()
    pairs = build(n, seed)
    valid = sum(1 for p in pairs if not check_pair(p, codes))
    caught = total = 0
    for p in pairs:
        for x in corruptions(p).values():
            total += 1
            caught += bool(check_pair(x, codes))
    chosen_ok = sum(_eval_score(p, p["chosen"]) for p in pairs) / len(pairs)
    # The P1-02 scorer does not check citations, so FT-01/FT-12 rejections can look correct to it;
    # only failure types that the evaluation suite itself grades are counted here.
    graded = [p for p in pairs if p["rejected_failure"] in {"FT-07", "FT-13", "FT-14", "FT-02"}]
    rejected_wrong = sum(not _eval_score(p, p["rejected"]) for p in graded) / len(graded)
    rng = random.Random(seed + 1)
    sel_ok = sel_n = 0
    for a, u in tw.pairs(tw.build(min(n, 50), seed + 1)):
        for rec in (a, u):
            right = tw._msg(rec, "assistant")
            wrong = f"{rec['gold']['distractor_value']} [1]"
            outs = [("m-wrong", wrong), ("m-right", right)]
            rng.shuffle(outs)
            got = from_model_outputs(rec, outs)
            sel_n += 1
            sel_ok += bool(got and got["chosen"] == right and got["rejected"] == wrong)
    cfg = load_config()["decontamination"]
    idx = ContaminationIndex.build(cfg["ngram_words"], cfg["public_splits"])
    overlap = sum(1 for p in pairs if idx.check("\n".join([*(m["content"] for m in p["prompt"]), p["chosen"],
                                                            p["rejected"]]))[0])
    m = {"pairs": len(pairs), "valid_pass_rate": valid / len(pairs), "corruption_catch_rate": caught / total,
         "eval_scorer_chosen_correct": chosen_ok, "eval_scorer_rejected_wrong": rejected_wrong,
         "model_output_selection_accuracy": sel_ok / sel_n, "eval_ngram_overlap_pairs": overlap,
         "train_eligible_pairs": sum(1 for p in pairs if p["train_eligible"]),
         "failure_counts": {c: sum(1 for p in pairs if p["rejected_failure"] == c)
                            for c in sorted({p["rejected_failure"] for p in pairs})}}
    c = CRITERIA
    passed = all(m[k] >= c[k] for k in ("valid_pass_rate", "corruption_catch_rate", "eval_scorer_chosen_correct",
                                        "eval_scorer_rejected_wrong", "model_output_selection_accuracy")) and \
        m["eval_ngram_overlap_pairs"] <= c["eval_ngram_overlap_pairs"] and m["train_eligible_pairs"] <= c["train_eligible_pairs"]
    return {"seed": seed, "n_twins": n, "metrics": m, "criteria": CRITERIA, "passed": passed}


def main() -> None:
    ap = argparse.ArgumentParser(prog="python -m nawa.data.preference")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--n", type=int, required=True)
    b.add_argument("--seed", type=int, required=True)
    b.add_argument("--out", type=Path, required=True)
    t = sub.add_parser("bench")
    t.add_argument("--seed", type=int, default=2026)
    t.add_argument("--n", type=int, default=200)
    a = ap.parse_args()
    if a.cmd == "bench":
        print(json.dumps(run_bench(a.seed, a.n), ensure_ascii=False, indent=2))
        return
    if a.out.exists():
        raise SystemExit(f"{a.out} exists; outputs are written to a new file, never overwritten")
    pairs = build(a.n, a.seed)
    codes = taxonomy_codes()
    bad = [(p["id"], pr) for p in pairs if (pr := check_pair(p, codes))]
    if bad:
        raise SystemExit(f"refusing to write malformed pairs: {bad[:3]}")
    with a.out.open("w", encoding="utf-8") as fh:
        for p in pairs:
            fh.write(json.dumps(p, ensure_ascii=False, sort_keys=True) + "\n")
    print(json.dumps({"pairs": len(pairs), "out": str(a.out)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
