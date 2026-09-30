"""Shared context-QA building blocks for faithfulness, abstention, robustness, arabic."""

from __future__ import annotations

import random

from nawa.evaluation.synth import Town

SYSTEM_CONTEXT = (
    "أنت مساعد دقيق. أجب عن السؤال اعتمادًا على السياق المعطى فقط. "
    "إذا لم يكن الجواب موجودًا في السياق فأجب بالعبارة: غير موجود في السياق. "
    "بعد الإجابة اذكر رقم الجملة الداعمة بين قوسين مربعين، مثل [2]."
)


def numbered_context(rng: random.Random, sentences: list[tuple[str, str | None]]) -> tuple[str, dict[str, int]]:
    """sentences: (text, key). Shuffle, number from 1, return text and key->index map."""
    order = sentences[:]
    rng.shuffle(order)
    lines, index = [], {}
    for i, (text, key) in enumerate(order, start=1):
        lines.append(f"[{i}] {text}")
        if key:
            index[key] = i
    return "\n".join(lines), index


def town_sentences(t: Town, attrs: tuple[str, ...], tag: str) -> list[tuple[str, str | None]]:
    return [(t.sentence(a), f"{tag}:{a}") for a in attrs]


def user_turn(context: str, question: str) -> str:
    return f"السياق:\n{context}\n\nالسؤال: {question}"
