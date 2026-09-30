"""faithfulness: answer only from a given context (FT-12, FT-07, FT-09). Also yields citation accuracy (T6)."""

from __future__ import annotations

import random
import re

from nawa.evaluation.normalize import contains_any, is_abstention, normalize_digits
from nawa.evaluation.schema import Item
from nawa.evaluation.suites import result
from nawa.evaluation.suites._context import SYSTEM_CONTEXT, numbered_context, town_sentences, user_turn
from nawa.evaluation.synth import ATTRS, QUESTIONS_MSA, distinct_towns

SUITE = "faithfulness"


def generate(rng: random.Random, n: int, split: str) -> list[Item]:
    items = []
    for _ in range(n):
        target, distractor = distinct_towns(rng, 2)
        attr = rng.choice(ATTRS)
        sents = town_sentences(target, ATTRS, "t") + town_sentences(distractor, ATTRS, "d")
        ctx, idx = numbered_context(rng, sents)
        q = QUESTIONS_MSA[attr].format(n=target.name.ar)
        items.append(Item(
            suite=SUITE, split=split,
            messages=[{"role": "system", "content": SYSTEM_CONTEXT}, {"role": "user", "content": user_turn(ctx, q)}],
            gold={"answers": target.gold(attr), "distractor_answers": distractor.gold(attr), "support": idx[f"t:{attr}"]},
            meta={"attr": attr, "source": "synthetic", "expected_failure_modes": ["FT-12", "FT-07"]},
            max_new_tokens=48,
        ))
    return items


def cited(output: str) -> set[int]:
    return {int(x) for x in re.findall(r"\[(\d+)\]", normalize_digits(output))}


def score(item: Item, output: str) -> dict:
    ok = contains_any(output, item.gold["answers"])
    confused = contains_any(output, item.gold["distractor_answers"]) and not ok
    abst = is_abstention(output) and not ok
    c = cited(output)
    return result(ok, abstained=abst, failure="FT-07" if confused else ("FT-13" if abst else "FT-12"),
                  citation_correct=item.gold["support"] in c and len(c) <= 2, cited_any=bool(c))


def oracle(item: Item) -> str:
    return f"{item.gold['answers'][0]} [{item.gold['support']}]"
