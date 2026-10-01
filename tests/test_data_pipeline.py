"""P2-05: cleaning, PII, dedup, decontamination, provenance, license and quality tools (ADR-0005)."""

from __future__ import annotations

import json
import random
import subprocess
import sys
from pathlib import Path

import pytest

from nawa.data import load_config
from nawa.data.clean import clean_text, looks_mojibake
from nawa.data.decontam import ContaminationIndex, eval_texts, ngram_hashes
from nawa.data.dedup import dedup, jaccard, shingles
from nawa.data.pii import find_pii, iban_ok, luhn_ok, redact, saudi_id_ok
from nawa.data.pipeline import BENCH_LICENSE, CRITERIA, fake_pii, run, run_bench
from nawa.data.provenance import G2_FIELDS, ProvenanceError, license_status, text_hash, validate_output
from nawa.data.quality import language, quality

ROOT = Path(__file__).resolve().parents[1]
CFG = load_config()
RNG = random.Random(99)
DOC = ("كانت القافلة تسير عبر الوادي الطويل حين لاحظ الدليل أن البئر القديمة جفت منذ موسم مضى "
       "فقرر أن يغير الطريق نحو الواحة الشرقية حيث ينتظرهم التجار بالماء والتمر والأخبار الجديدة")


@pytest.fixture(scope="module")
def index() -> ContaminationIndex:
    return ContaminationIndex.build(CFG["decontamination"]["ngram_words"])


def rec(i: int, text: str, license_: str = BENCH_LICENSE) -> dict:
    return {"id": f"r{i}", "text": text, "source": "synthetic:test", "license": license_, "domain": "synthetic",
            "date": "2026-10-01"}


# ---- config -------------------------------------------------------------------------------------

def test_config_has_no_license_list_of_its_own() -> None:
    assert "approved_licenses" not in CFG  # single list lives in configs/verification.yaml (OD-03)
    assert CFG["dedup"]["num_perm"] % CFG["dedup"]["bands"] == 0


# ---- clean --------------------------------------------------------------------------------------

def test_clean_removes_hidden_controls_and_keeps_meaning() -> None:
    raw = "\ufeffمَرْحَبًا\u200b  بالـــعالم\u202e\u2066\u200c\x07\r\n\r\n\r\n\r\nسطر"
    r = clean_text(raw)
    assert r.text == "مَرْحَبًا بالعالم\u200c\n\nسطر"  # diacritics and ZWNJ kept
    assert r.changes["bidi_controls"] == 2 and r.changes["zero_width"] == 2 and r.changes["tatweel"] == 3
    assert clean_text("بالـعالم", remove_tatweel=False).text == "بالـعالم"


def test_clean_maps_presentation_forms_and_flags_mojibake() -> None:
    assert clean_text("\ufe8d\ufedf").text == "ال"
    broken = "مرحبا بالعالم".encode("utf-8").decode("latin-1")
    assert looks_mojibake(broken) and not looks_mojibake("مرحبا بالعالم Hello")
    assert "mojibake" in clean_text(broken).flags


# ---- PII ----------------------------------------------------------------------------------------

def test_checksums() -> None:
    assert luhn_ok("4111 1111 1111 1111") and not luhn_ok("4111 1111 1111 1112")
    assert iban_ok("GB82 WEST 1234 5698 7654 32") and not iban_ok("GB82 WEST 1234 5698 7654 33")
    assert saudi_id_ok(fake_pii("national_id", random.Random(1)))
    assert saudi_id_ok("1000000008") and not saudi_id_ok("1000000000") and not saudi_id_ok("3000000008")


@pytest.mark.parametrize("kind", ["email", "phone", "ipv4", "secret", "card", "national_id", "iban"])
def test_each_pii_type_is_redacted_without_leaking_value(kind: str) -> None:
    value = fake_pii(kind, RNG)
    text = f"تواصل معنا {value} في أي وقت"
    out, spans = redact(text)
    assert [s.type for s in spans] == [kind]
    assert f"[{kind.upper()}]" in out and value not in out
    assert all(not hasattr(s, "value") for s in spans)


def test_pii_rejects_checksum_failures_and_ordinary_numbers() -> None:
    card = fake_pii("card", RNG)
    bad = card[:-1] + str((int(card[-1]) + 1) % 10)
    assert all(s.type != "card" for s in find_pii(f"رقم {bad}"))
    assert find_pii("ولد عام 1998 وعمره 27 سنة وسعر الكتاب 45.5 ريال وغرفة 1204") == []


def test_pii_handles_arabic_digits() -> None:
    _, spans = redact("الهاتف +٩٦٦ ٥٥ ١٢٣ ٤٥٦٧ فقط")
    assert [s.type for s in spans] == ["phone"]


# ---- dedup --------------------------------------------------------------------------------------

def test_exact_dedup_ignores_whitespace_and_diacritics() -> None:
    r = dedup([("a", DOC), ("b", "  " + DOC.replace(" ", "   ")), ("c", DOC.replace("الوادي", "الوَادِي"))])
    assert r.duplicate_of == {"b": "a", "c": "a"} and set(r.kind.values()) == {"exact"}


def test_near_dedup_is_confirmed_by_exact_jaccard() -> None:
    near = DOC.replace("الطويل", "البعيد")
    other = "نص مختلف تماما عن القافلة يتحدث عن الحساب والهندسة والبرمجة والجبر والقياس والتجربة العلمية"
    r = dedup([("a", DOC), ("b", near), ("c", other)], threshold=0.6)
    assert r.duplicate_of == {"b": "a"} and r.kind["b"] == "near"
    assert r.similarity["b"] == round(jaccard(shingles(DOC), shingles(near)), 4)
    assert dedup([("a", DOC), ("b", near)], threshold=0.99).duplicate_of == {}


