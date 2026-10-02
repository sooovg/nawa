"""P6-03: planner, decomposer, state, budget, generator interface and self-consistency (ADR-0008, code-only).

Success criteria, registered before the first run (pass/fail; no quality claim, ADR-0008 D4):

R1  Budget. Limits and costs are non-negative ints only (no float, no bool). Exhaustively for every limit 0..3 on every
    resource and every charge sequence: a charge is accepted iff it fits, a refused charge changes nothing (also when
    one charge touches several resources), and spend never exceeds a limit.
R2  State. Every record is hash-chained; JSON round-trip is byte-identical; editing any field, removing, inserting or
    reordering a record, or forging ``head``/``closed`` is detected; the same calls give the same bytes; a step that does
    not fit the budget produces one recorded ``stop`` with ``budget_exhausted:<RESOURCE>`` and nothing is recorded
    after it; floats in payloads are refused.
R3  Decomposer. On synthetic questions built from fragments with invented names (every combination of fragment kinds
    and separators, seed 0), the sub-questions equal the construction: same order, kinds, planted expressions and
    dependencies (``ثم``/``then`` only); the expression found evaluates with the P6-02 calculator to the planted value;
    Arabic-Indic digits give the same result as ASCII; decimals are never split; code blocks are never split; ``و`` is
    never a split point (stated limit).
R4  Planner. Equal to an independently written reference on every combination of sub-question lists (up to 3,
    with dependencies), grants (all subsets), budgets (a grid) and n_candidates 1..3. Invariants: every sub-question is
    scheduled or dropped with a reason; nothing scheduled depends on something dropped; every scheduled sub-question
    has exactly one VERIFY; DECIDE is last and depends on every VERIFY; TOOL steps only with their grant and only for
    tools that exist in the P6-02 registry with that permission; total cost within the budget; NETWORK cannot be
    granted; the plan hash is deterministic and changes when the plan changes.
R5  Generator interface. Exactly ``n`` candidates are charged and recorded; a failing or malformed generator is recorded
    as an ``error`` step, never hidden; a non-stub generator is refused (P6-03a); budget exhaustion is recorded before
    the generator runs; seeds give deterministic output.
R6  Self-consistency. Groups by the evaluation's ``normalize`` and ``is_abstention`` (reused); exact shares; a tie has
    no plurality; the result is never calibrated and never verification; brute-force check on random votes.
R7  Negative control (agreement is not truth): a WrongStub that agrees with itself on every candidate still yields
    CONTRADICTED from the P6-04 verifier and ABSTAIN from the P6-05 decision.
R8  Scope. The package imports no external model library and no network library (enforced by
    tests/test_original_system_policy.py), and no numeric threshold appears in consistency or planner code.
"""

from __future__ import annotations

import itertools
import json
import random
import re
from fractions import Fraction
from pathlib import Path

import pytest

from nawa.abstention.decision import Action as Decide
from nawa.abstention.decision import decide
from nawa.evaluation.normalize import is_abstention
from nawa.reasoning import (Action, Budget, BudgetExhausted, Candidate, FailingStub, Kind, OracleStub, Resource,
                            ScriptedStub, Spend, State, StateClosed, SubTask, WrongStub, agreement, decompose,
                            generate_candidates, plan, plan_subtasks)
from nawa.reasoning.consistency import ABSTAIN_KEY
from nawa.reasoning.decomposer import find_expression
from nawa.tools.calculator import calculate
from nawa.tools.registry import Permission, default_registry
from nawa.verification.claims import ArithmeticClaim
from nawa.verification.states import VerificationState
from nawa.verification.verifier import check

ROOT = Path(__file__).resolve().parents[1]
RES = list(Resource)


# ---------------------------------------------------------------- R1 budget
def test_r1_budget_rejects_bad_numbers():
    for bad in (-1, 1.0, True, None, "3"):
        with pytest.raises(ValueError):
            Budget(max_steps=bad)
        with pytest.raises(ValueError):
            Budget().charge(Spend(), {Resource.STEPS: bad})
    with pytest.raises(ValueError):
        Budget().charge(Spend(), {"STEPS": 1})
    with pytest.raises(ValueError):
        Budget.from_dict({"STEPS": 1})
    assert Budget.from_dict(Budget(1, 2, 3, 4).to_dict()) == Budget(1, 2, 3, 4)


