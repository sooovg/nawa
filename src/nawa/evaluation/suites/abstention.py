"""abstention: twin items. Same question; one context has the evidence, the other lacks it (FT-13, FT-14).

The unanswerable twin keeps a distractor town that HAS the asked attribute, to tempt a wrong answer.
"""

from __future__ import annotations

import random

from nawa.evaluation.normalize import contains_any, is_abstention
from nawa.evaluation.schema import Item
from nawa.evaluation.suites import result
from nawa.evaluation.suites._context import SYSTEM_CONTEXT, numbered_context, town_sentences, user_turn
from nawa.evaluation.synth import ATTRS, QUESTIONS_MSA, distinct_towns

SUITE = "abstention"


def generate(rng: random.Random, n: int, split: str) -> list[Item]:
    """n twin pairs -> 2n items."""
    items = []
    for pair in range(n):
        target, distractor = distinct_towns(rng, 2)
        attr = rng.choice(ATTRS)
        others = tuple(a for a in ATTRS if a != attr)
        q = QUESTIONS_MSA[attr].format(n=target.name.ar)
        twin = f"{split}-{rng.getrandbits(48):012x}"
        for answerable in (True, False):
            t_attrs = ATTRS if answerable else others
            sents = town_sentences(target, t_attrs, "t") + town_sentences(distractor, ATTRS, "d")
            ctx, idx = numbered_context(rng, sents)
            items.append(Item(
                suite=SUITE, split=split,
                messages=[{"role": "system", "content": SYSTEM_CONTEXT}, {"role": "user", "content": user_turn(ctx, q)}],
                gold={"answerable": answerable, "answers": target.gold(attr) if answerable else [],
                      "distractor_answers": distractor.gold(attr), "support": idx.get(f"t:{attr}")},
                meta={"attr": attr, "twin_id": twin, "source": "synthetic"},
                max_new_tokens=48,
            ))
    return items


def score(item: Item, output: str) -> dict:
    abst = is_abstention(output)
    if item.gold["answerable"]:
        ok = contains_any(output, item.gold["answers"])
        abst = abst and not ok
        return result(ok, abstained=abst, failure="FT-13" if abst else "FT-12", answerable=True)
    ok = abst and not contains_any(output, item.gold["distractor_answers"])
    # On an unanswerable item any non-abstaining answer is a hallucination (FT-14).
    return result(ok, abstained=abst, failure="FT-14", answerable=False)


def oracle(item: Item) -> str:
    if item.gold["answerable"]:
        return f"{item.gold['answers'][0]} [{item.gold['support']}]"
    return "غير موجود في السياق"
