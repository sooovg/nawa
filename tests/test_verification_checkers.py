"""P6-04: claims checked against provided evidence by independent deterministic checkers (ADR-0008).

Pass/fail criteria, written before the run (ADR-0008 D2):

K1. The verifier returns exactly one of the five P6-08 states. A claim is SUPPORTED only when a checker found
    entailing evidence: a provided evidence id, or a computation id (``calc:``/``exec:``).
K2. Only provided evidence is used. A fact absent from the evidence is INSUFFICIENT_EVIDENCE, whatever is true in the
    world. Synthetic evidence that disagrees with the claim makes it CONTRADICTED.
K3. Planted conflicts are found, and consistent evidence is never flagged.
K4. Negative controls: an unsupported claim is never SUPPORTED; a planted contradiction is CONTRADICTED; a checker
    that always agrees cannot turn a contradicted claim into SUPPORTED.
K5. The checkers are independent: each one's findings are the same alone, with the others, and in any order.
K6. Determinism: the same input gives the same JSON report, under any order of claims and evidence.

No external model, no network, no real data. The data is synthetic and made in this file. No claim about hallucination.
"""

from __future__ import annotations

import itertools
import json
import random
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

import pytest

from nawa.tools.files import FileInspector
from nawa.tools.sandbox import SandboxPolicy
from nawa.verification import (ArithmeticClaim, CalculatorChecker, CodeClaim, Evidence, FactClaim, FactRecord,
                               Finding, QuoteChecker, RecordChecker, Relation, SandboxChecker, TextClaim,
                               VerificationState, check, consensus, default_checkers, evidence_from_files,
                               extract_claims, find_quote, norm_value, uncertainty)

S = VerificationState
FAST = SandboxPolicy(timeout_s=2)


def state_of(report, cid: str) -> VerificationState:
    return {c.claim_id: c.state for c in report.verdict.claims}[cid]


# ==== values and extraction =========================================================================================
@pytest.mark.parametrize("a,b", [("٣٫٥", "3.50"), ("7/2", "3.5"), ("2,385,509", "2385509"), ("٢٣٨٥٥٠٩", 2385509),
                                 ("  الرياض ", "الرياض"), ("مكّة", "مكة"), ("أحمد", "احمد"), ("-0.5", "-1/2")])
def test_values_normalise_to_the_same_value(a, b) -> None:
    assert norm_value(a) == norm_value(b)


@pytest.mark.parametrize("a,b", [("3.5", "3.05"), ("10", "100"), ("الرياض", "جدة"), ("1/3", "0.333")])
def test_different_values_stay_different(a, b) -> None:
    assert norm_value(a) != norm_value(b)


def test_float_values_are_refused_to_keep_values_exact() -> None:
    with pytest.raises(ValueError):
        norm_value(0.1)


def test_extract_claims_structured_answer() -> None:
    cl = extract_claims("مكة تقع في السعودية [e1]. ٢ + ٣ × ٤ = ١٤. Pi is about 3.14 [e2]! x = 5. 7/2 = 3.5؟ "
                        "سطر آخر [e1][e3]\n\n")
    assert [type(c).__name__ for c in cl] == ["TextClaim", "ArithmeticClaim", "TextClaim", "TextClaim",
                                              "ArithmeticClaim", "TextClaim"]
    assert [c.claim_id for c in cl] == ["c1", "c2", "c3", "c4", "c5", "c6"]
    assert cl[0].citations == ("e1",) and cl[1].expression == "2 + 3 × 4" and cl[1].value == "14"
    assert cl[2].text == "Pi is about 3.14" and cl[5].citations == ("e1", "e3")
    assert extract_claims("") == [] and extract_claims(" [e1]. ") == []


# ==== K1/K4: checker outcomes =======================================================================================
def test_calculator_checker() -> None:
    r = check([ArithmeticClaim("a1", "2 + 3 × 4", "14"), ArithmeticClaim("a2", "2 + 3 × 4", "20"),
               ArithmeticClaim("a3", "0.1 + 0.2", "0.3"), ArithmeticClaim("a4", "1/0", "1"),
               ArithmeticClaim("a5", "2 + 2", "four"), ArithmeticClaim("a6", "abs(-1)", "1")])
    assert [state_of(r, f"a{i}") for i in range(1, 7)] == [S.SUPPORTED, S.CONTRADICTED, S.SUPPORTED, S.UNCERTAIN,
                                                          S.UNCERTAIN, S.UNCERTAIN]
    assert all(f.evidence_id.startswith("calc:") for f in r.findings if f.relation is Relation.ENTAILS)