def test_r1_budget_exhaustive_all_or_nothing():
    charges = [{Resource.STEPS: 1}, {Resource.TOOL_CALLS: 1, Resource.STEPS: 1}, {Resource.CANDIDATES: 2},
               {Resource.SUBTASKS: 1, Resource.CANDIDATES: 1}, {}]
    checked = 0
    for limits in itertools.product(range(4), repeat=4):
        b = Budget(*limits)
        for seq in itertools.product(range(len(charges)), repeat=3):
            spend = Spend()
            for i in seq:
                c = charges[i]
                fits = all(spend.get(r) + c.get(r, 0) <= b.limit(r) for r in RES)
                assert b.allows(spend, c) == fits
                if fits:
                    spend = b.charge(spend, c)
                else:
                    before = spend
                    with pytest.raises(BudgetExhausted) as e:
                        b.charge(spend, c)
                    assert spend == before
                    first = next(r for r in RES if spend.get(r) + c.get(r, 0) > b.limit(r))
                    assert e.value.resource is first and e.value.reason == f"budget_exhausted:{first.value}"
                assert all(spend.get(r) <= b.limit(r) for r in RES)
                checked += 1
    assert checked == 4 ** 4 * 5 ** 3 * 3


# ---------------------------------------------------------------- R2 state
def _run(budget=Budget(), n=3) -> State:
    s = State(budget, "r")
    s.record("plan", payload={"q": "س"})
    for i in range(n):
        s.record("tool", ref=f"s{i}", payload={"x": i, "v": "1/3"}, cost={Resource.TOOL_CALLS: 1})
    return s


def test_r2_chain_roundtrip_and_determinism():
    a, b = _run(), _run()
    assert a.to_json() == b.to_json() and a.verify() == []
    c = State.from_json(a.to_json())
    assert c.to_json() == a.to_json() and c.spend == a.spend
    assert [r.prev_hash for r in a.records[1:]] == [r.hash for r in a.records[:-1]]
    assert a.spend.to_dict() == {"STEPS": 4, "TOOL_CALLS": 3, "CANDIDATES": 0, "SUBTASKS": 0}


def _tampered(text: str):
    d = json.loads(text)
    out = []
    for i in range(len(d["records"])):
        for f in ("seq", "kind", "ref", "outcome", "reason", "payload", "cost", "spend_after", "prev_hash", "hash"):
            e = json.loads(text)
            v = e["records"][i][f]
            e["records"][i][f] = (v + 1) if isinstance(v, int) else ({"x": 1} if isinstance(v, dict) else
                                                                      ("ok" if v == "tool" else "tool"))
            out.append((f"edit {i}.{f}", e))
    for i in range(len(d["records"])):
        e = json.loads(text)
        del e["records"][i]
        out.append((f"remove {i}", e))
    e = json.loads(text)
    e["records"][1], e["records"][2] = e["records"][2], e["records"][1]
    out.append(("swap", e))
    e = json.loads(text)
    e["records"].insert(1, dict(e["records"][1]))
    out.append(("insert", e))
    e = json.loads(text)
    e["head"] = "f" * 64
    out.append(("head", e))
    e = json.loads(text)
    e["closed"] = True
    out.append(("closed", e))
    return out


def test_r2_tamper_detected():
    text = _run().to_json()
    cases = _tampered(text)
    assert len(cases) > 40
    for name, e in cases:
        with pytest.raises(ValueError):
            State.from_json(json.dumps(e))
        assert name  # every case raised


def test_r2_budget_stop_is_recorded_and_final():
    s = _run(Budget(max_steps=10, max_tool_calls=2), n=2)
    r = s.record("tool", ref="s9", cost={Resource.TOOL_CALLS: 1})
    assert r.kind == "stop" and r.reason == "budget_exhausted:TOOL_CALLS" and r.outcome == "refused"
    assert r.payload["refused_ref"] == "s9" and s.closed and s.verify() == []
    with pytest.raises(StateClosed):
        s.record("note")
    with pytest.raises(StateClosed):
        s.stop("again")
    assert State.from_json(s.to_json()).closed
    # STEPS exhaustion: the stop record is free and still recorded
    t = State(Budget(max_steps=1))
    t.record("plan")
    assert t.record("note").reason == "budget_exhausted:STEPS" and t.spend.steps == 1 and t.verify() == []


