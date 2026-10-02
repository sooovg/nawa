"""P6-05: abstention decision function and risk–coverage (ADR-0008).

Pass/fail criteria, written before the run:

A1. ``decide`` returns exactly one of the five actions, and equals an independently written reference on every
    combination: claim states up to 3 claims, an unchecked claim (tool-checkable or not), self-conflict, both modes,
    ambiguity, search permission and budget, tool grants and budget.
A2. Invariants:
    - never an answer with a CONTRADICTED claim or a self-contradiction;
    - strict mode answers only SUPPORTED;
    - lenient mode discloses every claim that is not SUPPORTED;
    - SEARCH only when the caller allows it (default: never; P6-02a BLOCKED, OD-11);
    - abstention text is recognised by the evaluation's own ``is_abstention``.
A3. ``curve``, ``aurc`` and ``max_coverage_at_risk`` equal a brute-force O(n²) computation, ties included, and one
    hand-computed example.
A4. Negative controls with stub policies:
    - an oracle ordering has the smallest AURC and a reversed ordering the largest;
    - always-abstain has coverage 0;
    - always-answer has coverage 1 and risk equal to the error rate.
A5. No numeric threshold in the decision code.

Synthetic inputs only; no model, no network, no real data; no claim that NAWA abstains better.
"""

from __future__ import annotations

import ast
import itertools
import random
from fractions import Fraction
from pathlib import Path

import pytest

from nawa.abstention import (Action, Context, Mode, abstention_text, aurc, claim_kinds, curve, decide,
                             decision_point, max_coverage_at_risk, oracle_aurc)
from nawa.evaluation.normalize import is_abstention
from nawa.verification import (ArithmeticClaim, CalculatorChecker, CodeClaim, Evidence, FactClaim, FactRecord,
                               QuoteChecker, RecordChecker, TextClaim, check)
from nawa.verification.consistency import Conflict
from nawa.verification.states import AnswerVerdict, ClaimVerdict, VerificationState, answer_state
from nawa.verification.verifier import Report

ROOT = Path(__file__).resolve().parents[1]
S = VerificationState
A = Action
CLAIM_STATES = (S.SUPPORTED, S.UNCERTAIN, S.CONTRADICTED, S.INSUFFICIENT_EVIDENCE)


def make_report(states: tuple, unchecked: tuple = (), self_conflict: bool = False) -> Report:
    claims = tuple(ClaimVerdict(f"c{i}", st, "x", (f"e{i}",) if st is S.SUPPORTED else ())
                   for i, st in enumerate(states))
    state, reason = answer_state(claims)
    conflicts = (Conflict("s", "a", None, (("n:1", ("c0",)), ("n:2", ("c1",)))),) if self_conflict else ()
    return Report(AnswerVerdict(state, reason, claims), (), (), conflicts, (), tuple(unchecked))


def reference(states, unchecked_kind, self_conflict, ctx: Context):
    """Written separately from ``decide``, as a list of guarded outcomes, to cross-check it."""
    flagged = {f"c{i}" for i, s in enumerate(states) if s is not S.SUPPORTED} | ({"c0", "c1"} if self_conflict else set())
    answer_state_ = answer_state(make_report(states).verdict.claims)[0]
    tool_ok = unchecked_kind is not None and {ArithmeticClaim: "CALCULATE", CodeClaim: "EXECUTE_CODE"}.get(
        unchecked_kind) in ctx.granted_tools and ctx.tool_calls_left > 0
    outcomes = [
        (ctx.ambiguous, A.ASK_CLARIFICATION),
        (self_conflict, A.ABSTAIN),
        (answer_state_ is S.CONTRADICTED, A.ABSTAIN),
        (tool_ok, A.RUN_TOOL),
        (answer_state_ is S.SUPPORTED and not self_conflict, A.ANSWER_WITH_CITATIONS),
        (ctx.mode is Mode.LENIENT and answer_state_ is S.PARTIALLY_SUPPORTED, A.ANSWER_WITH_CITATIONS),
        (ctx.search_allowed and ctx.searches_left > 0, A.SEARCH),
        (True, A.ABSTAIN),
    ]
    return next(a for cond, a in outcomes if cond), flagged


