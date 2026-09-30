"""P1-02: every suite is deterministic, valid, solvable by an oracle, and not solvable by noise."""

from __future__ import annotations

import random

import pytest

from nawa.evaluation import suites
from nawa.evaluation.build import SEEDS, SIZES, build_public, build_split
from nawa.evaluation.normalize import contains, final_number, is_abstention, normalize
from nawa.evaluation.sandbox import run_python
from nawa.evaluation.schema import BLOCKED_SUITES, SUITES, Item
from nawa.evaluation.taxonomy import load_taxonomy

NOISE = ["", "جواب عشوائي لا علاقة له", "42", "I am not sure what you mean."]


@pytest.fixture(scope="module")
def dev():
    return build_split("dev", SEEDS["dev"])


def test_all_agents_md_suites_present_or_explicitly_blocked() -> None:
    required = {"faithfulness", "abstention", "factual", "reasoning_math", "code", "tool_use",
                "domain", "robustness", "arabic", "regression_general"}
    assert required == set(SUITES) | set(BLOCKED_SUITES)
    assert "OD-01" in BLOCKED_SUITES["domain"]


def test_build_is_deterministic(dev) -> None:
    again = build_split("dev", SEEDS["dev"])
    for name in SUITES:
        assert [i.to_json() for i in dev[name]] == [i.to_json() for i in again[name]]


def test_sizes_and_uniqueness(dev) -> None:
    for name in SUITES:
        expected = SIZES["dev"][name] * (2 if name == "abstention" else 1)
        assert len(dev[name]) == expected, name
    all_hashes = [i.content_hash() for its in dev.values() for i in its]
    assert len(all_hashes) == len(set(all_hashes))


def test_dev_and_calib_do_not_overlap(dev) -> None:
    calib = build_public()["calib"]
    a = {i.content_hash() for its in dev.values() for i in its}
    b = {i.content_hash() for its in calib.values() for i in its}
    assert not a & b


def test_oracle_scores_correct(dev) -> None:
    for name, items in dev.items():
        mod = suites.get(name)
        for it in items:
            assert mod.score(it, mod.oracle(it))["correct"], (name, it.id)


def test_noise_is_not_rewarded(dev) -> None:
    for name, items in dev.items():
        mod = suites.get(name)
        for noise in NOISE:
            hits = sum(mod.score(it, noise)["correct"] for it in items)
            if name == "tool_use":
                assert hits == 0
            else:
                assert hits <= len(items) * 0.05, (name, noise, hits)


def test_failures_map_to_taxonomy(dev) -> None:
    ids = set(load_taxonomy())
    for name, items in dev.items():
        mod = suites.get(name)
        for it in items[:5]:
            f = mod.score(it, "جواب عشوائي لا علاقة له")["failure"]
            assert f is None or f in ids, (name, f)


def test_items_roundtrip_json(dev) -> None:
    import json
    it = dev["faithfulness"][0]
    assert Item.from_dict(json.loads(it.to_json())).to_json() == it.to_json()


def test_faithfulness_detects_entity_conflation(dev) -> None:
    mod = suites.get("faithfulness")
    it = dev["faithfulness"][0]
    r = mod.score(it, it.gold["distractor_answers"][0])
    assert not r["correct"] and r["failure"] == "FT-07" and r["hallucinated"]


def test_abstention_twins(dev) -> None:
    mod = suites.get("abstention")
    items = dev["abstention"]
    unans = [i for i in items if not i.gold["answerable"]]
    ans = [i for i in items if i.gold["answerable"]]
    assert len(unans) == len(ans)
    assert all(mod.score(i, "غير موجود في السياق")["correct"] for i in unans)
    assert not any(mod.score(i, "غير موجود في السياق")["correct"] for i in ans)
    guess = mod.score(unans[0], unans[0].gold["distractor_answers"][0])
    assert guess["hallucinated"] and guess["failure"] == "FT-14"


def test_code_fake_package_import_fails(dev) -> None:
    mod = suites.get("code")
    trap = next(i for i in dev["code"] if i.meta["kind"] == "fake_package")
    bad = f"```python\nimport {trap.gold['fake_package']}\ndef strip_tashkeel(s):\n    return {trap.gold['fake_package']}.strip(s)\n```"
    assert not mod.score(trap, bad)["correct"]


def test_code_wrong_solution_fails(dev) -> None:
    mod = suites.get("code")
    task = next(i for i in dev["code"] if i.meta["kind"] != "fake_package")
    wrong = f"```python\ndef {task.gold['function']}(*a):\n    return None\n```"
    assert not mod.score(task, wrong)["correct"]


def test_sandbox_limits() -> None:
    assert not run_python("import socket\nsocket.socket()").ok
    r = run_python("while True: pass", timeout=3)
    assert not r.ok
    assert run_python("print(1+1)").stdout.strip() == "2"


def test_normalization() -> None:
    assert normalize("إِلى الْمَدِينَةِ") == normalize("الى المدينه")
    assert contains("عدد السكان ٤٥٬٢١٠ نسمة", "45210")
    assert not contains("1234", "123")
    assert final_number("خطوات...\nالجواب: ١٢٥") == 125
    assert is_abstention("المعلومة غير موجودة في السياق")


def test_frozen_factual_requires_private_bank() -> None:
    with pytest.raises(ValueError):
        suites.get("factual").generate(random.Random(0), 5, "frozen")
