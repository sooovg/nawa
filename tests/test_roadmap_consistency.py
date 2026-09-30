"""Machine checks that keep ROADMAP.md internally consistent (R-01, ADR-0002)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROADMAP = (ROOT / "ROADMAP.md").read_text(encoding="utf-8")
ALLOWED = {"PLANNED", "CLAIMED", "IN_PROGRESS", "BLOCKED", "FAILED", "DONE", "REJECTED", "SUPERSEDED"}
GATE_ALLOWED = ALLOWED | {"PENDING_REVIEW"}


def section(start: str, end: str) -> str:
    i = ROADMAP.index(start)
    return ROADMAP[i: ROADMAP.index(end, i)]


def defined_tasks() -> dict[int, list[str]]:
    """Task IDs defined in §4 as '**Pn-mm [...]**' (subtasks like P2-03a allowed)."""
    phases = section("# 4. مراحل التنفيذ والبوابات", "# 5. قواعد Git")
    out: dict[int, list[str]] = {}
    for tid in re.findall(r"\*\*(P\d+-\d+[a-z]?) \[", phases):
        out.setdefault(int(tid[1:].split("-")[0]), []).append(tid)
    return out


def status_rows() -> list[list[str]]:
    table = section("## 2.2 سجل المهام", "## 2.3")
    return [[c.strip() for c in l.strip("|").split("|")] for l in table.splitlines()
            if l.startswith("| ") and not l.startswith("| Task ID")]


def test_gate_table_covers_g0_to_g10_in_order() -> None:
    table = section("## 2.1 حالة البوابات", "## 2.2")
    gates = re.findall(r"^\| (G\d+) ", table, flags=re.M)
    assert gates == [f"G{i}" for i in range(11)]
    for line in table.splitlines():
        if re.match(r"^\| G\d+ ", line):
            assert line.split("|")[2].strip() in GATE_ALLOWED, line


def test_every_phase_gate_is_defined_in_section_4() -> None:
    phases = section("# 4. مراحل التنفيذ والبوابات", "# 5. قواعد Git")
    for i in range(11):
        assert re.search(rf"^### G{i}\b", phases, flags=re.M), f"G{i} not defined in §4"


def test_status_statuses_are_allowed() -> None:
    for row in status_rows():
        assert row[1] in ALLOWED, row


def test_status_table_covers_exactly_the_defined_tasks() -> None:
    covered: set[str] = set()
    for row in status_rows():
        tid = row[0]
        m = re.fullmatch(r"P(\d+)-(\d+)\.\.P\1-(\d+)", tid)
        if m:
            ph, lo, hi = int(m[1]), int(m[2]), int(m[3])
            covered |= {f"P{ph}-{n:02d}" for n in range(lo, hi + 1)}
        elif re.fullmatch(r"P\d+-\d+[a-z]?", tid):
            covered.add(tid)
    defined = {t for ts in defined_tasks().values() for t in ts}
    assert covered == defined, {"untracked": sorted(defined - covered), "undefined": sorted(covered - defined)}


def test_no_duplicate_task_rows() -> None:
    ids = [r[0] for r in status_rows()]
    assert len(ids) == len(set(ids))


def test_owner_decision_register_exists() -> None:
    table = section("## 2.4 قرارات المالك المطلوبة", "# 3. بنية المستودعات")
    assert len(re.findall(r"^\| OD-\d\d ", table, flags=re.M)) >= 1


def test_changelog_has_entries() -> None:
    log = ROADMAP[ROADMAP.index("# 12. سجل التغييرات"):]
    assert len(re.findall(r"^\| \d+\.\d+\.\d+", log, flags=re.M)) >= 2