def all_cases():
    for k in range(0, 4):
        for states in itertools.product(CLAIM_STATES, repeat=k):
            for unchecked_kind in (None, ArithmeticClaim, CodeClaim, TextClaim):
                for self_conflict in ((False, True) if k >= 2 else (False,)):
                    for mode, amb, sa, sl, tools, tl in itertools.product(
                            Mode, (False, True), (False, True), (0, 1),
                            (frozenset(), frozenset({"CALCULATE"}), frozenset({"CALCULATE", "EXECUTE_CODE"})),
                            (0, 1)):
                        yield states, unchecked_kind, self_conflict, Context(
                            mode=mode, ambiguous=amb, search_allowed=sa, searches_left=sl, granted_tools=tools,
                            tool_calls_left=tl, claim_kinds={"u": unchecked_kind} if unchecked_kind else {})


def test_decide_matches_reference_and_invariants_on_every_combination() -> None:
    n = 0
    seen = set()
    for states, kind, sc, ctx in all_cases():
        st = states + ((S.INSUFFICIENT_EVIDENCE,) if kind else ())      # an unchecked claim is C1 in the verdict
        rep = make_report(st, ("u",) if kind else (), sc)
        if kind:   # rename the unchecked claim's verdict id to "u"
            cl = rep.verdict.claims[:-1] + (ClaimVerdict("u", S.INSUFFICIENT_EVIDENCE, "no_evidence"),)
            rep = Report(AnswerVerdict(*answer_state(cl), cl), (), (), rep.claim_conflicts, (), ("u",))
        d = decide(rep, ctx)
        want, _ = reference(st, kind, sc, ctx)
        assert d.action is want, (states, kind, sc, ctx, d)
        assert d.action in set(A)
        seen.add(d.action)
        states_ = {c.state for c in rep.verdict.claims}
        if d.action is A.ANSWER_WITH_CITATIONS:
            assert S.CONTRADICTED not in states_ and not rep.claim_conflicts
            if ctx.mode is Mode.STRICT:
                assert rep.verdict.state is S.SUPPORTED and d.disclosed == ()
            not_sup = {c.claim_id for c in rep.verdict.claims if c.state is not S.SUPPORTED}
            assert not_sup <= set(d.disclosed)
            assert {c for c, _ in d.citations} == {c.claim_id for c in rep.verdict.claims if c.state is S.SUPPORTED}
            assert all(ev for _, ev in d.citations)
        if d.action is A.SEARCH:
            assert ctx.search_allowed and ctx.searches_left > 0
        if d.action is A.RUN_TOOL:
            assert ctx.tool_calls_left > 0 and d.targets == ("u",)
        n += 1
    assert seen == set(A) and n > 10_000


def test_default_context_is_conservative_and_never_searches() -> None:
    for states in itertools.product(CLAIM_STATES, repeat=2):
        d = decide(make_report(states))
        assert d.action in (A.ANSWER_WITH_CITATIONS, A.ABSTAIN)
        assert (d.action is A.ANSWER_WITH_CITATIONS) == (states == (S.SUPPORTED, S.SUPPORTED))


def test_a_search_budget_alone_never_permits_search() -> None:
    """Found by a surviving mutation: permission must be explicit; a budget without it is not enough."""
    assert Context().search_allowed is False
    for states in itertools.product(CLAIM_STATES, repeat=2):
        assert decide(make_report(states), Context(searches_left=5)).action is not A.SEARCH


def test_search_and_network_are_not_grantable_here() -> None:
    with pytest.raises(ValueError, match="OD-11"):
        Context(granted_tools={"NETWORK"})
    with pytest.raises(ValueError):
        Context(searches_left=-1)
    with pytest.raises(ValueError):
        Context(ambiguous=1)            # type: ignore[arg-type]
    with pytest.raises(ValueError):
        decide("not a report")          # type: ignore[arg-type]


@pytest.mark.parametrize("lang", ["ar", "en"])
def test_abstention_text_is_recognised_by_the_evaluation(lang: str) -> None:
    assert is_abstention(abstention_text(lang))
    with pytest.raises(ValueError):
        abstention_text("fr")


