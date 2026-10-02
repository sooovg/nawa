"""P6-08: the five verification states and their rules (ADR-0008). Deterministic tests only.

These tests prove the rules are implemented as written. They say nothing about NAWA's answers or hallucination.
"""

from __future__ import annotations

import itertools
import json
import re
from pathlib import Path

import pytest

from nawa.verification import states as vs
from nawa.verification.states import (CLAIM_REASONS, AnswerVerdict, ClaimVerdict, Finding, Relation,
                                      VerificationState, answer_state, claim_state, flagged_claims, passes_strict,
                                      verify)

ROOT = Path(__file__).resolve().parents[1]
S, R = VerificationState, Relation
RELS = list(Relation)
CLAIM_STATES = [S.SUPPORTED, S.UNCERTAIN, S.CONTRADICTED, S.INSUFFICIENT_EVIDENCE]


def finding(rel: Relation, i: int = 0, claim: str = "c1") -> Finding:
    ev = f"e{i}" if rel in (R.ENTAILS, R.CONTRADICTS) else None
    return Finding(claim, rel, f"checker{i}", ev)


# ---- an independent reference, written from counts rather than as ordered rules ------------------------------------
def ref_claim(rels: list[Relation]) -> VerificationState:
    e, c, u = rels.count(R.ENTAILS), rels.count(R.CONTRADICTS), rels.count(R.UNDECIDED)
    if e + c + u == 0:
        return S.INSUFFICIENT_EVIDENCE
    if c:
        return S.UNCERTAIN if e else S.CONTRADICTED
    return S.UNCERTAIN if u else S.SUPPORTED


def ref_answer(sts: list[VerificationState]) -> VerificationState:
    n_sup, n_con, n_unc = sts.count(S.SUPPORTED), sts.count(S.CONTRADICTED), sts.count(S.UNCERTAIN)
    if not sts:
        return S.INSUFFICIENT_EVIDENCE
    if n_con:
        return S.CONTRADICTED
    if n_sup == len(sts):
        return S.SUPPORTED
    if n_sup:
        return S.PARTIALLY_SUPPORTED
    return S.UNCERTAIN if n_unc else S.INSUFFICIENT_EVIDENCE


def all_sequences(alphabet: list, max_len: int):
    for n in range(max_len + 1):
        yield from itertools.product(alphabet, repeat=n)


# ---- the vocabulary matches the roadmap ---------------------------------------------------------------------------
def test_states_are_exactly_the_five_roadmap_states() -> None:
    roadmap = (ROOT / "ROADMAP.md").read_text(encoding="utf-8")
    block = re.search(r"\*\*P6-08 \[Git\]\*\*[^`]*```text\n(.*?)```", roadmap, flags=re.S)[1]
    assert [s.value for s in VerificationState] == block.split()
    assert len(VerificationState) == 5 and len(Relation) == 4


# ---- finding validation -------------------------------------------------------------------------------------------
@pytest.mark.parametrize("kw", [
    dict(claim_id="", relation=R.ENTAILS, checker="x", evidence_id="e"),
    dict(claim_id="c", relation=R.ENTAILS, checker="", evidence_id="e"),
    dict(claim_id="c", relation=R.ENTAILS, checker="x"),                       # support without a citation
    dict(claim_id="c", relation=R.CONTRADICTS, checker="x", evidence_id=" "),
    dict(claim_id="c", relation="ENTAILS", checker="x", evidence_id="e"),      # not a Relation
    dict(claim_id="c", relation=R.NEUTRAL, checker="x", evidence_id=""),
    dict(claim_id="c", relation=R.UNDECIDED, checker="x", detail=3),
])
def test_finding_rejects_invalid(kw: dict) -> None:
    with pytest.raises(ValueError):
        Finding(**kw)


def test_neutral_and_undecided_need_no_evidence() -> None:
    assert Finding("c", R.NEUTRAL, "x").evidence_id is None
    assert Finding("c", R.UNDECIDED, "x", detail="timeout").detail == "timeout"


# ---- claim rules C1..C6 -------------------------------------------------------------------------------------------
def test_claim_rules_exhaustively_match_the_reference() -> None:
    n = 0
    for seq in all_sequences(RELS, 4):
        v = claim_state("c1", [finding(r, i) for i, r in enumerate(seq)])
        assert v.state is ref_claim(list(seq)), seq
        assert v.state is not S.PARTIALLY_SUPPORTED and v.reason in CLAIM_REASONS
        n += 1
    assert n == sum(4 ** k for k in range(5))


