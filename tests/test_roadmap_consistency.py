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


def test_p1_06_is_not_circular_and_anchoring_is_a_g5_condition() -> None:
    """R-04 / ADR-0004: P1-06 must not wait for a model that cannot read text, and the numeric anchoring
    (P1-06a) must block G5, not G1, so there is no G1 <-> P5 loop."""
    rows = {r[0]: r for r in status_rows()}
    assert "P1-06" in rows and "P1-06a" in rows
    assert "P3-05" not in rows["P1-06"][3], rows["P1-06"]
    assert "ADR-0004" in rows["P1-06"][3] and "G5" in rows["P1-06a"][3]
    phases = section("# 4. مراحل التنفيذ والبوابات", "# 5. قواعد Git")
    g1 = phases[phases.index("### G1"):phases.index("## P2")]
    g5 = phases[phases.index("### G5"):phases.index("## P6")]
    assert "P1-06a" not in g1 and "P1-06a" in g5
    assert (ROOT / "docs/decisions/ADR-0004-p1-06-dependency.md").is_file()


def test_p2_code_scope_split_keeps_data_production_blocked_and_g2_unchanged() -> None:
    """R-05 / ADR-0005: P2 code tasks are unblocked under §0; data-production tasks stay BLOCKED;
    G2 keeps every condition, so no gate is weakened."""
    rows = {r[0]: r for r in status_rows()}
    assert "P2-01..P2-08" not in rows
    for tid in ("P2-01", "P2-06", "P2-07", "P2-08"):
        assert rows[tid][1] == "BLOCKED", rows[tid]
        assert "ADR-0005" in rows[tid][3], rows[tid]
    for tid in ("P2-02", "P2-03", "P2-04", "P2-05"):
        assert rows[tid][1] in {"PLANNED", "CLAIMED", "IN_PROGRESS", "DONE"}, rows[tid]
    phases = section("# 4. مراحل التنفيذ والبوابات", "# 5. قواعد Git")
    g2 = phases[phases.index("### G2"):phases.index("## P3")]
    for condition in ("200 مثال", "صفر تسرب", "source/license/language/domain/quality/date/hash/processing_version",
                      "لا بيانات غير مرخصة"):
        assert condition in g2, condition
    assert (ROOT / "docs/decisions/ADR-0005-p2-code-scope.md").is_file()


def test_p4_code_scope_split_blocks_curves_and_upload_and_keeps_g4_unchanged() -> None:
    """R-06 / ADR-0007: P4 code tasks are unblocked under §0 without adopting any technique; scaling curves
    (P4-01) and HF upload (P4-08) stay BLOCKED; G4 keeps every condition, so no gate is weakened."""
    rows = {r[0]: r for r in status_rows()}
    assert "P4-01..P4-08" not in rows
    for tid in ("P4-01", "P4-08"):
        assert rows[tid][1] == "BLOCKED", rows[tid]
        assert "ADR-0007" in rows[tid][3], rows[tid]
    for tid in ("P4-02", "P4-03", "P4-04", "P4-05", "P4-06", "P4-07"):
        assert rows[tid][1] in {"PLANNED", "CLAIMED", "IN_PROGRESS", "DONE", "FAILED"}, rows[tid]
    phases = section("# 4. مراحل التنفيذ والبوابات", "# 5. قواعد Git")
    p4 = phases[phases.index("## P4"):phases.index("## P5")]
    g4 = p4[p4.index("### G4"):]
    for condition in ("scaling curves موجودة", "كل ادعاء معماري له ablation", "لا تقنية مفروضة"):
        assert condition in g4, condition
    assert "لا يصبح NAWA “ternary” أو “hybrid” أو “MoE” رسميًا إلا بعد أن تثبت بوابة مستقلة" in p4
    assert "ADR-0007" in p4 and "لا تُعتمد أي تقنية" in p4
    assert (ROOT / "docs/decisions/ADR-0007-p4-code-scope.md").is_file()


def test_task_reports_record_a_commit_or_pr() -> None:
    """R-06: every completion report in §2.3 names its commit or PR, not a placeholder."""
    reports = section("## 2.3 تقارير إنجاز المهام", "## 2.4 ")
    for part in re.split(r"(?m)^(?=### )", reports)[1:]:
        m = re.search(r"\*\*Git commit:\*\* (.+)", part)
        assert m, part.splitlines()[0]
        assert re.search(r"PR #\d+|`[0-9a-f]{7,40}`", m[1]), part.splitlines()[0]