def test_dedup_is_deterministic_and_keeps_first() -> None:
    items = [("x", DOC), ("y", DOC + " والسلام")]
    assert dedup(items, threshold=0.7).duplicate_of == dedup(items, threshold=0.7).duplicate_of == {"y": "x"}
    with pytest.raises(ValueError):
        dedup(items, num_perm=10, bands=3)


# ---- decontamination ----------------------------------------------------------------------------

def test_decontamination_never_reads_frozen() -> None:
    with pytest.raises(ValueError):
        eval_texts(["frozen"])


def test_decontamination_flags_dev_overlap_and_frozen_hash(index: ContaminationIndex) -> None:
    dev = next(t for t in eval_texts(["dev"]) if len(t.split()) >= 12)
    assert index.check("مقدمة لا علاقة لها " + dev + " خاتمة")[0]
    assert not index.check(DOC)[0]
    frozen_hash = sorted(index.item_hashes)[0]
    assert index.check(DOC, frozen_hash) == (True, "content hash matches a frozen item")


def test_hashed_ngram_index_file_extends_the_index(tmp_path: Path) -> None:
    f = tmp_path / "frozen_ngrams.txt"
    f.write_text("\n".join(sorted(ngram_hashes(DOC, 8))) + "\n", encoding="utf-8")
    idx = ContaminationIndex.build(8, extra_index_files=[f])
    assert idx.check(DOC)[0]


# ---- quality and language -----------------------------------------------------------------------

def test_language_tag() -> None:
    assert language(DOC) == "ar" and language("The caravan crossed the long valley at night") == "en"
    assert language(DOC + " The caravan crossed the long valley at night and rested") == "mixed"
    assert language("123 !!") == "unknown"


@pytest.mark.parametrize("text,flag", [
    ("#$%&*@!" * 30 + " كلمة", "symbols"),
    ("\n".join(["سطر مكرر هنا"] * 10), "repeated_lines"),
    (DOC + " " + "ه" * 60, "char_run"),
])
def test_quality_scales_with_severity(text: str, flag: str) -> None:
    q = quality(text)
    assert flag in q.flags and q.score < CFG["quality"]["min_score"]


def test_clean_text_scores_one() -> None:
    assert quality(DOC).score == 1.0 and quality(DOC).flags == []


# ---- provenance and license ---------------------------------------------------------------------

def test_license_status_uses_the_single_approved_list() -> None:
    assert license_status("x", []) == (False, "license 'x' not approved (OD-03; configs/verification.yaml)")
    assert license_status("", ["x"])[0] is False and license_status("x", ["x"]) == (True, "")


def test_pipeline_output_carries_g2_fields_and_validates(index: ContaminationIndex) -> None:
    out = run([rec(1, DOC)], approved=[BENCH_LICENSE], index=index)
    (k,) = out["kept"]
    assert set(G2_FIELDS) <= set(k) and k["hash"] == text_hash(k["text"]) and k["train_eligible"] is False
    for bad in ({"hash": "0"}, {"train_eligible": True}, {"date": "yesterday"}, {"language": "xx"},
                {"processing_version": "old"}, {"source": ""}):
        with pytest.raises(ProvenanceError):
            validate_output({**k, **bad}, CFG["processing_version"], CFG["languages"])


def test_committed_policy_drops_everything_for_license(index: ContaminationIndex) -> None:
    out = run([rec(1, DOC)], index=index)  # approved list from configs/verification.yaml is empty (OD-03)
    assert out["kept"] == [] and out["dropped"][0]["reason"] == "license"


def test_pipeline_drops_with_reason_and_no_text(index: ContaminationIndex) -> None:
    email = fake_pii("email", RNG)
    recs = [rec(1, DOC + " " + email), rec(2, DOC + " " + email), rec(3, "قصير"),
            {"id": "r4", "text": DOC}, rec(1, DOC + " مكرر")]
    out = run(recs, approved=[BENCH_LICENSE], index=index)
    assert [k["id"] for k in out["kept"]] == ["r1"] and email not in out["kept"][0]["text"]
    reasons = {(d["id"], d["reason"]) for d in out["dropped"]}
    assert reasons == {("r2", "duplicate"), ("r3", "too_short"), ("r4", "invalid_input"), ("r1", "invalid_input")}
    assert all("text" not in d for d in out["dropped"]) and email not in json.dumps(out, ensure_ascii=False)
    assert out["stats"]["input"] == len(out["kept"]) + len(out["dropped"])


# ---- benchmark with pre-registered criteria -----------------------------------------------------

@pytest.mark.parametrize("seed", [2026, 7])
def test_bench_meets_preregistered_criteria(seed: int) -> None:
    rep = run_bench(seed)
    assert rep["criteria"] == CRITERIA and rep["passed"], rep["metrics"]


def test_cli_run_writes_new_dir_and_refuses_overwrite(tmp_path: Path) -> None:
    src = tmp_path / "in.jsonl"
    src.write_text(json.dumps(rec(1, DOC), ensure_ascii=False) + "\n", encoding="utf-8")
    out = tmp_path / "out"
    cmd = [sys.executable, "-m", "nawa.data.pipeline", "run", str(src), "--out-dir", str(out)]
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    assert p.returncode == 0, p.stderr
    assert json.loads((out / "stats.json").read_text(encoding="utf-8"))["dropped"] == {"license": 1}
    assert subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT).returncode != 0
