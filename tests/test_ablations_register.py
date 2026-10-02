"""P4-07: `docs/ablations.md` lists every P4 record, including failures, and adopts nothing (ADR-0007 D2, D4)."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = (ROOT / "docs/ablations.md").read_text(encoding="utf-8")
ROADMAP = (ROOT / "ROADMAP.md").read_text(encoding="utf-8")


def p4_records() -> list[dict]:
    lines = (ROOT / "experiments/log.jsonl").read_text(encoding="utf-8").splitlines()
    return [r for r in map(json.loads, lines) if r.get("schema") == "p4-record/v1"]


def section(title: str) -> str:
    i = DOC.index(title)
    j = DOC.find("\n### ", i + len(title))
    return DOC[i: j if j != -1 else len(DOC)]


def table_rows(text: str) -> list[list[str]]:
    rows = [[c.strip() for c in line.strip().strip("|").split("|")] for line in text.splitlines()
            if line.startswith("| ") and not line.startswith("|---")]
    return rows[1:]


def task_status(tid: str) -> str:
    m = re.search(rf"^\| {re.escape(tid)} \| (\w+) \|", ROADMAP, flags=re.M)
    assert m, tid
    return m[1]


def test_index_equals_every_p4_record_in_the_log() -> None:
    rows = table_rows(section("### Index of every P4 record"))
    want = [[r["experiment_id"], r["task_id"], r["status"], str(r["passed"]).lower(), str(len(r["criteria"])),
             r["data_kind"], str(r["seed"]), f"`{r['config_hash']}`", f"`{r['git_commit'][:7]}`",
             "none" if r["artifact"] is None else str(r["artifact"])] for r in p4_records()]
    got = [[r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[10], r[11], r[12]] for r in rows]
    assert got == want


def test_every_p4_record_has_a_detail_row_including_failures() -> None:
    detail = section("### Experiment details")
    listed = {r[0] for r in table_rows(detail)}
    assert {r["experiment_id"] for r in p4_records()} <= listed
    for r in p4_records():
        if r["status"] != "PASSED":
            assert r["experiment_id"] in detail, r["experiment_id"]


def test_nothing_is_adopted_and_comparisons_point_to_blocked_real_text_tasks() -> None:
    rows = table_rows(section("### Technique status"))
    assert rows
    for row in rows:
        assert "ADOPTED" not in row[4] or row[4].startswith("NOT ADOPTED"), row
    comparisons = {row[0]: row[5] for row in rows}
    for name, tid in (("Sparse MoE and MoE hybrid", "P4-02a"),
                      ("Ternary and symmetric 4-bit QAT + packed export", "P4-03a"),
                      ("Convolution mixer and attention/convolution hybrid", "P4-04a"),
                      ("Weight sharing, low-rank MLP, magnitude sparsity", "P4-05a")):
        assert comparisons[name].startswith(tid), name
        if task_status(tid) == "BLOCKED":
            assert "BLOCKED" in comparisons[name], name
    assert "no attention:convolution ratio is chosen" in DOC


def test_synthetic_records_carry_no_improvement_claim() -> None:
    for r in p4_records():
        if r["data_kind"] == "synthetic":
            assert {c["type"] for c in r["claims"]} <= {"correctness", "evidence"}, r["experiment_id"]
            assert r["artifact"] is None, r["experiment_id"]


def test_p4_07_done_only_with_its_condition_met() -> None:
    if task_status("P4-07") == "DONE":
        for tid in ("P4-02", "P4-03", "P4-04", "P4-05", "P4-06"):
            assert task_status(tid) == "DONE", tid
        assert "## Status at P4-07 closure" in DOC
    for tid in ("P4-01", "P4-08", "P4-02a", "P4-03a", "P4-04a", "P4-05a"):
        if "OD-03 | ترخيص الأوزان والبيانات المستقبلية | P0-01، P2-07 | OPEN" in ROADMAP:
            assert task_status(tid) == "BLOCKED", tid