def test_p4_real_text_comparisons_are_tracked_and_g4_stays_open() -> None:
    """R-06 / ADR-0007 D1, D3: each comparison study has a real-text subtask that stays BLOCKED and is a G4 condition,
    and G4 cannot be closed while P4-01 (scaling curves) is not done."""
    rows = {r[0]: r for r in status_rows()}
    for tid in ("P4-02a", "P4-03a", "P4-04a", "P4-05a"):
        assert rows[tid][1] in {"BLOCKED", "PLANNED", "CLAIMED", "IN_PROGRESS", "DONE", "FAILED"}, rows[tid]
        assert "ADR-0007" in rows[tid][3], rows[tid]
    phases = section("# 4. مراحل التنفيذ والبوابات", "# 5. قواعد Git")
    g4 = phases[phases.index("### G4"):phases.index("## P5")]
    assert "P4-02a وP4-03a وP4-04a وP4-05a" in g4
    gates = section("## 2.1 حالة البوابات", "## 2.2")
    g4_status = re.search(r"^\| G4 [^|]*\| (\w+) \|", gates, flags=re.M)[1]
    if rows["P4-01"][1] != "DONE" or any(rows[t][1] != "DONE" for t in ("P4-02a", "P4-03a", "P4-04a", "P4-05a")):
        assert g4_status not in {"DONE", "PENDING_REVIEW"}, g4_status


def test_p6_code_scope_split_blocks_model_dependent_parts_and_strengthens_g6() -> None:
    """R-08 / ADR-0008: P6 code tasks are unblocked under §0 with no external model, no network and no quality claim;
    the parts that need a trained core, real data or an owner decision stay BLOCKED; G6 keeps every condition and
    gains one; OD-11 is registered."""
    rows = {r[0]: r for r in status_rows()}
    assert "P6-01..P6-09" not in rows
    for tid in ("P6-01", "P6-02", "P6-03", "P6-04", "P6-05", "P6-06", "P6-07", "P6-08"):
        assert rows[tid][1] in {"PLANNED", "CLAIMED", "IN_PROGRESS", "DONE", "FAILED"}, rows[tid]
        assert "ADR-0008" in rows[tid][3], rows[tid]
    gates = section("## 2.1 حالة البوابات", "## 2.2")
    g5_status = re.search(r"^\| G5 [^|]*\| (\w+) \|", gates, flags=re.M)[1]
    for tid in ("P6-01a", "P6-02a", "P6-03a", "P6-04a", "P6-05a", "P6-09"):
        assert "ADR-0008" in rows[tid][3], rows[tid]
        if tid != "P6-02a" and g5_status != "DONE":
            assert rows[tid][1] == "BLOCKED", rows[tid]
    odt = section("## 2.4 قرارات المالك المطلوبة", "# 3. بنية المستودعات")
    od11 = re.search(r"^\| OD-11 \|[^\n]*\| (\w+) \|$", odt, flags=re.M)
    assert od11 and "P6-02a" in od11[0]
    if od11[1] == "OPEN":
        assert rows["P6-02a"][1] == "BLOCKED", rows["P6-02a"]
    phases = section("# 4. مراحل التنفيذ والبوابات", "# 5. قواعد Git")
    p6 = phases[phases.index("## P6"):phases.index("## P7")]
    g6 = p6[p6.index("### G6"):]
    for condition in ("تحقق واضح الادعاء مقابل الدليل", "امتنع النظام عند نقص الدليل دون انهيار في التغطية",
                      "لا يمر ادعاء غير مدعوم بصمت في الوضع الدقيق", "المخاطر والتغطية مقاسة بمنحنى risk–coverage",
                      "P6-01a وP6-02a وP6-03a وP6-04a وP6-05a وP6-09 منجزة على نواة NAWA مدربة"):
        assert condition in g6, condition
    assert "ADR-0008" in p6 and "دون أي نموذج خارجي" in p6 and "دون شبكة" in p6
    g6_status = re.search(r"^\| G6 [^|]*\| (\w+) \|", gates, flags=re.M)[1]
    if g5_status != "DONE" or any(rows[t][1] != "DONE" for t in ("P6-01a", "P6-03a", "P6-04a", "P6-05a", "P6-09")):
        assert g6_status not in {"DONE", "PENDING_REVIEW"}, g6_status
    assert (ROOT / "docs/decisions/ADR-0008-p6-code-scope.md").is_file()