def test_r2_payload_rules():
    s = State(Budget())
    for bad in (0.5, {"a": 1.0}, [1, {2: 3}], object(), {1, 2}):
        with pytest.raises(ValueError):
            s.record("note", payload=bad)
    with pytest.raises(ValueError):
        s.record("stop")
    with pytest.raises(ValueError):
        s.record("bogus")
    assert s.records == []


# ---------------------------------------------------------------- R3 decomposer
NAMES = ["زارِنا", "كولموت", "Vexor", "تالينو"]
EXPRS = [("3 + 4", "7"), ("12 × 3", "36"), ("(2 + 3) * 4", "20"), ("7.5 - 2.5", "5"), ("2 ^ 5", "32"),
         ("10 ÷ 4", "5/2")]
TO_AR = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")


def _fragment(kind: str, i: int, rng: random.Random) -> tuple[str, dict]:
    name = NAMES[i % len(NAMES)]
    if kind == "arith":
        e, v = EXPRS[rng.randrange(len(EXPRS))]
        return f"كم يساوي {e}", {"kind": Kind.ARITHMETIC, "value": v}
    if kind == "text":
        return f"ما عاصمة {name}", {"kind": Kind.TEXT}
    return f"what is the colour of {name}", {"kind": Kind.TEXT}


def test_r3_decomposer_matches_construction():
    rng = random.Random(0)
    seps = ["؟ ", "? ", "\n", "؛ ", ". "]
    seqs = [" ثم ", " then ", " وبعد ذلك "]
    n = 0
    for kinds in itertools.product(["arith", "text", "en"], repeat=3):
        for sep, sq in itertools.product(seps, seqs):
            for chain in range(3):       # 0: all independent; 1: f2 then f3; 2: f1 then f2 then f3
                frags = [_fragment(k, i, rng) for i, k in enumerate(kinds)]
                if chain == 0:
                    q = sep.join(f for f, _ in frags) + "؟"
                    deps = [(), (), ()]
                elif chain == 1:
                    q = frags[0][0] + sep + frags[1][0] + sq + frags[2][0]
                    deps = [(), (), ("t2",)]
                else:
                    q = sq.join(f for f, _ in frags)
                    deps = [(), ("t1",), ("t2",)]
                got = decompose(q)
                assert [t.task_id for t in got] == ["t1", "t2", "t3"], q
                for t, (text, exp), d in zip(got, frags, deps):
                    assert t.text == text and t.kind is exp["kind"] and t.depends_on == d, (q, t)
                    if t.kind is Kind.ARITHMETIC:
                        assert calculate(t.expression).value == Fraction(exp["value"])
                ar = decompose(q.translate(TO_AR))
                assert [(t.kind, t.depends_on, t.expression) for t in ar] == \
                       [(t.kind, t.depends_on, t.expression) for t in got]
                n += 1
    assert n == 27 * 15 * 3


def test_r3_decomposer_edge_cases():
    assert decompose("") == [] and decompose(" ؟؟ . \n !") == []
    one = decompose("كم يساوي 3.5 * 2. والمسافة ٤٫٥ كم")
    assert [t.text for t in one] == ["كم يساوي 3.5 * 2", "والمسافة ٤٫٥ كم"]   # decimals kept, و not split
    assert one[0].expression == "3.5 * 2"
    code = decompose("شغّل هذا؟\n```python\nx = 1; print(x)? \n```\nثم اشرح")
    assert [t.kind for t in code] == [Kind.TEXT, Kind.CODE, Kind.TEXT]
    assert code[1].code == "x = 1; print(x)? \n"                              # nothing inside the fence is split
    assert decompose("ما لون زارِنا وكم عمر كولموت")[0].text == "ما لون زارِنا وكم عمر كولموت"
    assert find_expression("رقم 42 فقط") is None and find_expression("سنة 2020-2021") == "2020-2021"
    with pytest.raises(ValueError):
        decompose("x" * 4001)
    with pytest.raises(ValueError):
        SubTask("t1", "x", Kind.ARITHMETIC)
    with pytest.raises(ValueError):
        SubTask("a", "x", Kind.TEXT)


