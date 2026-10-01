"""Abstention twins builder and checker (ROADMAP P2-03, ADR-0005).

A twin pair shares one question. The answerable twin's context contains the evidence sentence and its
target answers and cites that sentence. The unanswerable twin's context is the same context with the
evidence removed, plus nothing new; its target abstains and says what is missing. A distractor entity
that HAS the asked attribute stays in both contexts, to train against answering from the wrong entity.

Separation from evaluation (RISK-01): the evaluation abstention suite (P1-02) uses towns built from
`nawa.evaluation.synth.SYLLABLES`. Twins here use a different entity type (fictional ships), different
attributes, sentence and question templates, a different system prompt, and names built only from
consonants that never occur in the evaluation syllables, so a twin name cannot equal an evaluation
name. `check_separation` enforces this and the P2-05 n-gram index confirms zero 8-gram overlap.

Code only: nothing here is training data. Every record is `train_eligible: false`; P2-02 decides later,
and its four methods do not cover "synthetic by construction" (recorded as a G2 limitation).

    python -m nawa.data.twins build --n 50 --seed 1 --out twins.jsonl
    python -m nawa.data.twins bench --seed 2026
"""

from __future__ import annotations

import argparse
import copy
import json
import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from nawa.evaluation.normalize import contains, is_abstention
from nawa.evaluation.synth import SYLLABLES

PROCESSING_VERSION = "p2-03.1"
SOURCE = "synthetic:p2-03-twins"
LICENSE = "NAWA-authored synthetic (code-generated 2026-10-01); license per OD-03"
TRAIN_BLOCK = "synthetic twins: not verified by a P2-02 method and G2 is open (ADR-0005 D2)"

SYSTEM_PROMPT = (
    "اعتمد على النص المرفق وحده في الرد. إن وجدت المعلومة فاذكرها ثم ضع رقم الجملة التي تثبتها بين معقوفين. "
    "وإن لم تجدها فقل: غير موجود في السياق، ثم بيّن ما الذي ينقص النص."
)

# Consonants used by evaluation syllables are excluded, so twin names share no consonant with them.
_EVAL_CONSONANTS = {c for ar, _ in SYLLABLES for c in ar if c not in "اوي"}
_TWIN_CONSONANTS = [c for c in "ثحخذصضظعءئ" if c not in _EVAL_CONSONANTS]
_VOWELS = ["ا", "و", "ي", ""]
CARGOES = ["الأقمشة", "الحبوب", "الخشب", "الحديد", "الأدوية", "الزجاج", "الجلود", "البهارات", "الفحم", "الكتب"]
PEOPLE = ["حامد", "صفاء", "عادل", "ضحى", "خديجة", "ظافر", "عائشة", "صالح", "حسين", "ذكرى"]
ATTRS = ("captain", "port", "built", "cargo", "length")
LABELS = {"captain": "اسم ربان", "port": "ميناء", "built": "سنة بناء", "cargo": "حمولة", "length": "طول"}


def _name(rng: random.Random, parts: int = 3) -> str:
    return "".join(rng.choice(_TWIN_CONSONANTS) + rng.choice(_VOWELS) for _ in range(parts))


@dataclass(frozen=True)
class Ship:
    name: str
    captain: str
    port: str
    built: int
    cargo: str
    length: int

    def value(self, attr: str) -> str:
        return str(getattr(self, attr))

    def sentence(self, attr: str) -> str:
        n = self.name
        return {
            "captain": f"يقود السفينة {n} الربان {self.captain}.",
            "port": f"ترسو السفينة {n} عادة في ميناء {self.port}.",
            "built": f"بُنيت السفينة {n} سنة {self.built}.",
            "cargo": f"تنقل السفينة {n} في رحلاتها {self.cargo}.",
            "length": f"يبلغ طول السفينة {n} {self.length} مترًا.",
        }[attr]

    def question(self, attr: str) -> str:
        n = self.name
        return {
            "captain": f"من ربان السفينة {n}؟",
            "port": f"في أي ميناء ترسو السفينة {n}؟",
            "built": f"متى بُنيت السفينة {n}؟",
            "cargo": f"ماذا تنقل السفينة {n}؟",
            "length": f"كم طول السفينة {n}؟",
        }[attr]


