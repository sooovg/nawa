"""regression_general: general skills that must not regress (T5): format following, extraction, ordering, units."""

from __future__ import annotations

import random

from nawa.evaluation.normalize import final_number, normalize
from nawa.evaluation.schema import Item
from nawa.evaluation.suites import result
from nawa.evaluation.synth import fictional_name

SUITE = "regression_general"
SYSTEM = "اتبع التعليمات بدقة، وأجب بالصيغة المطلوبة فقط."
WORDS = ["الشمس", "تشرق", "كل", "صباح", "على", "المدينة", "الهادئة", "والناس", "يذهبون", "إلى", "أعمالهم", "مبكرًا"]


def _make(rng: random.Random, k: int):
    if k == 0:
        n = rng.randint(4, 11)
        s = " ".join(rng.sample(WORDS, n))
        return f"كم عدد الكلمات في الجملة التالية؟ أجب برقم فقط.\n{s}", {"number": n}, "word_count"
    if k == 1:
        names = [fictional_name(rng, 2).lat for _ in range(4)]
        return (f"رتب الأسماء التالية أبجديًا بالإنجليزية وافصل بينها بفاصلة فقط: {', '.join(names)}",
                {"sequence": sorted(names)}, "sort")
    if k == 2:
        user = fictional_name(rng, 2).lat.lower()
        text = f"للتواصل مع فريق الدعم راسلوا {user}@example.org أو اتصلوا بالمكتب في ساعات العمل."
        return f"استخرج البريد الإلكتروني من النص التالي، وأجب به فقط:\n{text}", {"exact": f"{user}@example.org"}, "extract"
    if k == 3:
        km = rng.randint(2, 90)
        return f"كم مترًا في {km} كيلومترًا؟ أجب برقم فقط.", {"number": km * 1000}, "units"
    a, b = rng.randint(10, 999), rng.randint(10, 999)
    while a == b:
        b = rng.randint(10, 999)
    return f"هل العدد {a} أكبر من العدد {b}؟ أجب بكلمة واحدة: نعم أو لا.", {"yesno": "نعم" if a > b else "لا"}, "compare"


def generate(rng: random.Random, n: int, split: str) -> list[Item]:
    items = []
    for i in range(n):
        q, gold, kind = _make(rng, i % 5)
        items.append(Item(suite=SUITE, split=split,
                          messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": q}],
                          gold=gold, meta={"kind": kind, "source": "synthetic"}, max_new_tokens=40))
    return items


def score(item: Item, output: str) -> dict:
    g, kind = item.gold, item.meta["kind"]
    if "number" in g:
        v = final_number(output)
        ok = v is not None and v == g["number"]
    elif "sequence" in g:
        o = normalize(output)
        pos = [o.find(x.lower()) for x in g["sequence"]]
        ok = all(p >= 0 for p in pos) and pos == sorted(pos)
    elif "exact" in g:
        ok = g["exact"] in output
    else:
        words = normalize(output).split()
        ok = bool(words) and words[0] == normalize(g["yesno"])
    return result(ok, failure="FT-09", kind=kind, hallucination_applicable=False)


def oracle(item: Item) -> str:
    g = item.gold
    if "number" in g:
        return str(g["number"])
    if "sequence" in g:
        return ", ".join(g["sequence"])
    return g.get("exact") or g["yesno"]