def test_sandbox_checker_including_denials_and_timeouts() -> None:
    cks = [SandboxChecker(policy=FAST)]
    r = check([CodeClaim("k1", "print(sum(range(10)))", "45"), CodeClaim("k2", "print(sum(range(10)))", "46"),
               CodeClaim("k3", "import socket\nprint(1)", "1"), CodeClaim("k4", "while True: pass", ""),
               CodeClaim("k5", "raise SystemExit(3)", ""), CodeClaim("k6", "print('x' * 9000)", "x" * 9000)],
              checkers=cks)
    assert [state_of(r, f"k{i}") for i in range(1, 7)] == [S.SUPPORTED, S.CONTRADICTED, S.UNCERTAIN, S.UNCERTAIN,
                                                          S.UNCERTAIN, S.UNCERTAIN]
    d = {f.claim_id: f.detail for f in r.findings}
    assert d["k3"] == "execution_failed:denied:import" and d["k4"].startswith("execution_failed")
    assert d["k6"] == "output_truncated"


EV = [Evidence("e1", "مكة المكرمة تقع في المملكة العربية السعودية.",
               (FactRecord("مدينة س", "عدد السكان", "1,200"), FactRecord("مدينة س", "الارتفاع", "277", "m"))),
      Evidence("e2", "ليس صحيحًا أن مدينة س هي العاصمة. The tower is 300 m tall.",
               (FactRecord("مدينة س", "عدد السكان", "1200"),)),
      Evidence("e3", "Unrelated text about rivers.", ())]


@pytest.mark.parametrize("claim,state", [
    (FactClaim("f", "مدينة س", "عدد السكان", "١٢٠٠"), S.SUPPORTED),
    (FactClaim("f", "مدينة س", "عدد السكان", "1300"), S.CONTRADICTED),
    (FactClaim("f", "مدينة س", "الارتفاع", "277", "m"), S.SUPPORTED),
    (FactClaim("f", "مدينة س", "الارتفاع", "277", "ft"), S.UNCERTAIN),          # unit mismatch: no conversion
    (FactClaim("f", "مدينة س", "المساحة", "50"), S.INSUFFICIENT_EVIDENCE),     # no record
    (FactClaim("f", "مدينة ص", "عدد السكان", "1200"), S.INSUFFICIENT_EVIDENCE),
    (FactClaim("f", "مدينة س", "عدد السكان", "1200", citations=("e3",)), S.INSUFFICIENT_EVIDENCE),  # cited: only e3
    (FactClaim("f", "مدينة س", "عدد السكان", "1200", citations=("e9",)), S.INSUFFICIENT_EVIDENCE),  # unknown cite
    (TextClaim("t", "مكة المكرمة تقع في المملكة العربية السعودية", ("e1",)), S.SUPPORTED),
    (TextClaim("t", "مكه المكرمه تقع في المملكه العربيه السعوديه", ("e1",)), S.SUPPORTED),       # normalisation
    (TextClaim("t", "مكة المكرمة تقع في المملكة العربية السعودية", ()), S.INSUFFICIENT_EVIDENCE),   # uncited
    (TextClaim("t", "مكة المكرمة تقع في المملكة العربية السعودية", ("e3",)), S.INSUFFICIENT_EVIDENCE),  # wrong cite
    (TextClaim("t", "مدينة س هي العاصمة", ("e2",)), S.UNCERTAIN),               # negation before the quote
    (TextClaim("t", "The tower is 300 m tall", ("e2",)), S.SUPPORTED),
    (TextClaim("t", "The tower is 30 m tall", ("e2",)), S.INSUFFICIENT_EVIDENCE),
    (TextClaim("t", "tower is 300", ("e2",)), S.SUPPORTED),
    (TextClaim("t", "ower is 300", ("e2",)), S.INSUFFICIENT_EVIDENCE),          # token boundaries, not substrings
])
def test_record_and_quote_checkers(claim, state) -> None:
    assert state_of(check([claim], EV), claim.claim_id) is state