def test_every_decision_shows_uncalibrated_uncertainty_and_performs_nothing() -> None:
    for states in itertools.product(CLAIM_STATES, repeat=2):
        for ctx in (Context(), Context(search_allowed=True, searches_left=1)):
            d = decide(make_report(states), ctx).to_dict()
            assert d["calibrated"] is False and d["performed"] is False
            assert d["uncertainty"]["calibrated"] is False and d["uncertainty"]["n_claims"] == 2
            assert sum(d["uncertainty"]["counts"].values()) == 2
    d = decide(make_report((S.SUPPORTED, S.UNCERTAIN)), Context(search_allowed=True, searches_left=1))
    assert d.action is A.SEARCH and d.to_dict()["uncertainty"]["supported_fraction"] == "1/2"
    from nawa.abstention.decision import Decision
    with pytest.raises(ValueError):
        Decision(A.SEARCH, "D7", "x", performed=True)
    with pytest.raises(ValueError):
        Decision(A.ABSTAIN, "D8", "x", uncertainty={"calibrated": True})


def test_search_decision_is_recorded_only() -> None:
    src = (ROOT / "src/nawa/abstention").glob("*.py")
    text = "\n".join(p.read_text(encoding="utf-8") for p in src)
    for banned in ("nawa.tools.registry", "run_code", "import socket", "urllib", "requests", "httpx"):
        assert banned not in text, banned


def test_decision_code_has_no_numeric_threshold() -> None:
    tree = ast.parse((ROOT / "src/nawa/abstention/decision.py").read_text(encoding="utf-8"))
    nums = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and type(n.value) in (int, float)}
    assert nums <= {0}, nums


# ==== end to end with P6-04 (synthetic twins: with and without evidence) =============================================
EV = [Evidence("e1", "The tower is 300 m tall.", (FactRecord("tower", "height", "300", "m"),))]


def test_twin_items_answer_with_evidence_and_abstain_without() -> None:
    claims = [FactClaim("f", "tower", "height", "300", "m"), TextClaim("t", "The tower is 300 m tall", ("e1",))]
    with_ev = decide(check(claims, EV))
    assert with_ev.action is A.ANSWER_WITH_CITATIONS and dict(with_ev.citations) == {"f": ("e1",), "t": ("e1",)}
    without = decide(check(claims, []))
    assert without.action is A.ABSTAIN and without.reason == "insufficient_evidence"
    allowed = decide(check(claims, []), Context(search_allowed=True, searches_left=1))
    assert allowed.action is A.SEARCH and set(allowed.targets) == {"f", "t"}


def test_contradicted_and_partial_answers() -> None:
    wrong = [FactClaim("f", "tower", "height", "250", "m")]
    assert decide(check(wrong, EV)).reason == "contradicted_by_evidence"
    partial = [FactClaim("f", "tower", "height", "300", "m"), TextClaim("t", "it opened in 1990", ("e1",))]
    rep = check(partial, EV)
    assert decide(rep).action is A.ABSTAIN
    lenient = decide(rep, Context(mode=Mode.LENIENT))
    assert lenient.action is A.ANSWER_WITH_CITATIONS and lenient.disclosed == ("t",)


def test_tool_path_then_answer() -> None:
    claims = [ArithmeticClaim("a", "6 * 7", "42"), FactClaim("f", "tower", "height", "300", "m")]
    kinds = claim_kinds(claims)
    first = check(claims, EV, checkers=[RecordChecker(), QuoteChecker()])        # no calculator yet
    d = decide(first, Context(granted_tools={"CALCULATE"}, tool_calls_left=1, claim_kinds=kinds))
    assert d.action is A.RUN_TOOL and d.targets == ("a",)
    assert decide(first, Context(claim_kinds=kinds)).action is A.ABSTAIN      # not granted: no tool call
    second = check(claims, EV, checkers=[RecordChecker(), QuoteChecker(), CalculatorChecker()])
    assert decide(second, Context(granted_tools={"CALCULATE"}, tool_calls_left=1, claim_kinds=kinds)).action \
        is A.ANSWER_WITH_CITATIONS


