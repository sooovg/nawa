"""factual: closed-book questions scored against an authored answer key (FT-02, FT-11).

Public items (dev/calib) come from eval/suites/factual_bank.yaml. Frozen items come from a
private bank passed via `bank_path`, which is never committed to Git.
"""

from __future__ import annotations

import random
from pathlib import Path

import yaml

from nawa.evaluation.normalize import contains_any, is_abstention
from nawa.evaluation.schema import Item
from nawa.evaluation.suites import result

SUITE = "factual"
PUBLIC_BANK = Path(__file__).resolve().parents[4] / "eval" / "suites" / "factual_bank.yaml"
SYSTEM = "أجب بإيجاز شديد بكلمة أو عبارة قصيرة. إذا لم تكن متأكدًا فقل: لا أعرف."


def load_bank(path: Path = PUBLIC_BANK) -> list[dict]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return data["items"]


def generate(rng: random.Random, n: int, split: str, bank: list[dict] | None = None) -> list[Item]:
    """For dev/calib, the public bank is split deterministically: dev takes items 0..29, calib the rest."""
    if bank is None:
        if split == "frozen":
            raise ValueError("frozen factual items require the private bank (P1-03)")
        full = load_bank()
        bank = full[:30] if split == "dev" else full[30:]
    chosen = bank[:] if n >= len(bank) else rng.sample(bank, n)
    return [Item(suite=SUITE, split=split,
                 messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": b["q"]}],
                 gold={"answers": b["a"]}, meta={"source": "authored", "review_status": "agent_authored_pending_human_review"},
                 max_new_tokens=32) for b in chosen]


def score(item: Item, output: str) -> dict:
    ok = contains_any(output, item.gold["answers"])
    abst = is_abstention(output) and not ok
    return result(ok, abstained=abst, failure="FT-11" if not abst else "FT-13")


def oracle(item: Item) -> str:
    return item.gold["answers"][0]