def test_find_quote_negation_rules() -> None:
    assert find_quote("x is big", "they say x is big") == (True, False)
    assert find_quote("x is big", "it is not true x is big") == (True, True)
    assert find_quote("x is big", "not x is big, but later: x is big") == (True, False)   # one clean occurrence
    assert find_quote("x is not big", "x is not big") == (True, False)                    # negation inside quote
    assert find_quote("", "anything") == (False, False)


# ==== K2: evidence only =============================================================================================
def test_only_provided_evidence_counts() -> None:
    true_in_world = FactClaim("w", "Makkah", "country", "Saudi Arabia")
    assert state_of(check([true_in_world], []), "w") is S.INSUFFICIENT_EVIDENCE
    assert state_of(check([true_in_world], EV), "w") is S.INSUFFICIENT_EVIDENCE
    planted = [Evidence("p1", records=(FactRecord("Makkah", "country", "Atlantis"),))]   # synthetic, deliberately odd
    assert state_of(check([true_in_world], planted), "w") is S.CONTRADICTED
    text = TextClaim("q", "Makkah is in Saudi Arabia", ("p1",))
    assert state_of(check([text], planted), "q") is S.INSUFFICIENT_EVIDENCE


def test_unsupported_claim_never_supported_and_flagged_in_strict_mode() -> None:
    cl = [TextClaim("c1", "مكة المكرمة تقع في المملكة العربية السعودية", ("e1",)),
          TextClaim("c2", "a sentence no evidence contains", ("e1",))]
    r = check(cl, EV)
    assert r.verdict.state is S.PARTIALLY_SUPPORTED and not r.strict_ok and r.flagged == ("c2",)


def test_checker_cannot_cite_evidence_that_was_not_provided() -> None:
    @dataclass(frozen=True)
    class Liar:
        name: str = "liar"
        kind: type = TextClaim

        def check(self, claim, evidence):
            return [Finding(claim.claim_id, Relation.ENTAILS, self.name, "made_up_source")]
    with pytest.raises(ValueError, match="not provided"):
        check([TextClaim("t", "x", ("e1",))], EV, checkers=[Liar()])


def test_reserved_computation_ids_cannot_be_used_as_evidence() -> None:
    with pytest.raises(ValueError):
        Evidence("calc:abc", "x")


# ==== K3: contradiction and consensus ===============================================================================
def test_evidence_conflicts_found_and_consistent_evidence_not_flagged() -> None:
    assert check([], EV).evidence_conflicts == ()        # 1,200 and 1200 agree
    planted = EV + [Evidence("e4", records=(FactRecord("مدينة س", "عدد السكان", "1500"),))]
    (c,) = check([], planted).evidence_conflicts
    assert c.values == (("n:1200", ("e1", "e2")), ("n:1500", ("e4",)))
    r = check([FactClaim("f", "مدينة س", "عدد السكان", "1200")], planted)
    assert state_of(r, "f") is S.UNCERTAIN              # C3: no majority vote, 2 against 1 is still a conflict


def test_answer_contradicting_itself_fails_strict_mode() -> None:
    cl = [FactClaim("a", "مدينة س", "عدد السكان", "1200"), FactClaim("b", "مدينة س", "عدد السكان", "1300")]
    r = check(cl, [])
    assert len(r.claim_conflicts) == 1 and set(r.flagged) == {"a", "b"} and not r.strict_ok


def test_citations_cannot_cherry_pick_a_source_and_hide_a_conflicting_one() -> None:
    """Found by a surviving mutation (first design): when citations scoped contradiction too, each claim could cite
    its own source and come out SUPPORTED. Now only support is scoped; any provided record can contradict."""
    ev = EV + [Evidence("e5", records=(FactRecord("مدينة س", "عدد السكان", "1300"),))]
    cl = [FactClaim("a", "مدينة س", "عدد السكان", "1200", citations=("e1",)),
          FactClaim("b", "مدينة س", "عدد السكان", "1300", citations=("e5",))]
    r = check(cl, ev)
    assert state_of(r, "a") is S.UNCERTAIN and state_of(r, "b") is S.UNCERTAIN
    assert not r.strict_ok and set(r.flagged) == {"a", "b"} and len(r.evidence_conflicts) == 1
    assert state_of(check([cl[0]], EV), "a") is S.SUPPORTED          # without the conflicting source: supported