# ---------------------------------------------------------------- R4 planner
def _reference_plan(subs, grants, budget, n):
    """Independent reference: per sub-question action lists, then greedy all-or-nothing budgeting."""
    tools = {Kind.ARITHMETIC: ("calculator", "CALCULATE"), Kind.CODE: ("python", "EXECUTE_CODE")}
    left = budget.to_dict()
    if left["STEPS"] < 2:
        return [], [(t.task_id, "budget:STEPS") for t in subs], False
    left["STEPS"] -= 2
    out, dropped, gone = [], [], set()
    for t in subs:
        dd = [d for d in t.depends_on if d in gone]
        if dd:
            dropped.append((t.task_id, f"depends_on_dropped:{dd[0]}"))
            gone.add(t.task_id)
            continue
        tl = tools.get(t.kind)
        if tl and tl[1] in grants:
            acts = [("TOOL", tl[0], ""), ("VERIFY", None, "")]
            need = {"STEPS": 2, "TOOL_CALLS": 1, "CANDIDATES": 0, "SUBTASKS": 1}
        else:
            acts = [("GENERATE", None, "tool_not_granted" if tl else "")] + \
                   ([("CONSISTENCY", None, "")] if n > 1 else []) + [("VERIFY", None, "")]
            need = {"STEPS": len(acts), "TOOL_CALLS": 0, "CANDIDATES": n, "SUBTASKS": 1}
        short = [k for k in ("STEPS", "TOOL_CALLS", "CANDIDATES", "SUBTASKS") if need[k] > left[k]]
        if short:
            dropped.append((t.task_id, f"budget:{short[0]}"))
            gone.add(t.task_id)
            continue
        for k in left:
            left[k] -= need[k]
        out += [(t.task_id, a, tool, note) for a, tool, note in acts]
    return out + [(None, "DECIDE", None, "")], dropped, True


def _sub_lists():
    kinds = [Kind.ARITHMETIC, Kind.CODE, Kind.TEXT]
    for k in range(4):
        for ks in itertools.product(kinds, repeat=k):
            for dep_mask in itertools.product([False, True], repeat=max(k - 1, 0)):
                subs = []
                for i, kd in enumerate(ks):
                    deps = (f"t{i}",) if i and dep_mask[i - 1] else ()
                    subs.append(SubTask(f"t{i + 1}", f"q{i}", kd, deps,
                                        expression="1 + 1" if kd is Kind.ARITHMETIC else None,
                                        code="print(2)" if kd is Kind.CODE else None))
                yield subs


def test_r4_planner_equals_reference_and_invariants():
    reg = default_registry()
    grant_sets = [frozenset(s) for k in range(3) for s in itertools.combinations(["CALCULATE", "EXECUTE_CODE"], k)]
    budgets = [Budget(st, tc, ca, su) for st in (1, 2, 4, 7, 64) for tc in (0, 1, 8) for ca in (0, 2, 16)
               for su in (1, 8)]
    n_checked = 0
    for subs in _sub_lists():
        for g in grant_sets:
            for b in budgets:
                for n in (1, 2, 3):
                    p = plan_subtasks(subs, grants=g, budget=b, n_candidates=n)
                    steps, dropped, feasible = _reference_plan(subs, g, b, n)
                    assert [(s.subtask, s.action.value, s.tool, s.note) for s in p.steps] == steps
                    assert list(p.dropped) == dropped and p.feasible == feasible
                    _invariants(p, subs, g, b, reg)
                    n_checked += 1
    assert n_checked > 30000


def _invariants(p, subs, grants, budget, reg):
    ids = {s.step_id: s for s in p.steps}
    sched = set(p.scheduled())
    dropped = {t for t, _ in p.dropped}
    assert sched | dropped == {t.task_id for t in subs} and not sched & dropped
    assert all(r for _, r in p.dropped)
    for t in subs:
        if t.task_id in sched:
            assert not set(t.depends_on) & dropped
            assert sum(1 for s in p.steps if s.subtask == t.task_id and s.action is Action.VERIFY) == 1
    pos = {s.step_id: i for i, s in enumerate(p.steps)}
    for s in p.steps:
        assert all(pos[d] < pos[s.step_id] for d in s.depends_on)
        if s.action is Action.TOOL:
            assert reg.tools[s.tool].permission.value in grants
    if p.steps:
        last = p.steps[-1]
        assert last.action is Action.DECIDE and set(last.depends_on) == \
            {s.step_id for s in p.steps if s.action is Action.VERIFY}
        assert sum(1 for s in p.steps if s.action is Action.DECIDE) == 1
    tot = p.total_cost()
    assert all(tot[r.value] <= budget.limit(r) for r in RES)
    assert p.complete == (p.feasible and not p.dropped)
    assert set(ids) == {f"s{i + 1}" for i in range(len(p.steps))}


