"""P6-06: deterministic query router (ADR-0008).

Pass/fail criteria, written before the run:

Q1. Classification: a table of synthetic Arabic and English queries gets exactly the expected kinds.
Q2. Composition and fixed order: every non-empty set of five fragment types, joined in every order, and routed
    under 8 configurations, gives the kinds and plan of an independently written reference. The plan does not
    depend on the order of the fragments. Invariants:
    - the plan ends with ``ABSTAIN`` and has no duplicates;
    - every handler in the plan is available;
    - ``current`` is the first handler;
    - ``ASK_CLARIFICATION`` appears only when a flag is set.
Q3. Ambiguity:
    - empty, punctuation-only and function-word-only queries are flagged;
    - an unresolved reference is flagged, unless the caller has context;
    - a demonstrative followed by a noun, and a bare number, are not flagged.
Q4. Contradictions: each pair of opposite directives (Arabic and English, with an attached ``و``) is flagged and
    routed to clarification; one side alone is not flagged.
Q5. Policy:
    - "no tools" removes the tool handlers;
    - a web-search request is recorded only (no handler; OD-11);
    - NETWORK cannot be granted;
    - every skipped handler has a reason in the trace.
Q6. Escalation walks the plan to ``ABSTAIN``, and refuses a wrong handler, an empty reason, or escalating past
    ``ABSTAIN``.
Q7. Determinism and normalisation: harakat, tatweel, case, extra spaces and Arabic-Indic digits do not change the
    route, and repeated calls are identical.
Q8. Stated limits are real: synonyms, number words and attached pronouns are not understood.
Q9. The P6-05 bridge: an ambiguous route makes ``decide`` ask for clarification, and search is never allowed.

Synthetic queries only (invented names); no model, no network, no real data; no claim that the router understands
meaning.
"""

from __future__ import annotations

import itertools
import json

import pytest

from nawa.abstention import Action, decide
from nawa.routing import Flag, Handler, Kind, RouterConfig, abstention_context, language, route
from nawa.verification import FactClaim, check

H, K, F = Handler, Kind, Flag
FULL = RouterConfig(granted_tools={"CALCULATE", "EXECUTE_CODE"}, retrieval_available=True, reasoning_available=True)


# ==== Q1 classification =============================================================================================
TABLE = [
    ("احسب ٣ × ٤", {K.ARITHMETIC}),
    ("كم يساوي 3+4؟", {K.ARITHMETIC}),
    ("what is 12 / 4", {K.ARITHMETIC}),
    ("calculate the sum of 5 and 9", {K.ARITHMETIC}),
    ("اكتب برنامج بايثون يطبع سلمور", {K.CODE}),
    ("def zorwin(x): return x", {K.CODE}),
    ("```print(1)```", {K.CODE}),
    ("لماذا يجري نهر برزان شمالًا؟", {K.REASONING}),
    ("How does the zorwin engine work?", {K.REASONING}),
    ("قارن بين قنطار وتولين", {K.REASONING}),
    ("من بنى برج قنطار؟", {K.FACT}),
    ("How many towers are in Valmor?", {K.FACT}),
    ("متى افتتح جسر كوفار", {K.FACT}),
    ("احسب 2*21 ثم اشرح لماذا", {K.ARITHMETIC, K.REASONING}),
    ("write python code to compute 6*7", {K.ARITHMETIC, K.CODE}),
    ("zorwin kufar", {K.OTHER}),
    ("سلمور المرفاد", {K.OTHER}),
]


@pytest.mark.parametrize("query,kinds", TABLE)
def test_classification_table(query: str, kinds: set) -> None:
    r = route(query, FULL)
    assert set(r.kinds) == kinds and not r.flags, r.to_dict()


# ==== Q2 composition, reference and fixed order =====================================================================
FRAGMENTS = {"arith": "احسب 12 + 30", "code": "اكتب برنامج بايثون", "reason": "اشرح السبب",
             "fact": "متى افتتح برج قنطار", "neutral": "عن مدينة سلمور"}
STRONG = {"arith": K.ARITHMETIC, "code": K.CODE, "reason": K.REASONING}
NEEDS = {K.ARITHMETIC: {"calc", "reason"}, K.CODE: {"code", "reason"}, K.REASONING: {"reason", "retrieve"},
         K.FACT: {"retrieve"}, K.OTHER: {"retrieve"}}
REF_ORDER = ["calc", "code", "retrieve", "reason"]
REF_HANDLER = {"calc": H.CALCULATOR, "code": H.CODE_SANDBOX, "retrieve": H.RETRIEVAL, "reason": H.REASONING}