def test_strict_mode_refuses_a_self_contradicting_answer_even_if_every_claim_is_supported() -> None:
    """Defence in depth: a checker (here a stub that always agrees) can support both claims; strict mode still fails."""
    cl = [FactClaim("a", "مدينة س", "عدد السكان", "1200"), FactClaim("b", "مدينة س", "عدد السكان", "1300")]
    r = check(cl, EV, checkers=[AlwaysAgree()])
    assert r.verdict.state is S.SUPPORTED and not r.strict_ok and set(r.flagged) == {"a", "b"}


def test_strict_mode_needs_both_support_and_self_consistency() -> None:
    cl = [FactClaim("a", "مدينة س", "عدد السكان", "1200"), FactClaim("b", "مدينة س", "الارتفاع", "277", "m")]
    r = check(cl, EV)
    assert r.verdict.state is S.SUPPORTED and r.strict_ok and r.flagged == ()


def test_consensus_requires_unanimity() -> None:
    ev = {e.evidence_id: e for e in EV}
    c = consensus(ev, "مدينة س", "عدد السكان")
    assert c.unanimous and c.value == "n:1200" and c.n_sources == 2
    ev["e4"] = Evidence("e4", records=(FactRecord("مدينة س", "عدد السكان", "1500"),))
    c = consensus(ev, "مدينة س", "عدد السكان")
    assert not c.unanimous and c.value is None and c.n_sources == 3
    assert consensus(ev, "مدينة س", "شيء").values == ()


def test_uncertainty_is_descriptive_not_calibrated() -> None:
    r = check([ArithmeticClaim("a", "1+1", "2"), ArithmeticClaim("b", "1+1", "3"), TextClaim("c", "x", ())])
    u = uncertainty(r.verdict)
    assert u["counts"] == {"SUPPORTED": 1, "UNCERTAIN": 0, "CONTRADICTED": 1, "INSUFFICIENT_EVIDENCE": 1}
    assert u["supported_fraction"] == Fraction(1, 3) and u["calibrated"] is False
    assert uncertainty(check([]).verdict)["supported_fraction"] is None


# ==== K4: stub checkers (oracle and wrong-on-purpose) ===============================================================
@dataclass(frozen=True)
class AlwaysAgree:
    name: str = "always_agree"
    kind: type = FactClaim

    def check(self, claim, evidence):
        return [Finding(claim.claim_id, Relation.ENTAILS, self.name, eid) for eid in sorted(evidence)]


def test_a_checker_that_always_agrees_cannot_make_a_contradicted_claim_supported() -> None:
    claim = FactClaim("f", "مدينة س", "عدد السكان", "1300")
    r = check([claim], EV, checkers=[RecordChecker(), AlwaysAgree()])
    assert state_of(r, "f") is S.UNCERTAIN                       # C3, never SUPPORTED
    assert state_of(check([claim], EV, checkers=[AlwaysAgree()]), "f") is S.SUPPORTED   # alone it would lie


# ==== synthetic worlds: independent expected states =================================================================
def world(seed: int):
    """Random structured evidence with known ground truth per (subject, attribute), and claims whose expected state
    is decided here from the generator's own labels, not by the code under test."""
    rng = random.Random(seed)
    subjects, attrs = [f"subj{i}" for i in range(4)], [f"attr{j}" for j in range(3)]
    truth = {(s, a): rng.randint(1, 50) for s in subjects for a in attrs}
    evidence, label = [], {}
    for k in range(rng.randint(1, 4)):
        recs = []
        for key in rng.sample(sorted(truth), rng.randint(0, len(truth))):
            v = truth[key] if rng.random() < 0.85 else truth[key] + rng.randint(1, 9)    # planted errors
            recs.append(FactRecord(key[0], key[1], str(v)))
            label.setdefault(key, set()).add(v)
        evidence.append(Evidence(f"src{k}", records=tuple(recs)))
    claims, expected = [], {}
    for i, key in enumerate(sorted(truth)):
        v = truth[key] if rng.random() < 0.5 else truth[key] + 1
        cid = f"f{i}"
        claims.append(FactClaim(cid, key[0], key[1], str(v)))
        vals = label.get(key, set())
        if not vals:
            expected[cid] = S.INSUFFICIENT_EVIDENCE
        elif vals == {v}:
            expected[cid] = S.SUPPORTED
        elif v in vals:
            expected[cid] = S.UNCERTAIN
        else:
            expected[cid] = S.CONTRADICTED
    n_conflicts = sum(len(v) > 1 for v in label.values())
    return claims, evidence, expected, n_conflicts