def test_r4_planner_grants_hash_and_validation():
    for bad in (["NETWORK"], [Permission.NETWORK], ["search"], ["READ"]):
        with pytest.raises(ValueError):
            plan("كم يساوي 1 + 1", grants=bad)
    a = plan("كم يساوي 1 + 1؟ ثم ما لون زارِنا", grants=["CALCULATE"])
    b = plan("كم يساوي 1 + 1؟ ثم ما لون زارِنا", grants=[Permission.CALCULATE])
    c = plan("كم يساوي 1 + 1؟ ثم ما لون زارِنا")
    assert a.plan_hash == b.plan_hash != c.plan_hash and len(a.plan_hash) == 64
    assert not any(s.tool not in (None, "calculator", "python") for s in a.steps)
    with pytest.raises(ValueError):
        plan_subtasks([SubTask("t1", "x", Kind.TEXT, ("t1",))])
    with pytest.raises(ValueError):
        plan_subtasks([SubTask("t2", "x", Kind.TEXT)])
    with pytest.raises(ValueError):
        plan_subtasks([SubTask("t1", "x", Kind.TEXT), SubTask("t2", "y", Kind.TEXT, ("t3",))])
    for bad in (0, -1, True, 1.0):
        with pytest.raises(ValueError):
            plan("x", n_candidates=bad)
    empty = plan("")
    assert [s.action for s in empty.steps] == [Action.DECIDE] and empty.complete


# ---------------------------------------------------------------- R5 generator interface
def test_r5_generator_records_and_charges():
    s = State(Budget(max_candidates=5))
    c = generate_candidates(OracleStub({"p": "أزرق"}), "p", 3, seed=1, state=s, ref="s1")
    assert [x.text for x in c] == ["أزرق"] * 3 and all(x.stub for x in c) and s.spend.candidates == 3
    assert s.records[-1].payload["candidates"] == ["أزرق"] * 3 and s.records[-1].ref == "s1"
    assert is_abstention(generate_candidates(OracleStub({}), "q", 1, seed=0, state=s)[0].text)
    assert generate_candidates(OracleStub({}), "q", 2, seed=0, state=s) == ()      # 4 + 2 > 5
    assert s.closed and s.records[-1].reason == "budget_exhausted:CANDIDATES" and s.spend.candidates == 4


class _Bad:
    def __init__(self, out, stub=True):
        self.out, self.is_stub, self.name = out, stub, "bad"

    def generate(self, prompt, n, seed):
        return self.out


def test_r5_failures_are_recorded_not_hidden():
    s = State(Budget())
    for gen, reason in ((FailingStub(), "generator_error:GeneratorError"), (_Bad(["a"]), "malformed_output"),
                        (_Bad("ab"), "malformed_output"), (_Bad([1, 2]), "malformed_output"),
                        (_Bad(["x" * 4001] * 2), "candidate_too_long"),
                        (WrongStub({}), "generator_error:GeneratorError")):
        assert generate_candidates(gen, "p", 2, seed=0, state=s) == ()
        assert s.records[-1].outcome == "error" and s.records[-1].reason == reason
    assert s.spend.candidates == 12 and s.verify() == []
    with pytest.raises(ValueError):
        generate_candidates(_Bad(["a"], stub=False), "p", 1, seed=0, state=s)      # P6-03a BLOCKED
    with pytest.raises(ValueError):
        generate_candidates(object(), "p", 1, seed=0, state=s)
    for bad in (0, True, 1.0):
        with pytest.raises(ValueError):
            generate_candidates(OracleStub({}), "p", bad, seed=0, state=s)


def test_r5_seed_determinism_and_steps_precheck():
    g = ScriptedStub(["a", "b", "c"])
    assert g.generate("p", 4, 0) == ["a", "b", "c", "a"] and g.generate("p", 4, 1) == ["b", "c", "a", "b"]
    s1, s2 = State(Budget()), State(Budget())
    generate_candidates(g, "p", 3, seed=5, state=s1)
    generate_candidates(g, "p", 3, seed=5, state=s2)
    assert s1.to_json() == s2.to_json()
    calls = []

    class Counting(ScriptedStub):
        def generate(self, prompt, n, seed):
            calls.append(1)
            return super().generate(prompt, n, seed)

    s = State(Budget(max_steps=1))
    s.record("plan")
    assert generate_candidates(Counting(["a"]), "p", 1, seed=0, state=s) == () and calls == []
    assert s.records[-1].reason == "budget_exhausted:STEPS"