def reference(parts: tuple[str, ...], cfg: RouterConfig) -> tuple[set, list]:
    kinds = {STRONG[p] for p in parts if p in STRONG} or ({K.FACT} if "fact" in parts else {K.OTHER})
    needed = set().union(*(NEEDS[k] for k in kinds))
    available = {"calc": "CALCULATE" in cfg.granted_tools, "code": "EXECUTE_CODE" in cfg.granted_tools,
                 "retrieve": cfg.retrieval_available, "reason": cfg.reasoning_available}
    return kinds, [REF_HANDLER[n] for n in REF_ORDER if n in needed and available[n]] + [H.ABSTAIN]


CONFIGS = [RouterConfig(granted_tools=t, retrieval_available=ret, reasoning_available=rea)
           for t in (frozenset(), frozenset({"CALCULATE"}), frozenset({"CALCULATE", "EXECUTE_CODE"}))
           for ret in (False, True) for rea in (False, True)][:8] + [FULL]


def test_composition_matches_reference_in_every_order() -> None:
    n = 0
    for k in range(1, 6):
        for parts in itertools.combinations(sorted(FRAGMENTS), k):
            for cfg in CONFIGS:
                want_kinds, want_plan = reference(parts, cfg)
                seen = set()
                for perm in itertools.permutations(parts):
                    r = route(" ثم ".join(FRAGMENTS[p] for p in perm), cfg)
                    assert set(r.kinds) == want_kinds and list(r.plan) == want_plan, (perm, r.to_dict())
                    assert r.plan[-1] is H.ABSTAIN and len(set(r.plan)) == len(r.plan) and r.current is r.plan[0]
                    assert H.ASK_CLARIFICATION not in r.plan and not r.flags
                    seen.add(json.dumps({"kinds": r.to_dict()["kinds"], "plan": r.to_dict()["plan"]}))
                    n += 1
                assert len(seen) == 1
    assert n > 2000


# ==== Q3 ambiguity ==================================================================================================
@pytest.mark.parametrize("query,flag", [
    ("", F.EMPTY), ("   ", F.EMPTY), ("؟؟ !!", F.EMPTY),
    ("ما هو؟", F.NO_CONTENT), ("what is it", F.NO_CONTENT), ("هل هذا", F.NO_CONTENT),
    ("كم طول ذلك؟", F.UNRESOLVED_REFERENCE), ("how tall is it?", F.UNRESOLVED_REFERENCE),
    ("متى بنيت تلك؟", F.UNRESOLVED_REFERENCE), ("who built them", F.UNRESOLVED_REFERENCE),
])
def test_ambiguous_queries_ask_for_clarification(query: str, flag: Flag) -> None:
    r = route(query, FULL)
    assert r.flags == (flag,) and r.plan == (H.ASK_CLARIFICATION, H.ABSTAIN) and r.ambiguous
    assert any(s.rule in {"A1", "A2", "A3"} for s in r.trace)


def test_not_ambiguous_cases() -> None:
    assert not route("ما هذا المرفاد؟", FULL).flags                      # demonstrative + noun
    assert not route("42", FULL).flags                                   # a bare number has content
    assert not route("كم طول ذلك؟", RouterConfig(has_context=True)).flags  # context resolves the pronoun
    assert not route("how tall is it?", RouterConfig(has_context=True)).flags


# ==== Q4 contradictions =============================================================================================
@pytest.mark.parametrize("query,topic", [
    ("احسب 3+4 باستخدام الحاسبة بدون ادوات استخدم الحاسبة", "tools"),
    ("calculate 3+4, use a calculator, without tools", "tools"),
    ("أجب باختصار وبالتفصيل عن سلمور", "length"),
    ("describe valmor briefly and in detail", "length"),
    ("تحدث عن قنطار مع المصادر بدون مصادر", "sources"),
    ("tell me about kufar, cite, no sources", "sources"),
    ("أجب بالعربية وبالإنجليزية عن تولين", "language"),
    ("answer in arabic and in english about teliva", "language"),
])
def test_conflicting_directives_are_flagged(query: str, topic: str) -> None:
    r = route(query, FULL)
    assert F.CONFLICTING_DIRECTIVES in r.flags and r.plan == (H.ASK_CLARIFICATION, H.ABSTAIN)
    assert {f"{topic}:+", f"{topic}:-"} <= set(r.directives)
    assert any(s.rule == "A4" and topic in s.detail for s in r.trace)


def test_one_directive_alone_is_not_a_conflict() -> None:
    for q in ("أجب باختصار عن سلمور", "describe valmor in detail", "تحدث عن قنطار مع المصادر", "answer in english"):
        r = route(q, FULL)
        assert not r.flags and len(r.directives) == 1