def _ship(rng: random.Random, taken: set[str]) -> Ship:
    while True:
        name = _name(rng)
        if name not in taken:
            taken.add(name)
            break
    return Ship(name, rng.choice(PEOPLE), _name(rng, 2), rng.randint(1801, 1989), rng.choice(CARGOES),
                rng.randint(31, 389))


def _user(context_lines: list[str], question: str) -> str:
    ctx = "\n".join(f"[{i}] {s}" for i, s in enumerate(context_lines, start=1))
    return f"النص:\n{ctx}\n\nالمطلوب: {question}"


def parse_user(text: str) -> tuple[list[str], str]:
    head, _, q = text.partition("\n\nالمطلوب: ")
    lines = head.removeprefix("النص:\n").split("\n")
    return [re.sub(r"^\[\d+\] ", "", ln) for ln in lines], q


def build_pair(rng: random.Random, idx: int, taken: set[str] | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    taken = set() if taken is None else taken
    target, distractor = _ship(rng, taken), _ship(rng, taken)
    while distractor.value(attr := rng.choice(ATTRS)) == target.value(attr):
        distractor = _ship(rng, taken)
    others = [a for a in ATTRS if a != attr]
    keep = rng.sample(others, k=rng.randint(2, len(others)))
    sents = [target.sentence(a) for a in keep] + [distractor.sentence(a) for a in rng.sample(ATTRS, 3) if a != attr]
    sents.append(distractor.sentence(attr))
    support = target.sentence(attr)
    full = sents + [support]
    rng.shuffle(full)
    without = [s for s in full if s != support]
    k = full.index(support) + 1
    q = target.question(attr)
    twin_id = f"twin-{idx:05d}-{rng.getrandbits(32):08x}"
    gold = {"attr": attr, "entity": target.name, "answer": target.value(attr), "support_sentence": support,
            "distractor": distractor.name, "distractor_value": distractor.value(attr)}
    common = {"twin_id": twin_id, "source": SOURCE, "license": LICENSE, "processing_version": PROCESSING_VERSION,
              "train_eligible": False, "train_block_reason": TRAIN_BLOCK}
    ans = {"id": f"{twin_id}-a", "kind": "answerable", **common, "gold": {**gold, "support": k}, "messages": [
        {"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": _user(full, q)},
        {"role": "assistant", "content": f"{target.value(attr)} [{k}]"}]}
    missing = f"غير موجود في السياق. النص يذكر السفينة {target.name} لكنه لا يذكر {LABELS[attr]} لها."
    una = {"id": f"{twin_id}-u", "kind": "unanswerable", **common, "gold": {**gold, "support": None}, "messages": [
        {"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": _user(without, q)},
        {"role": "assistant", "content": missing}]}
    return ans, una


def build(n: int, seed: int) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    taken: set[str] = set()
    out: list[dict[str, Any]] = []
    for i in range(n):
        out.extend(build_pair(rng, i, taken))
    return out


def _msg(rec: dict[str, Any], role: str) -> str:
    return next(m["content"] for m in rec["messages"] if m["role"] == role)


def check_pair(a: dict[str, Any], u: dict[str, Any]) -> list[str]:
    """Problems with a twin pair; empty means the pair is well formed."""
    p: list[str] = []
    if (a.get("kind"), u.get("kind")) != ("answerable", "unanswerable") or a.get("twin_id") != u.get("twin_id"):
        return ["kinds or twin_id do not form a pair"]
    g = a["gold"]
    ca, qa = parse_user(_msg(a, "user"))
    cu, qu = parse_user(_msg(u, "user"))
    ra, ru = _msg(a, "assistant"), _msg(u, "assistant")
    if qa != qu:
        p.append("questions differ")
    if _msg(a, "system") != _msg(u, "system"):
        p.append("system prompts differ")
    removed = [s for s in ca if s not in cu]
    if [s for s in cu if s not in ca]:
        p.append("unanswerable context adds sentences")
    if removed != [g["support_sentence"]]:
        p.append("contexts differ by more or less than the evidence sentence")
    k = g.get("support")
    if not isinstance(k, int) or not 1 <= k <= len(ca) or ca[k - 1] != g["support_sentence"]:
        p.append("citation index does not point to the evidence sentence")
    if not contains(g["support_sentence"], g["answer"]):
        p.append("answer is not in the evidence sentence")
    if any(contains(s, g["answer"]) and g["entity"] in s for s in cu):
        p.append("unanswerable context still states the answer for the entity")
    if not contains(ra, g["answer"]) or f"[{k}]" not in ra or is_abstention(ra):
        p.append("answerable target does not answer with the citation")
    if not is_abstention(ru) or re.search(r"\[\d+\]", ru):
        p.append("unanswerable target does not abstain without a citation")
    if contains(ru, g["answer"]) or contains(ru, g["distractor_value"]):
        p.append("unanswerable target leaks a value")
    if g["entity"] not in ru or LABELS[g["attr"]] not in ru:
        p.append("unanswerable target does not say what is missing")
    if not any(g["distractor"] in s and contains(s, g["distractor_value"]) for s in cu):
        p.append("distractor with the asked attribute is missing")
    for r in (a, u):
        if r.get("train_eligible") is not False:
            p.append("record marked train_eligible")
    return p


def check_separation(recs: list[dict[str, Any]]) -> list[str]:
    """Twin entity names must not use any evaluation consonant (so they cannot equal evaluation names)."""
    bad = []
    for r in recs:
        for name in (r["gold"]["entity"], r["gold"]["distractor"]):
            if set(name) & _EVAL_CONSONANTS:
                bad.append(f"{r['id']}: name {name!r} uses an evaluation consonant")
    return bad


def pairs(recs: list[dict[str, Any]]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    by: dict[str, dict[str, dict[str, Any]]] = {}
    for r in recs:
        by.setdefault(r["twin_id"], {})[r["kind"]] = r
    return [(d.get("answerable", {}), d.get("unanswerable", {})) for d in by.values()]


# ---------------------------------------------------------------------------------------------------
# Benchmark: well-formed pairs must pass, every corrupted pair must be caught. Pre-registered criteria.
# ---------------------------------------------------------------------------------------------------

CRITERIA = {"valid_pass_rate": 1.0, "corruption_catch_rate": 1.0, "eval_scorer_agreement": 1.0,
            "decontam_positive_control": 1.0, "eval_ngram_overlap_records": 0,
            "eval_name_collisions": 0, "pii_records": 0, "duplicate_pairs": 0}


def _set_msg(rec: dict[str, Any], role: str, text: str) -> None:
    for m in rec["messages"]:
        if m["role"] == role:
            m["content"] = text


def corruptions(a: dict[str, Any], u: dict[str, Any]) -> dict[str, tuple[dict[str, Any], dict[str, Any]]]:
    g = a["gold"]
    out = {}

    def mk(name: str, fn) -> None:  # noqa: ANN001
        x, y = copy.deepcopy(a), copy.deepcopy(u)
        fn(x, y)
        out[name] = (x, y)

    mk("answer_left_in_unanswerable", lambda x, y: _set_msg(y, "user", _msg(x, "user")))
    wrong = g["support"] - 1 if g["support"] > 1 else g["support"] + 1
    mk("wrong_citation", lambda x, y: _set_msg(x, "assistant", f"{g['answer']} [{wrong}]"))
    mk("answer_without_citation", lambda x, y: _set_msg(x, "assistant", g["answer"]))
    mk("unanswerable_guesses", lambda x, y: _set_msg(y, "assistant", g["distractor_value"]))
    mk("abstain_leaks_answer", lambda x, y: _set_msg(y, "assistant", _msg(y, "assistant") + f" ربما {g['answer']}"))
    mk("abstain_without_reason", lambda x, y: _set_msg(y, "assistant", "غير موجود في السياق."))
    mk("question_changed", lambda x, y: _set_msg(y, "user", _msg(y, "user").replace("المطلوب: ", "المطلوب: هل ")))
    mk("answerable_abstains", lambda x, y: _set_msg(x, "assistant", f"غير موجود في السياق [{g['support']}]"))
    mk("train_eligible_set", lambda x, y: x.__setitem__("train_eligible", True))

    def extra_sentence(x: dict[str, Any], y: dict[str, Any]) -> None:
        cu, q = parse_user(_msg(y, "user"))
        _set_msg(y, "user", _user(cu + ["جملة جديدة لم ترد في التوأم الآخر."], q))
    mk("unanswerable_adds_sentence", extra_sentence)

    def drop_distractor(x: dict[str, Any], y: dict[str, Any]) -> None:
        for r in (x, y):
            c, q = parse_user(_msg(r, "user"))
            c = [s for s in c if not (g["distractor"] in s and contains(s, g["distractor_value"]))]
            _set_msg(r, "user", _user(c, q))
        x["gold"]["support"] = parse_user(_msg(x, "user"))[0].index(g["support_sentence"]) + 1
        _set_msg(x, "assistant", f"{g['answer']} [{x['gold']['support']}]")
    mk("distractor_removed", drop_distractor)
    return out


def eval_scorer_ok(rec: dict[str, Any]) -> bool:
    """The P1-02 abstention scorer must grade the twin's target as correct (same notion of abstaining)."""
    from nawa.evaluation.schema import Item
    from nawa.evaluation.suites import abstention

    g = rec["gold"]
    ans = rec["kind"] == "answerable"
    item = Item(suite="abstention", split="dev", messages=[m for m in rec["messages"] if m["role"] != "assistant"],
                gold={"answerable": ans, "answers": [g["answer"]] if ans else [],
                      "distractor_answers": [g["distractor_value"]], "support": g["support"]})
    return bool(abstention.score(item, _msg(rec, "assistant"))["correct"])


def run_bench(seed: int = 2026, n: int = 200) -> dict[str, Any]:
    from nawa.data import load_config
    from nawa.data.decontam import ContaminationIndex
    from nawa.data.dedup import dedup
    from nawa.data.pii import find_pii

    recs = build(n, seed)
    ps = pairs(recs)
    valid = sum(1 for a, u in ps if not check_pair(a, u))
    caught: dict[str, int] = {}
    for a, u in ps:
        for name, (x, y) in corruptions(a, u).items():
            caught[name] = caught.get(name, 0) + (1 if check_pair(x, y) else 0)
    cfg = load_config()["decontamination"]
    idx = ContaminationIndex.build(cfg["ngram_words"], cfg["public_splits"])
    overlap = sum(1 for r in recs if idx.check("\n".join(m["content"] for m in r["messages"]))[0])
    pii = sum(1 for r in recs if any(find_pii(m["content"]) for m in r["messages"]))
    dd = dedup([(a["id"], _msg(a, "user")) for a, _ in ps], threshold=0.8)
    agree = sum(eval_scorer_ok(r) for r in recs) / len(recs)
    from nawa.evaluation.build import build_public
    controls = build_public()["dev"]["abstention"][:20]
    control = sum(1 for it in controls if idx.check("\n".join(m["content"] for m in it.messages))[0]) / len(controls)
    m = {"pairs": len(ps), "records": len(recs), "valid_pass_rate": valid / len(ps),
         "eval_scorer_agreement": agree, "decontam_positive_control": control,
         "corruption_catch_rate": sum(caught.values()) / (len(ps) * len(caught)),
         "caught_by_corruption": {k: v / len(ps) for k, v in sorted(caught.items())},
         "eval_ngram_overlap_records": overlap, "eval_name_collisions": len(check_separation(recs)),
         "pii_records": pii, "duplicate_pairs": len(dd.duplicate_of),
         "answer_attrs": {a: sum(1 for x, _ in ps if x["gold"]["attr"] == a) for a in ATTRS}}
    c = CRITERIA
    passed = (m["valid_pass_rate"] >= c["valid_pass_rate"] and m["eval_scorer_agreement"] >= c["eval_scorer_agreement"]
              and m["decontam_positive_control"] >= c["decontam_positive_control"] and m["corruption_catch_rate"] >= c["corruption_catch_rate"]
              and all(m[k] <= c[k] for k in ("eval_ngram_overlap_records", "eval_name_collisions", "pii_records",
                                             "duplicate_pairs")))
    return {"seed": seed, "n": n, "metrics": m, "criteria": CRITERIA, "passed": passed}


def main() -> None:
    ap = argparse.ArgumentParser(prog="python -m nawa.data.twins")
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
    recs = build(a.n, a.seed)
    probs = [(x["twin_id"], pr) for x, y in pairs(recs) if (pr := check_pair(x, y))] + check_separation(recs)
    if probs:
        raise SystemExit(f"refusing to write malformed twins: {probs[:3]}")
    with a.out.open("w", encoding="utf-8") as fh:
        for r in recs:
            fh.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
    print(json.dumps({"pairs": a.n, "records": len(recs), "out": str(a.out)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
