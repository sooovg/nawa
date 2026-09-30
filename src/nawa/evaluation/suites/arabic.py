"""arabic: the same context QA asked in MSA, Gulf, Egyptian, Levantine, Arabizi, and code-switched registers (FT-15)."""

from __future__ import annotations

import random

from nawa.evaluation.normalize import contains_any
from nawa.evaluation.schema import Item
from nawa.evaluation.suites import result
from nawa.evaluation.suites._context import numbered_context, town_sentences, user_turn
from nawa.evaluation.synth import ATTRS, make_town

SUITE = "arabic"
SYSTEM = "أجب عن السؤال اعتمادًا على السياق فقط وبإيجاز. السؤال قد يكون بلهجة عربية أو بالعربيزي أو بخليط لغوي."

Q = {
    "msa":       {"river": "على ضفاف أي نهر تقع بلدة {ar}؟", "product": "ما أشهر منتجات بلدة {ar}؟", "year": "متى تأسست بلدة {ar}؟"},
    "gulf":      {"river": "وش اسم النهر اللي تقع عليه بلدة {ar}؟", "product": "وش أشهر شي تنتجه بلدة {ar}؟", "year": "بلدة {ar} متى تأسست؟"},
    "egyptian":  {"river": "هي بلدة {ar} على نهر إيه؟", "product": "بلدة {ar} مشهورة بإيه؟", "year": "بلدة {ar} اتأسست سنة كام؟"},
    "levantine": {"river": "شو اسم النهر يلي عليه بلدة {ar}؟", "product": "شو أشهر شي بتنتجه بلدة {ar}؟", "year": "إيمتى تأسست بلدة {ar}؟"},
    "arabizi":   {"river": "shu esm el nahr elli 3aleh baldet {lat}?", "product": "baldet {lat} mash-hoora b shu?", "year": "baldet {lat} t2assaset emta?"},
    "code_switch": {"river": "What is the river اللي تقع عليه بلدة {ar}?", "product": "بلدة {ar} famous for what product؟", "year": "In which year تأسست بلدة {ar}؟"},
}
REGISTERS = tuple(Q)


def generate(rng: random.Random, n: int, split: str) -> list[Item]:
    items = []
    for i in range(n):
        reg = REGISTERS[i % len(REGISTERS)]
        t = make_town(rng)
        attr = rng.choice(("river", "product", "year"))
        ctx, _ = numbered_context(rng, town_sentences(t, ATTRS, "t"))
        q = Q[reg][attr].format(ar=t.name.ar, lat=t.name.lat)
        items.append(Item(suite=SUITE, split=split,
                          messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": user_turn(ctx, q)}],
                          gold={"answers": t.gold(attr)}, meta={"register": reg, "attr": attr, "source": "synthetic"},
                          max_new_tokens=40))
    return items


def score(item: Item, output: str) -> dict:
    return result(contains_any(output, item.gold["answers"]), failure="FT-15", register=item.meta["register"])


def oracle(item: Item) -> str:
    return item.gold["answers"][0]