def test_synthetic_worlds_match_expected_states_and_conflicts() -> None:
    seen = set()
    for seed in range(300):
        claims, evidence, expected, n_conflicts = world(seed)
        r = check(claims, evidence)
        got = {c.claim_id: c.state for c in r.verdict.claims}
        assert got == expected, seed
        assert len(r.evidence_conflicts) == n_conflicts, seed
        assert all(c.state in set(S) for c in r.verdict.claims)
        seen |= set(got.values())
    assert seen == {S.SUPPORTED, S.CONTRADICTED, S.UNCERTAIN, S.INSUFFICIENT_EVIDENCE}


def test_supported_always_has_entailing_evidence() -> None:
    for seed in range(100):
        claims, evidence, _, _ = world(seed)
        r = check(claims, evidence)
        ids = {e.evidence_id for e in evidence}
        for c in r.verdict.claims:
            if c.state is S.SUPPORTED:
                assert c.supporting and set(c.supporting) <= ids and not c.contradicting


# ==== K5/K6: independence and determinism ===========================================================================
MIXED = [ArithmeticClaim("a", "6*7", "42"), CodeClaim("k", "print(6*7)", "42"),
         FactClaim("f", "مدينة س", "عدد السكان", "1200"), TextClaim("t", "The tower is 300 m tall", ("e2",)),
         TextClaim("u", "nothing", ())]


def test_checkers_are_independent_of_each_other_and_of_order() -> None:
    cks = default_checkers(FAST)
    alone = {k.name: [f for f in check(MIXED, EV, checkers=[k]).findings] for k in cks}
    for perm in itertools.permutations(cks):
        together = check(MIXED, EV, checkers=perm).findings
        for k in cks:
            assert [f for f in together if f.checker == k.name] == alone[k.name]


def test_report_is_deterministic_under_reordering() -> None:
    base = json.dumps(check(MIXED, EV, checkers=default_checkers(FAST)).to_dict(), ensure_ascii=False, sort_keys=True)
    for cl, ev in [(MIXED[::-1], EV[::-1]), (MIXED[2:] + MIXED[:2], EV[1:] + EV[:1])]:
        again = json.dumps(check(cl, ev, checkers=default_checkers(FAST)).to_dict(), ensure_ascii=False,
                           sort_keys=True)
        assert again == base


def test_claims_without_a_checker_are_listed_and_insufficient() -> None:
    r = check(MIXED, EV, checkers=[CalculatorChecker(), QuoteChecker()])
    assert r.unchecked == ("f", "k") and state_of(r, "f") is S.INSUFFICIENT_EVIDENCE


def test_inputs_are_validated() -> None:
    with pytest.raises(ValueError):
        check(["not a claim"])                                   # type: ignore[list-item]
    with pytest.raises(ValueError):
        check(MIXED, EV + [EV[0]])                               # duplicate evidence id
    with pytest.raises(ValueError):
        check(MIXED, EV, checkers=[QuoteChecker(), QuoteChecker()])
    with pytest.raises(ValueError):
        check([TextClaim("a", "x"), TextClaim("a", "y")])        # duplicate claim id


# ==== evidence from files (read-only, P6-02) ========================================================================
def test_evidence_from_files_pins_content_and_refuses_partial_reads(tmp_path: Path) -> None:
    (tmp_path / "doc.txt").write_text("النص الكامل للوثيقة هنا.", encoding="utf-8")
    (tmp_path / "big.txt").write_text("x" * 5000, encoding="utf-8")
    fi = FileInspector(tmp_path, max_bytes=1000)
    (ev,) = evidence_from_files(fi, ["doc.txt"])
    assert ev.evidence_id.startswith("file:doc.txt@") and len(ev.evidence_id.split("@")[1]) == 12
    r = check([TextClaim("t", "النص الكامل للوثيقة", (ev.evidence_id,))], [ev])
    assert state_of(r, "t") is S.SUPPORTED
    with pytest.raises(ValueError, match="whole"):
        evidence_from_files(fi, ["big.txt"])