def test_ambiguity_comes_first_and_decisions_serialise() -> None:
    d = decide(check([FactClaim("f", "tower", "height", "300", "m")], EV), Context(ambiguous=True))
    assert d.action is A.ASK_CLARIFICATION and d.to_dict()["action"] == "ASK_CLARIFICATION"


# ==== risk–coverage =================================================================================================
def brute(items):
    """O(n²): one point per distinct threshold, plus the empty point."""
    n = len(items)
    pts = [(Fraction(0), None)]
    for t in sorted({s for s, _ in items}, reverse=True):
        acc = [c for s, c in items if s >= t]
        pts.append((Fraction(len(acc), n), Fraction(sum(not c for c in acc), len(acc))))
    return pts


def brute_aurc(items):
    pts = brute(items)
    return None if len(pts) == 1 else sum((r * (c - pc) for (pc, _), (c, r) in zip(pts, pts[1:])), Fraction(0))


def rand_items(rng, n, kind):
    def score():
        if kind == "int":
            return rng.randint(0, 5)              # many ties
        if kind == "fraction":
            return Fraction(rng.randint(0, 20), rng.randint(1, 4))
        return rng.choice([0.1, 0.25, 0.5, 0.75, 0.9]) if rng.random() < 0.5 else rng.random()
    return [(score(), rng.random() < 0.6) for _ in range(n)]


def test_curve_and_aurc_match_brute_force() -> None:
    rng = random.Random(0)
    for trial in range(600):
        items = rand_items(rng, rng.randint(0, 25), ("int", "fraction", "float")[trial % 3])
        got = [(p.coverage, p.risk) for p in curve(items)]
        assert got == brute(items), items
        assert aurc(items) == brute_aurc(items)
        for mr in (Fraction(0), Fraction(1, 4), Fraction(1, 2), 1):
            best = max_coverage_at_risk(items, mr)
            ok = [(c, r) for c, r in brute(items) if r is not None and r <= mr]
            assert best.coverage == (max(c for c, _ in ok) if ok else 0)


def test_hand_computed_example() -> None:
    items = [(0.9, True), (0.8, False), (0.7, True), (0.7, False)]
    assert [(p.coverage, p.risk) for p in curve(items)] == [(0, None), (Fraction(1, 4), 0), (Fraction(1, 2),
                                                             Fraction(1, 2)), (1, Fraction(1, 2))]
    assert aurc(items) == Fraction(3, 8) and oracle_aurc(items) == Fraction(5, 24)
    assert curve(items)[1].risk_interval()[0] == 0.0


def test_negative_controls_oracle_random_reversed_and_trivial_policies() -> None:
    rng = random.Random(1)
    for _ in range(200):
        correct = [rng.random() < 0.6 for _ in range(rng.randint(1, 30))]
        n = len(correct)
        # distinct scores: the oracle puts every correct item first, the reversed ordering every wrong item first;
        # each prefix then has the fewest / the most errors, so these bound the AURC of any ordering
        oracle = [(n - k if c else -k, c) for k, c in enumerate(correct)]
        reverse = [(-k if c else n - k, c) for k, c in enumerate(correct)]
        rand = [(rng.random(), c) for c in correct]
        assert aurc(oracle) == oracle_aurc(rand) <= aurc(rand) <= aurc(reverse)
        if 0 < sum(correct) < n:
            assert aurc(oracle) < aurc(reverse)
        never = decision_point([(False, c) for c in correct])
        always = decision_point([(True, c) for c in correct])
        assert never.coverage == 0 and never.risk is None
        assert always.coverage == 1 and always.risk == Fraction(sum(not c for c in correct), len(correct))
        exact = decision_point([(c, c) for c in correct])
        assert exact.risk in (None, 0)


def test_risk_coverage_input_validation() -> None:
    assert curve([]) == [curve([])[0]] and aurc([]) is None and oracle_aurc([]) is None
    for bad in ([(float("nan"), True)], [("0.5", True)], [(0.5, 1)], [(True, True)]):
        with pytest.raises(ValueError):
            curve(bad)
    for mr in (0.1, -1, 2, True):
        with pytest.raises(ValueError):
            max_coverage_at_risk([(1, True)], mr)
    with pytest.raises(ValueError):
        decision_point([(1, True)])
