"""reasoning_math: multi-step Arabic word problems with exact integer answers (FT-03)."""

from __future__ import annotations

import random

from nawa.evaluation.normalize import final_number
from nawa.evaluation.schema import Item
from nawa.evaluation.suites import result

SUITE = "reasoning_math"
SYSTEM = "حل المسألة خطوة بخطوة باختصار، ثم اكتب في السطر الأخير: الجواب: <العدد>"
NAMES = ["أحمد", "سارة", "خالد", "مريم", "علي", "نورة"]


def _problem(rng: random.Random) -> tuple[str, int, str]:
    k = rng.randrange(7)
    nm = rng.choice(NAMES)
    if k == 0:
        a, p = rng.randint(3, 12), rng.randint(7, 45)
        pay = (a * p // 50 + 1 + rng.randint(0, 3)) * 50
        return f"اشترى {nm} {a} كتب بسعر {p} ريالًا للكتاب الواحد، ودفع {pay} ريالًا. كم ريالًا بقي له؟", pay - a * p, "change"
    if k == 1:
        a, b = rng.randint(5, 60), rng.randint(3, 40)
        return f"في مزرعة {a} دجاجة و{b} بقرة. كم عدد أرجل الحيوانات كلها؟", 2 * a + 4 * b, "legs"
    if k == 2:
        p, d = rng.randint(4, 90) * 100, rng.choice((10, 20, 25, 50))
        return f"سعر جهاز {p} ريال، وعليه خصم {d}%. كم سعره بعد الخصم؟", p * (100 - d) // 100, "discount"
    if k == 3:
        s, h = rng.randint(20, 60) * 2, rng.randint(1, 6)
        return f"تسير سيارة بسرعة ثابتة {s} كيلومترًا في الساعة. كم كيلومترًا تقطع في {h} ساعات ونصف الساعة؟", s * h + s // 2, "rate"
    if k == 4:
        a, b = rng.randint(6, 30), rng.randint(1, 5)
        return f"عمر {nm} {a} سنة، وعمر أخيه ضعف عمره ناقص {b} سنوات. كم مجموع عمريهما؟", a + (2 * a - b), "ages"
    if k == 5:
        n, d = rng.randint(100, 9999), rng.randint(3, 17)
        return f"ما باقي قسمة {n} على {d}؟", n % d, "modulo"
    r, b = rng.randint(10, 40), rng.randint(5, 30)
    k2 = rng.randint(1, r - 1)
    return (f"في صندوق {r} كرة حمراء و{b} كرة زرقاء. أُخرجت منه {k2} كرات حمراء، ثم أضيف إليه من الكرات الزرقاء "
            f"ضعف عدد الكرات التي أُخرجت. كم كرة في الصندوق الآن؟", (r - k2) + b + 2 * k2, "multi_step")


def generate(rng: random.Random, n: int, split: str) -> list[Item]:
    items = []
    for _ in range(n):
        q, ans, kind = _problem(rng)
        items.append(Item(suite=SUITE, split=split,
                          messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": q}],
                          gold={"answer": ans}, meta={"kind": kind, "source": "synthetic"}, max_new_tokens=192))
    return items


def score(item: Item, output: str) -> dict:
    v = final_number(output)
    return result(v is not None and abs(v - item.gold["answer"]) < 1e-9, failure="FT-03", kind=item.meta["kind"])


def oracle(item: Item) -> str:
    return f"الجواب: {item.gold['answer']}"