# ---------------------------------------------------------------- R6 self-consistency
def _cands(texts):
    return [Candidate(i, t, "x", True) for i, t in enumerate(texts)]


def test_r6_grouping_ties_and_flags():
    a = agreement(_cands(["الأزرق", "الازرق", "أزرق", "Red", "red"]))
    assert a.plurality == "الازرق" and a.plurality_share == Fraction(2, 5)   # normalize: hamza; "أزرق" differs
    t = agreement(_cands(["a", "b", "A", "B"]))
    assert t.plurality is None and t.representative is None and t.plurality_share is None
    ab = agreement(_cands(["لا أعرف", "I don't know", "x"]))
    assert ab.plurality == ABSTAIN_KEY and ab.abstained and ab.share(ABSTAIN_KEY) == Fraction(2, 3)
    assert agreement([]).plurality is None
    d = agreement(_cands(["x"])).to_dict()
    assert d["calibrated"] is False and d["is_verification"] is False and d["plurality_share"] == "1"
    assert not isinstance(a, VerificationState)
    with pytest.raises(ValueError):
        agreement([Candidate(0, "a", "x", True), Candidate(0, "b", "x", True)])
    from nawa.reasoning.consistency import Agreement
    with pytest.raises(ValueError):
        Agreement(0, (), None, None, calibrated=True)


def test_r6_bruteforce_random_votes():
    rng = random.Random(0)
    pool = ["a", "A", "b", "c ", "C", "لا اعرف", "d"]
    for _ in range(500):
        texts = [rng.choice(pool) for _ in range(rng.randint(1, 7))]
        a = agreement(_cands(texts))
        keys = [ABSTAIN_KEY if t == "لا اعرف" else t.strip().lower() for t in texts]
        counts = {k: keys.count(k) for k in keys}
        best = max(counts.values())
        winners = [k for k, v in counts.items() if v == best]
        assert a.plurality == (winners[0] if len(winners) == 1 else None)
        assert sum(a.share(k) for k in counts) == 1
        assert all(a.share(k) == Fraction(v, len(texts)) for k, v in counts.items())


# ---------------------------------------------------------------- R7 negative control
def test_r7_agreement_is_not_truth():
    q = "كم يساوي 3 + 5"
    p = plan(q, n_candidates=5)                          # no CALCULATE grant: the planner schedules generation
    assert [s.action for s in p.steps] == [Action.GENERATE, Action.CONSISTENCY, Action.VERIFY, Action.DECIDE]
    st = State(Budget())
    cands = generate_candidates(WrongStub({q: "7"}), q, 5, seed=0, state=st)
    ag = agreement(cands)
    assert ag.plurality == "7" and ag.plurality_share == 1                 # unanimous, and wrong
    report = check([ArithmeticClaim("c1", p.subtasks[0].expression, ag.representative)])
    assert report.verdict.state is VerificationState.CONTRADICTED
    assert decide(report).action is Decide.ABSTAIN
    good = generate_candidates(OracleStub({q: "8"}), q, 5, seed=0, state=st)
    rep = check([ArithmeticClaim("c1", p.subtasks[0].expression, agreement(good).representative)])
    assert rep.verdict.state is VerificationState.SUPPORTED and decide(rep).action is Decide.ANSWER_WITH_CITATIONS


# ---------------------------------------------------------------- R8 scope
def test_r8_no_numeric_threshold_and_stated_limits():
    src = ROOT / "src/nawa/reasoning"
    for name in ("consistency.py", "planner.py"):
        code = (src / name).read_text(encoding="utf-8")
        assert not re.search(r"(?<![\w.])\d+\.\d+(?![\w.])", code), name     # no float literal / cut-off
        assert not re.search(r"share\s*[<>]=?|[<>]=?\s*Fraction\(", code), name
    doc = (src / "decomposer.py").read_text(encoding="utf-8")
    assert "Lexical rules only" in doc and "P6-03a" in doc
    assert "BLOCKED" in (src / "generator.py").read_text(encoding="utf-8")