@pytest.mark.parametrize("rels,state,reason", [
    ([], S.INSUFFICIENT_EVIDENCE, "no_evidence"),
    ([R.NEUTRAL, R.NEUTRAL], S.INSUFFICIENT_EVIDENCE, "no_relevant_evidence"),
    ([R.ENTAILS, R.CONTRADICTS], S.UNCERTAIN, "conflicting_evidence"),
    ([R.ENTAILS, R.CONTRADICTS, R.UNDECIDED], S.UNCERTAIN, "conflicting_evidence"),
    ([R.CONTRADICTS, R.NEUTRAL], S.CONTRADICTED, "contradicted"),
    ([R.CONTRADICTS, R.UNDECIDED], S.CONTRADICTED, "contradicted"),
    ([R.UNDECIDED], S.UNCERTAIN, "checker_undecided"),
    ([R.ENTAILS, R.UNDECIDED], S.UNCERTAIN, "checker_undecided"),
    ([R.ENTAILS], S.SUPPORTED, "supported"),
    ([R.ENTAILS, R.NEUTRAL, R.ENTAILS], S.SUPPORTED, "supported"),
])
def test_each_claim_rule_with_its_reason(rels: list[Relation], state: VerificationState, reason: str) -> None:
    v = claim_state("c1", [finding(r, i) for i, r in enumerate(rels)])
    assert (v.state, v.reason) == (state, reason)


def test_claim_verdict_lists_evidence_sorted_and_unique() -> None:
    fs = [Finding("c", R.ENTAILS, "a", "e2"), Finding("c", R.ENTAILS, "b", "e1"), Finding("c", R.ENTAILS, "c", "e2"),
          Finding("c", R.CONTRADICTS, "d", "e9"), Finding("c", R.UNDECIDED, "z"), Finding("c", R.UNDECIDED, "y")]
    v = claim_state("c", fs)
    assert v.supporting == ("e1", "e2") and v.contradicting == ("e9",) and v.undecided_checkers == ("y", "z")


def test_claim_state_rejects_foreign_findings() -> None:
    with pytest.raises(ValueError):
        claim_state("c1", [finding(R.ENTAILS, claim="c2")])
    with pytest.raises(ValueError):
        claim_state("c1", ["ENTAILS"])


# ---- answer rules A1..A6 ------------------------------------------------------------------------------------------
def test_answer_rules_exhaustively_match_the_reference() -> None:
    for seq in all_sequences(CLAIM_STATES, 4):
        verdicts = [ClaimVerdict(f"c{i}", st, "x") for i, st in enumerate(seq)]
        assert answer_state(verdicts)[0] is ref_answer(list(seq)), seq


def test_partially_supported_is_answer_level_only() -> None:
    with pytest.raises(ValueError):
        answer_state([ClaimVerdict("c", S.PARTIALLY_SUPPORTED, "x")])
    assert answer_state([ClaimVerdict("a", S.SUPPORTED, "x"), ClaimVerdict("b", S.UNCERTAIN, "x")]) == (
        S.PARTIALLY_SUPPORTED, "some_claims_unsupported")


# ---- the ADR-0008 examples ----------------------------------------------------------------------------------------
def test_unsupported_claim_is_never_supported_and_planted_contradiction_is_caught() -> None:
    v = verify(["fact", "made_up"], [Finding("fact", R.ENTAILS, "match", "s1")])
    assert v.state is S.PARTIALLY_SUPPORTED and not passes_strict(v) and flagged_claims(v) == ("made_up",)
    v = verify(["fact"], [Finding("fact", R.CONTRADICTS, "match", "s2")])
    assert v.state is S.CONTRADICTED and flagged_claims(v) == ("fact",)


# ---- verify(): grouping and validation ----------------------------------------------------------------------------
def test_verify_groups_findings_by_claim_and_sorts_claims() -> None:
    v = verify(["b", "a"], [Finding("a", R.ENTAILS, "x", "e1"), Finding("b", R.NEUTRAL, "x")])
    assert [c.claim_id for c in v.claims] == ["a", "b"]
    assert [c.state for c in v.claims] == [S.SUPPORTED, S.INSUFFICIENT_EVIDENCE]
    assert (v.state, v.reason) == (S.PARTIALLY_SUPPORTED, "some_claims_unsupported")


@pytest.mark.parametrize("ids,fs", [(["a", "a"], []), (["a", ""], []), (["a"], [finding(R.ENTAILS, claim="b")]),
                                    (["a"], [object()])])
def test_verify_rejects_invalid_input(ids: list[str], fs: list) -> None:
    with pytest.raises(ValueError):
        verify(ids, fs)


