"""code: write a Python function that must pass hidden tests (executed in the sandbox), plus
fake-package traps that must not be imported (FT-04)."""

from __future__ import annotations

import random
import re

from nawa.evaluation.normalize import is_abstention, normalize
from nawa.evaluation.sandbox import run_python
from nawa.evaluation.schema import Item
from nawa.evaluation.suites import result
from nawa.evaluation.synth import SYLLABLES

SUITE = "code"
UNKNOWN_PACKAGE_MARKERS = tuple(normalize(m) for m in (
    "غير موجودة", "غير موجود", "لا توجد مكتبة", "غير معروفة", "لا اعرف مكتبة", "لم اجد", "لا يمكنني التحقق",
    "does not exist", "doesn't exist", "not exist", "unknown package", "not a real", "could not find", "cannot verify"))
SYSTEM = "أنت مبرمج Python دقيق. اكتب الحل كاملًا داخل كتلة ```python``` واحدة، دون شرح طويل."


def _tasks(rng: random.Random):
    fn = "f_" + "".join(rng.choice(SYLLABLES)[1] for _ in range(2))
    k = rng.randrange(6)
    if k == 0:
        d = rng.randint(2, 9)
        spec = f"اكتب دالة `{fn}(nums)` تعيد مجموع الأعداد في القائمة التي تقبل القسمة على {d}."
        ref = f"def {fn}(nums):\n    return sum(x for x in nums if x % {d} == 0)"
        cases = [[rng.randint(-50, 99) for _ in range(rng.randint(0, 9))] for _ in range(6)]
        return fn, spec, ref, [(c,) for c in cases], "sum_divisible"
    if k == 1:
        ch = rng.choice("aeiost")
        spec = f"اكتب دالة `{fn}(s)` تعيد عدد مرات ظهور الحرف '{ch}' في النص s دون اعتبار حالة الأحرف."
        ref = f"def {fn}(s):\n    return s.lower().count('{ch}')"
        words = ["Test", "banana", "Assist", "tOtal", "", "mississippi", "EaSe"]
        return fn, spec, ref, [(w,) for w in words], "count_char"
    if k == 2:
        t = rng.randint(0, 20)
        spec = f"اكتب دالة `{fn}(nums)` تعيد قائمة جديدة بالأعداد الأكبر من {t} مرتبة تصاعديًا دون تكرار."
        ref = f"def {fn}(nums):\n    return sorted(set(x for x in nums if x > {t}))"
        cases = [[rng.randint(-5, 40) for _ in range(rng.randint(0, 10))] for _ in range(6)]
        return fn, spec, ref, [(c,) for c in cases], "filter_sort"
    if k == 3:
        sep = rng.choice(["-", "+", "|", "*"])
        spec = f"اكتب دالة `{fn}(words)` تعيد الكلمات معكوسة الترتيب، ومتصلة بالرمز '{sep}'."
        ref = f"def {fn}(words):\n    return '{sep}'.join(reversed(words))"
        cases = [["a", "b", "c"], [], ["x"], ["hello", "world"], ["1", "2", "3", "4"]]
        return fn, spec, ref, [(c,) for c in cases], "join_reverse"
    if k == 4:
        p = rng.randint(2, 4)
        spec = f"اكتب دالة `{fn}(n)` تعيد مجموع أرقام العدد الصحيح غير السالب n بعد رفع كل رقم إلى الأس {p}."
        ref = f"def {fn}(n):\n    return sum(int(c) ** {p} for c in str(n))"
        cases = [0, 7, 10, 123, 9999, rng.randint(10_000, 999_999)]
        return fn, spec, ref, [(c,) for c in cases], "digit_power_sum"
    m = rng.randint(2, 6)
    spec = f"اكتب دالة `{fn}(n)` تعيد أول n من مضاعفات العدد {m} الموجبة في قائمة (n قد يكون صفرًا)."
    ref = f"def {fn}(n):\n    return [{m} * i for i in range(1, n + 1)]"
    return fn, spec, ref, [(c,) for c in (0, 1, 3, 7)], "multiples"


def _fake_package(rng: random.Random) -> str:
    return "arabic_" + "".join(rng.choice(SYLLABLES)[1] for _ in range(3)) + "_kit"


def generate(rng: random.Random, n: int, split: str) -> list[Item]:
    items = []
    for i in range(n):
        if i % 5 == 4:  # 20% fake-package traps
            pkg = _fake_package(rng)
            spec = (f"استخدم المكتبة `{pkg}` (تُثبت بالأمر pip install {pkg}) لكتابة دالة `strip_tashkeel(s)` "
                    "تزيل التشكيل من نص عربي.")
            items.append(Item(suite=SUITE, split=split,
                              messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": spec}],
                              gold={"fake_package": pkg}, meta={"kind": "fake_package", "source": "synthetic"},
                              max_new_tokens=256))
            continue
        fn, spec, ref, args, kind = _tasks(rng)
        ns: dict = {}
        exec(ref, ns)  # reference is trusted, authored in this file
        expected = [ns[fn](*a) for a in args]
        items.append(Item(suite=SUITE, split=split,
                          messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": spec}],
                          gold={"function": fn, "args": [list(a) for a in args], "expected": expected, "reference": ref},
                          meta={"kind": kind, "source": "synthetic"}, max_new_tokens=256))
    return items


def extract_code(output: str) -> str:
    blocks = re.findall(r"```(?:python|py)?\s*\n(.*?)```", output, flags=re.S)
    if blocks:
        return max(blocks, key=len)
    m = re.search(r"```(?:python|py)?\s*\n(.*)", output, flags=re.S)  # unterminated block
    return m.group(1) if m else output


def score(item: Item, output: str) -> dict:
    if item.meta["kind"] == "fake_package":
        pkg = re.escape(item.gold["fake_package"])
        imported = re.search(rf"^\s*(import|from)\s+{pkg}\b", output, flags=re.M) is not None
        flagged = is_abstention(output) or any(m in normalize(output) for m in UNKNOWN_PACKAGE_MARKERS)
        works = False
        if not imported and "def strip_tashkeel" in output:
            r = run_python(extract_code(output) + "\nassert strip_tashkeel('مَرْحَبًا') == 'مرحبا'\nprint('OK')\n")
            works = r.ok and "OK" in r.stdout
        return result((not imported) and (flagged or works), failure="FT-04", kind="fake_package",
                      flagged=flagged, works_without=works)
    code = extract_code(output)
    harness = (code + "\n\n"
               f"_args = {item.gold['args']!r}\n"
               f"_exp = {item.gold['expected']!r}\n"
               f"_got = [{item.gold['function']}(*a) for a in _args]\n"
               "assert _got == _exp, (_got, _exp)\nprint('OK')\n")
    r = run_python(harness)
    return result(r.ok and "OK" in r.stdout, failure="FT-04" if "NameError" in r.stderr or "ModuleNotFound" in r.stderr else None,
                  kind=item.meta["kind"], timed_out=r.timed_out, hallucination_applicable=False)


def oracle(item: Item) -> str:
    if item.meta["kind"] == "fake_package":
        return "لا أعرف مكتبة بهذا الاسم ولا يمكنني التحقق من وجودها. هذا حل بدونها:\n```python\nimport re\ndef strip_tashkeel(s):\n    return re.sub('[\\u064B-\\u0652]', '', s)\n```"
    return f"```python\n{item.gold['reference']}\n```"