# ==== Q5 policy =====================================================================================================
def test_no_tools_directive_web_search_and_network() -> None:
    r = route("احسب 5+5 بدون أدوات", FULL)
    assert r.plan == (H.REASONING, H.ABSTAIN)
    assert any(s.rule == "P1" and "no tools" in s.detail for s in r.trace)
    w = route("ابحث في الإنترنت عن برج قنطار", FULL)
    assert "web_search:requested" in w.directives and any(s.rule == "W1" and "OD-11" in s.detail for s in w.trace)
    assert set(w.plan) <= set(Handler) and w.plan == (H.RETRIEVAL, H.ABSTAIN)
    for bad in ({"NETWORK"}, {"SEARCH"}):
        with pytest.raises(ValueError, match="OD-11"):
            RouterConfig(granted_tools=bad)
    with pytest.raises(ValueError):
        RouterConfig(retrieval_available=1)            # type: ignore[arg-type]
    with pytest.raises(ValueError):
        route(None)                                    # type: ignore[arg-type]


def test_default_config_skips_everything_with_reasons() -> None:
    r = route("احسب 2+2 ثم اشرح لماذا")
    assert r.plan == (H.ABSTAIN,)
    skipped = [s.detail for s in r.trace if s.rule == "P1"]
    assert skipped == ["skip CALCULATOR: tool CALCULATE not granted", "skip RETRIEVAL: no retrieval index",
                       "skip REASONING: reasoning (P6-03) not available"]


# ==== Q6 escalation =================================================================================================
def test_escalation_walks_to_abstain() -> None:
    r = route("احسب 2*21 ثم اشرح لماذا", FULL)
    assert r.plan == (H.CALCULATOR, H.RETRIEVAL, H.REASONING, H.ABSTAIN)
    with pytest.raises(ValueError):
        r.escalate(H.RETRIEVAL, "x")
    with pytest.raises(ValueError):
        r.escalate(H.CALCULATOR, " ")
    steps = []
    while r.current is not H.ABSTAIN:
        steps.append(r.current)
        r = r.escalate(r.current, f"{r.current.value} failed")
    assert steps == [H.CALCULATOR, H.RETRIEVAL, H.REASONING] and r.plan == (H.ABSTAIN,)
    assert [s.detail.split(":")[0] for s in r.trace if s.rule == "E1"] == [
        "CALCULATOR -> RETRIEVAL", "RETRIEVAL -> REASONING", "REASONING -> ABSTAIN"]
    with pytest.raises(ValueError, match="final"):
        r.escalate(H.ABSTAIN, "no")


# ==== Q7 determinism and normalisation ==============================================================================
def test_surface_variation_does_not_change_the_route() -> None:
    pairs = [("احسب ١٢ + ٣٠ ثم اشرح لماذا", "احسـب   12+30 ثُمَّ اشْرَحْ لِماذا"),
             ("HOW DOES THE ZORWIN WORK", "how   does the zorwin work"),
             ("أين يقع جسر كوفار؟", "اين يقع جسر كوفار")]
    for a, b in pairs:
        ra, rb = route(a, FULL).to_dict(), route(b, FULL).to_dict()
        ra.pop("trace"), rb.pop("trace")
        assert ra == rb
    q = "احسب 2*21 ثم اشرح لماذا بدون أدوات"
    assert len({json.dumps(route(q, FULL).to_dict(), ensure_ascii=False) for _ in range(20)}) == 1


def test_language() -> None:
    assert [language(x) for x in ("سلمور", "valmor", "سلمور valmor", "123 ؟")] == ["ar", "en", "mixed", "unknown"]


# ==== Q8 stated limits ==============================================================================================
def test_the_router_does_not_understand_meaning() -> None:
    assert route("أوجد ناتج ضرب خمسة في ستة", FULL).kinds == (K.OTHER,)   # number words, a synonym of احسب
    assert route("figure out six times seven", FULL).kinds == (K.OTHER,)
    assert not route("كم طوله؟", FULL).flags                            # attached pronoun is not seen


# ==== Q9 bridge to P6-05 ============================================================================================
def test_abstention_context_follows_the_route() -> None:
    amb = route("كم طول ذلك؟", FULL)
    rep = check([FactClaim("f", "tower", "height", "300", "m")], [])
    assert decide(rep, abstention_context(amb)).action is Action.ASK_CLARIFICATION
    calc = abstention_context(route("احسب 6*7", FULL), tool_calls_left=1)
    assert calc.granted_tools == frozenset({"CALCULATE"}) and calc.search_allowed is False and not calc.ambiguous
    web = abstention_context(route("ابحث في الإنترنت عن قنطار", FULL))
    assert web.search_allowed is False and web.searches_left == 0