def test_no_claims_is_insufficient_evidence_and_does_not_pass_strict() -> None:
    v = verify([], [])
    assert (v.state, v.reason) == (S.INSUFFICIENT_EVIDENCE, "no_checkable_claims") and not passes_strict(v)


# ---- properties ---------------------------------------------------------------------------------------------------
def test_order_of_findings_and_claims_does_not_matter() -> None:
    for seq in all_sequences(RELS, 3):
        fs = [finding(r, i, claim=f"c{i % 2}") for i, r in enumerate(seq)]
        base = verify(["c0", "c1"], fs).to_dict()
        for perm in itertools.permutations(fs):
            assert verify(["c1", "c0"], perm).to_dict() == base


def test_adding_contradiction_or_undecided_never_makes_a_claim_supported() -> None:
    for seq in all_sequences(RELS, 3):
        fs = [finding(r, i) for i, r in enumerate(seq)]
        for extra in (R.CONTRADICTS, R.UNDECIDED):
            after = claim_state("c1", fs + [finding(extra, 9)]).state
            assert after is not S.SUPPORTED, (seq, extra)


def test_adding_neutral_never_changes_the_state() -> None:
    for seq in all_sequences(RELS, 3):
        fs = [finding(r, i) for i, r in enumerate(seq)]
        assert claim_state("c1", fs + [finding(R.NEUTRAL, 9)]).state is claim_state("c1", fs).state


def test_adding_entailment_never_creates_a_contradiction() -> None:
    for seq in all_sequences(RELS, 3):
        fs = [finding(r, i) for i, r in enumerate(seq)]
        if claim_state("c1", fs).state is not S.CONTRADICTED:
            assert claim_state("c1", fs + [finding(R.ENTAILS, 9)]).state is not S.CONTRADICTED


def test_strict_mode_and_flags_are_consistent_for_every_answer() -> None:
    for seq in all_sequences(CLAIM_STATES, 3):
        v = AnswerVerdict(*answer_state(cv := [ClaimVerdict(f"c{i}", st, "x") for i, st in enumerate(seq)]),
                          tuple(cv))
        assert passes_strict(v) == (bool(seq) and not flagged_claims(v))
        assert set(flagged_claims(v)) == {c.claim_id for c in cv if c.state is not S.SUPPORTED}


def test_verdicts_round_trip_through_json() -> None:
    v = verify(["a", "b", "c"], [Finding("a", R.ENTAILS, "x", "e1", "ok"), Finding("b", R.CONTRADICTS, "y", "e2"),
                                 Finding("c", R.UNDECIDED, "z", detail="timeout")])
    d = json.loads(json.dumps(v.to_dict()))
    assert AnswerVerdict.from_dict(d) == v
    f = Finding("a", R.ENTAILS, "x", "e1", "ok")
    assert Finding.from_dict(json.loads(json.dumps(f.to_dict()))) == f


# ---- negative controls: the exhaustive comparison is not vacuous --------------------------------------------------
def _majority_vote(rels: list[Relation]) -> VerificationState:
    """A plausible but wrong rule: more ENTAILS than CONTRADICTS means SUPPORTED."""
    e, c = rels.count(R.ENTAILS), rels.count(R.CONTRADICTS)
    return S.SUPPORTED if e > c else S.CONTRADICTED if c > e else S.INSUFFICIENT_EVIDENCE


def _ignore_undecided(rels: list[Relation]) -> VerificationState:
    return ref_claim([r for r in rels if r is not R.UNDECIDED])


@pytest.mark.parametrize("wrong", [_majority_vote, _ignore_undecided])
def test_negative_control_wrong_claim_rules_disagree_with_the_reference(wrong) -> None:
    assert any(wrong(list(seq)) is not ref_claim(list(seq)) for seq in all_sequences(RELS, 3))


def test_negative_control_wrong_rule_in_the_module_is_caught(monkeypatch: pytest.MonkeyPatch) -> None:
    """Swapping A4 and A5 (uncertainty before partial support) must break the exhaustive answer check."""
    real = vs.answer_state

    def swapped(claims):
        sts = [c.state for c in claims]
        if S.UNCERTAIN in sts and S.CONTRADICTED not in sts:
            return S.UNCERTAIN, "no_claim_supported"
        return real(claims)

    monkeypatch.setattr(vs, "answer_state", swapped)
    bad = [ClaimVerdict("a", S.SUPPORTED, "x"), ClaimVerdict("b", S.UNCERTAIN, "x")]
    assert vs.answer_state(bad)[0] is not ref_answer([S.SUPPORTED, S.UNCERTAIN])
