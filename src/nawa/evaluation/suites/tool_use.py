"""tool_use: decide which tool (if any) a request needs (FT-16, FT-06)."""

from __future__ import annotations

import random

from nawa.evaluation.normalize import first_label
from nawa.evaluation.schema import Item
from nawa.evaluation.suites import result

SUITE = "tool_use"
LABELS = ("calculator", "search", "python", "none")
SYSTEM = (
    "لديك الأدوات التالية: calculator للحسابات العددية الدقيقة، search للمعلومات الحديثة أو المتغيرة، "
    "python لتنفيذ الكود أو معالجة الملفات والبيانات، و none إذا كنت تستطيع الإجابة مباشرة دون أداة. "
    "أجب بكلمة واحدة فقط من: calculator, search, python, none."
)
CITIES = ["الرياض", "القاهرة", "عمّان", "الدار البيضاء", "دبي", "تونس", "جدة", "بيروت", "الكويت", "مسقط", "الدوحة", "الجزائر"]
WORDS = ["كتاب", "شمس", "بيت", "قلم", "بحر", "شجرة", "نافذة", "طريق", "سحابة", "مدرسة", "جبل", "نهر", "باب", "مفتاح"]
COMPANIES = ["أرامكو", "سابك", "أبل", "مايكروسوفت", "تسلا", "الاتصالات السعودية", "إعمار", "سامسونج"]


def _req(rng: random.Random, label: str) -> str:
    if label == "calculator":
        return rng.choice([
            f"ما حاصل ضرب {rng.randint(10_000, 999_999)} في {rng.randint(1_000, 99_999)} بالضبط؟",
            f"احسب الجذر التربيعي للعدد {rng.randint(10_000, 9_999_999)} لأقرب أربع منازل عشرية.",
            f"كم يساوي {rng.randint(1000, 9999)} أس {rng.randint(3, 6)} بالضبط؟"])
    if label == "search":
        return rng.choice([
            "ما سعر صرف الدولار الأمريكي مقابل الريال السعودي اليوم؟",
            f"كيف حالة الطقس الآن في {rng.choice(CITIES)}؟",
            f"ما سعر سهم شركة {rng.choice(COMPANIES)} الآن؟",
            f"كم درجة الحرارة المتوقعة غدًا في {rng.choice(CITIES)}؟",
            f"هل توجد رحلات طيران متاحة اليوم من {rng.choice(CITIES)} إلى {rng.choice(CITIES)}؟",
            f"ما آخر إصدار منشور من مكتبة {rng.choice(['numpy', 'pandas', 'pytorch', 'transformers'])} هذا الأسبوع؟",
            "ما أحدث الأخبار عن أسعار النفط اليوم؟"])
    if label == "python":
        return rng.choice([
            f"لدي ملف CSV فيه {rng.randint(500, 90_000)} صف. احسب متوسط العمود price وأخرج أعلى عشر قيم.",
            f"نفّذ هذا الكود وأخبرني بالمخرج بالضبط: print(sorted(set(range({rng.randint(5, 50)}, 0, -3))))",
            "حوّل ملف JSON كبير مرفق إلى جدول Excel مع حذف الصفوف المكررة."])
    return rng.choice([
        f"ما معنى كلمة «{rng.choice(WORDS)}»؟",
        f"ترجم كلمة «{rng.choice(WORDS)}» إلى الإنجليزية.",
        f"اكتب جملة ترحيب قصيرة لضيف اسمه {rng.choice(['سالم', 'هدى', 'فهد', 'ليلى', 'عمر', 'نورة'])}.",
        f"ما جمع كلمة «{rng.choice(WORDS)}»؟",
        f"ما حاصل جمع {rng.randint(2, 9)} و{rng.randint(2, 9)}؟"])


def generate(rng: random.Random, n: int, split: str) -> list[Item]:
    items, seen = [], set()
    for i in range(n):
        label = LABELS[i % 4]
        for _ in range(200):
            req = _req(rng, label)
            if req not in seen:
                break
        else:
            raise RuntimeError(f"tool_use: template space exhausted for {label}")
        seen.add(req)
        items.append(Item(suite=SUITE, split=split,
                          messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": req}],
                          gold={"label": label}, meta={"source": "synthetic"}, max_new_tokens=8))
    return items


def score(item: Item, output: str) -> dict:
    got = first_label(output, LABELS)
    fail = "FT-06" if item.gold["label"] == "search" else "FT-16"
    return result(got == item.gold["label"], failure=fail, predicted=got, hallucination_applicable=False)


def oracle(item: Item) -> str:
    return item.gold["label"]
