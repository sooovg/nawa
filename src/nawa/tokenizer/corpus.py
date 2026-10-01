"""Code-generated corpora for P3-01/P3-02 (no external text; ADR-0006).

Each generator is deterministic for a seed. Training and held-out sets use different seeds, so held-out
text is unseen but from the same distribution. Because the text is synthetic, measurements describe the
candidates' mechanics (losslessness, compression on these distributions, robustness), not real-corpus
quality; selecting a tokenizer (P3-03) needs a licensed real corpus.

Arabic words are root-and-pattern derivations with optional clitics, so morpheme boundaries are known
(gold for the morphology metric). Some stems start or end with letters that look like clitics, so a
segmenter that splits on surface letters alone is penalised.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

CONSONANTS = "بتثجحخدذرزسشصضطظعغفقكلمنهوي"
PATTERNS = ("فعل", "فاعل", "مفعول", "فعيل", "فعال", "تفعيل", "استفعال", "مفعل", "فعلان", "انفعال", "افتعال")
PROCLITICS = ("و", "ف", "ب", "ل", "ك", "ال", "وال", "بال", "لل", "س")
ENCLITICS = ("ه", "ها", "هم", "كم", "نا", "هما", "ك")
EN_WORDS = ("model", "data", "file", "server", "python", "token", "layer", "training", "test", "cache", "network",
            "query", "result", "error", "version", "update", "branch", "commit", "image", "system")
FUNCTION_WORDS = ("في", "من", "على", "إلى", "عن", "مع", "أن", "هذا", "التي", "الذي", "قد", "لا", "ثم", "كل")


@dataclass(frozen=True)
class Word:
    text: str
    morphemes: tuple[str, ...]

    def boundaries(self) -> set[int]:
        out, i = set(), 0
        for m in self.morphemes[:-1]:
            i += len(m)
            out.add(i)
        return out


class ArabicGen:
    def __init__(self, seed: int, n_roots: int = 400) -> None:
        self.rng = random.Random(seed)
        # Root inventory comes from a fixed seed so train and held-out share a lexicon (as a real language does).
        lex = random.Random(424242)
        self.roots = sorted({"".join(lex.choice(CONSONANTS) for _ in range(3)) for _ in range(n_roots)})

    def stem(self) -> str:
        r = self.rng.choice(self.roots)
        p = self.rng.choice(PATTERNS)
        return p.replace("ف", "\0").replace("ع", "\1").replace("ل", "\2").replace("\0", r[0]).replace(
            "\1", r[1]).replace("\2", r[2])

    def word(self) -> Word:
        if self.rng.random() < 0.15:
            w = self.rng.choice(FUNCTION_WORDS)
            return Word(w, (w,))
        parts: list[str] = []
        if self.rng.random() < 0.45:
            parts.append(self.rng.choice(PROCLITICS))
        parts.append(self.stem())
        if self.rng.random() < 0.3 and not (parts[0] in ("ال", "وال", "بال", "لل") and len(parts) > 1):
            parts.append(self.rng.choice(ENCLITICS))
        return Word("".join(parts), tuple(parts))

    def sentence(self, lo: int = 6, hi: int = 18) -> str:
        words = [self.word().text for _ in range(self.rng.randint(lo, hi))]
        return " ".join(words) + self.rng.choice(("." , ".", "،", "؟", "!"))

    def doc(self, n: int) -> str:
        return " ".join(self.sentence() for _ in range(n))


def arabic(seed: int, n_docs: int, sentences: int = 6) -> list[str]:
    g = ArabicGen(seed)
    return [g.doc(sentences) for _ in range(n_docs)]


def morph_words(seed: int, n: int) -> list[Word]:
    g = ArabicGen(seed)
    out: list[Word] = []
    while len(out) < n:
        w = g.word()
        if len(w.morphemes) > 1 or g.rng.random() < 0.3:
            out.append(w)
    return out


def english(seed: int, n_docs: int) -> list[str]:
    rng = random.Random(seed)
    docs = []
    for _ in range(n_docs):
        sents = []
        for _ in range(rng.randint(3, 6)):
            ws = [rng.choice(EN_WORDS) if rng.random() < 0.5 else rng.choice(("the", "a", "of", "to", "is", "and", "in"))
                  for _ in range(rng.randint(6, 14))]
            sents.append(" ".join(ws).capitalize() + ".")
        docs.append(" ".join(sents))
    return docs


def code(seed: int, n_docs: int) -> list[str]:
    rng = random.Random(seed)
    ident = lambda: "_".join(rng.choice(EN_WORDS) for _ in range(rng.randint(1, 3)))  # noqa: E731
    docs = []
    for _ in range(n_docs):
        f, a, b = ident(), ident(), ident()
        n = rng.randint(2, 999)
        docs.append(
            f"def {f}({a}, {b}={n}):\n"
            f"    \"\"\"Return the {rng.choice(EN_WORDS)} of {a}.\"\"\"\n"
            f"    result = []\n"
            f"    for i in range(len({a})):\n"
            f"        if {a}[i] > {b}:\n"
            f"            result.append({a}[i] * {rng.randint(2, 9)})\n"
            f"    return result  # {rng.choice(EN_WORDS)}\n")
    return docs


def mixed(seed: int, n_docs: int) -> list[str]:
    rng = random.Random(seed)
    g = ArabicGen(seed)
    docs = []
    for _ in range(n_docs):
        words = []
        for _ in range(rng.randint(20, 40)):
            words.append(rng.choice(EN_WORDS) if rng.random() < 0.25 else g.word().text)
        docs.append(" ".join(words) + ".")
    return docs


_RARE_RANGES = ((0x4E00, 0x4FFF), (0x1F300, 0x1F5FF), (0x2200, 0x22FF), (0x0900, 0x097F), (0x05D0, 0x05EA),
                (0xFB50, 0xFBB1), (0x0750, 0x077F), (0x10A0, 0x10FF), (0x1D400, 0x1D4FF))


def rare_unicode(seed: int, n_docs: int) -> list[str]:
    rng = random.Random(seed)
    g = ArabicGen(seed)
    docs = []
    for _ in range(n_docs):
        parts = []
        for _ in range(rng.randint(10, 20)):
            r = rng.random()
            if r < 0.5:
                lo, hi = rng.choice(_RARE_RANGES)
                parts.append("".join(chr(rng.randint(lo, hi)) for _ in range(rng.randint(1, 4))))
            elif r < 0.7:
                parts.append("e\u0301" + "a\u0308" + "n\u0303")  # decomposed Latin with combining marks
            elif r < 0.85:
                parts.append("مي\u200cخواهم")  # Persian with ZWNJ
            else:
                parts.append(g.word().text)
        docs.append(" ".join(parts))
    return docs


TASHKEEL = "\u064e\u064f\u0650\u0651\u0652\u064b\u064c\u064d"
_ARABIZI = {"ا": "a", "ب": "b", "ت": "t", "ث": "th", "ج": "j", "ح": "7", "خ": "5", "د": "d", "ذ": "th", "ر": "r",
            "ز": "z", "س": "s", "ش": "sh", "ص": "s", "ض": "d", "ط": "6", "ظ": "z", "ع": "3", "غ": "gh", "ف": "f",
            "ق": "q", "ك": "k", "ل": "l", "م": "m", "ن": "n", "ه": "h", "و": "w", "ي": "y", "ء": "2", "ة": "a",
            "ى": "a", "أ": "a", "إ": "i", "آ": "a", "ؤ": "2", "ئ": "2"}


def noisy_pairs(seed: int, n: int) -> list[tuple[str, str, str]]:
    """(kind, clean, noisy) with kinds tashkeel, tatweel, typo, repeat, arabizi."""
    rng = random.Random(seed)
    g = ArabicGen(seed)
    out = []
    kinds = ("tashkeel", "tatweel", "typo", "repeat", "arabizi")
    for i in range(n):
        clean = g.sentence(8, 14)
        kind = kinds[i % len(kinds)]
        if kind == "tashkeel":
            noisy = "".join(c + (rng.choice(TASHKEEL) if "\u0621" <= c <= "\u064a" and rng.random() < 0.7 else "")
                            for c in clean)
        elif kind == "tatweel":
            noisy = "".join(c + ("\u0640" * rng.randint(1, 3) if "\u0621" <= c <= "\u064a" and rng.random() < 0.15
                                 else "") for c in clean)
        elif kind == "typo":
            cs = list(clean)
            for _ in range(max(1, len(cs) // 15)):
                j = rng.randrange(len(cs) - 1)
                cs[j], cs[j + 1] = cs[j + 1], cs[j]
            noisy = "".join(cs)
        elif kind == "repeat":
            noisy = "".join(c * (rng.randint(3, 6) if "\u0621" <= c <= "\u064a" and rng.random() < 0.05 else 1)
                            for c in clean)
        else:
            noisy = "".join(_ARABIZI.get(c, c) for c in clean)
        out.append((kind, clean, noisy))
    return out


def training_corpus(seed: int, scale: int = 1) -> list[str]:
    """Mixed training text: Arabic, English, code, mixed, a little rare Unicode."""
    return (arabic(seed, 600 * scale) + english(seed + 1, 150 * scale) + code(seed + 2, 150 * scale)
            + mixed(seed + 3, 150 * scale) + rare_unicode(seed + 4, 20 * scale))
