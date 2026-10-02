"""P6-07 — the full deterministic, replayable pipeline (ROADMAP P6-07, ADR-0008). Code only, stub generators only.

Success criteria, registered before the first run (no quality claim; synthetic questions with invented names):

- **C1 determinism:** the same query, config and components give byte-identical traces, within one process and
  across fresh processes with different ``PYTHONHASHSEED``.
- **C2 replay:** every corpus trace replays exactly; a tampered trace is refused; a replaced component (generator,
  index, reranker, checkers) is reported, never passed silently.
- **C3 reference:** on a combinatorial corpus (sub-question kinds x tool grants x per-sub-question generator
  behaviour x n candidates) and on a budget sweep, (action, rule, P6-05 rule) equals a reference written
  independently from the documented rules Q0..Q5 and the cost model.
- **C4 safety invariants on every corpus run:** an answer only with a complete plan and every claim SUPPORTED; the
  state verifies and never exceeds the budget; exactly one final record (``decide`` or ``stop``); the number of tool
  records equals the TOOL_CALLS spend; no tool call without its grant; no denied call; the actual spend equals the
  planned spend when the run is not stopped.
- **C5 refusals:** ambiguity asks (Q0); decomposer failure abstains (Q2); a non-stub generator and a NETWORK grant
  are refused; a web-search request performs nothing; a "no tools" directive removes the tool; a tool timeout or
  error leaves the sub-question unanswered (Q4).
- **C6 negative control:** a unanimous wrong stub is CONTRADICTED and the pipeline abstains; the oracle answers.
- **C7 replaceability:** every component can be replaced; the replacement is recorded by name and used; invalid
  components are rejected.
- **C8 scope:** the smoke harness is labelled not P6-09 and makes no quality claim; nothing is calibrated; the
  package imports no model or network library (checked in ``test_original_system_policy.py``).
"""

from __future__ import annotations

import hashlib
import itertools
import json
import os
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass

import pytest

from nawa.abstention.decision import abstention_text
from nawa.pipeline import CLARIFY_TEXT, SMOKE_LABEL, Components, PipelineConfig, replay, run, smoke
from nawa.reasoning.budget import Budget
from nawa.reasoning.decomposer import SubTask, decompose
from nawa.reasoning.generator import OracleStub, ScriptedStub, WrongStub
from nawa.retrieval.index import build
from nawa.retrieval.metadata import Document
from nawa.retrieval.rerank import LexicalReranker
from nawa.routing.router import Handler, RouterConfig, route
from nawa.tools.registry import default_registry
from nawa.tools.sandbox import SandboxPolicy
from nawa.verification.checkers import CalculatorChecker
from nawa.verification.claims import extract_claims

AB = abstention_text("ar")
INDEX = build([Document("d1", "لون زارِنا أزرق.", source="synthetic"),
               Document("d2", "عمر كولموت سبعة أعوام.", source="synthetic")])

# part -> (prompt text after decomposition, kind, correct answer, wrong answer, expression)
PARTS = {
    "A": ("احسب 3 + 5", "arith", "3 + 5 = 8", "3 + 5 = 7", "3 + 5"),
    "B": ("احسب 12 / 4", "arith", "12 / 4 = 3", "12 / 4 = 5", "12 / 4"),
    "T": ("ما لون زارِنا", "text", "لون زارِنا أزرق [@d1#0]", "لون زارِنا أحمر [@d1#0]", None),
}
BEHAVIOURS = ("correct", "wrong", "abstain", "tie", "fail")


@dataclass(frozen=True)
class TableStub:
    """Test stub: per prompt, a behaviour. ``tie`` alternates correct / wrong by candidate index."""
    behaviour: tuple                    # ((prompt, behaviour), ...)
    name: str = "table-stub"
    is_stub: bool = True

    def generate(self, prompt: str, n: int, seed: int) -> list[str]:
        b = dict(self.behaviour).get(prompt, "fail")
        part = next(p for p in PARTS.values() if p[0] == prompt) if b != "fail" else None
        if b == "fail":
            raise RuntimeError("scripted failure")
        if b == "correct":
            return [part[2]] * n
        if b == "wrong":
            return [part[3]] * n
        if b == "abstain":
            return [AB] * n
        return [part[2] if i % 2 == 0 else part[3] for i in range(n)]


def _query(parts: tuple[str, ...]) -> str:
    return "؟ ".join(PARTS[p][0] for p in parts)


def _comps(behaviour=(), **kw) -> Components:
    return Components(generator=TableStub(tuple(behaviour)), index=INDEX, **kw)


# ---- the independent reference ---------------------------------------------------------------------------------
def _cands(part: str, b: str, n: int) -> list[str] | None:
    p = PARTS[part]
    return {"correct": [p[2]] * n, "wrong": [p[3]] * n, "abstain": [AB] * n,
            "tie": [p[2] if i % 2 == 0 else p[3] for i in range(n)], "fail": None}[b]


def reference(parts, grants, behaviour, n, budget: Budget):
    """(action, rule, p6_05_rule) from the documented rules, without running the pipeline's code paths."""
    q = _query(parts)
    r = route(q, RouterConfig(granted_tools=frozenset(grants), retrieval_available=True, reasoning_available=True))
    retrieval = Handler.RETRIEVAL in r.plan
    tool_ok = "CALCULATE" in grants and Handler.CALCULATOR in r.plan
    steps_left = budget.max_steps - (3 + (1 if retrieval else 0))       # manifest, route, [retrieve], decompose
    if steps_left < 2:          # the plan record and the decide record do not both fit
        return ("ABSTAIN", "Q1", None)
    left = {"S": steps_left - 2, "T": budget.max_tool_calls, "C": budget.max_candidates, "U": budget.max_subtasks}
    dropped, answers = False, []
    for i, part in enumerate(parts):
        tool = PARTS[part][1] == "arith" and tool_ok
        need = {"S": 2, "T": 1, "C": 0, "U": 1} if tool else {"S": 2 + (n > 1), "T": 0, "C": n, "U": 1}
        if any(need[k] > left[k] for k in need):
            dropped = True
            continue
        for k in need:
            left[k] -= need[k]
        if tool:
            answers.append((part, "correct"))
            continue
        c = _cands(part, dict(behaviour).get(PARTS[part][0], "fail"), n)
        if c is None or (n == 1 and c[0] == AB):
            answers.append((part, None))
            continue
        top = Counter(c).most_common()
        if len(top) > 1 and top[0][1] == top[1][1]:
            answers.append((part, None))
        elif top[0][0] == AB:
            answers.append((part, None))
        else:
            answers.append((part, "correct" if top[0][0] == PARTS[part][2] else "wrong"))
    if dropped:
        return ("ABSTAIN", "Q3", None)
    if any(a is None for _, a in answers):
        return ("ABSTAIN", "Q4", None)
    states = []
    for part, a in answers:
        if PARTS[part][1] == "arith":
            states.append("S" if a == "correct" else "X")
        else:
            states.append("S" if (a == "correct" and retrieval) else "N")
    if "X" in states:
        return ("ABSTAIN", "Q5", "D3")
    if all(s == "S" for s in states):
        return ("ANSWER_WITH_CITATIONS", "Q5", "D5")
    return ("ABSTAIN", "Q5", "D8")


def _observed(res):
    return (res.action, res.rule, (res.decision or {}).get("rule") if res.rule == "Q5" else None)


SEQS = [s for k in (1, 2) for s in itertools.product("ABT", repeat=k)]
GRANTS = [frozenset(), frozenset({"CALCULATE"})]


def _behaviours(parts):
    gen = sorted({p for p in parts})
    for combo in itertools.product(BEHAVIOURS, repeat=len(gen)):
        yield tuple((PARTS[p][0], b) for p, b in zip(gen, combo))


def _corpus():
    for parts in SEQS:
        for g in GRANTS:
            for beh in _behaviours(parts):
                for n in (1, 2, 3):
                    yield parts, g, beh, n, Budget()


def _check_invariants(res, budget: Budget, granted: frozenset):
    st = res.state
    assert st.verify() == []
    recs = st.records
    for r in ("STEPS", "TOOL_CALLS", "CANDIDATES", "SUBTASKS"):
        assert st.spend.to_dict()[r] <= budget.to_dict()[r]
    assert recs[-1].kind in ("decide", "stop") and sum(r.kind in ("decide", "stop") for r in recs) == 1
    assert (recs[-1].kind == "stop") == (res.rule == "Q1")
    tools = [r for r in recs if r.kind == "tool"]
    assert len(tools) == st.spend.to_dict()["TOOL_CALLS"]
    for t in tools:
        need = {"calculator": "CALCULATE", "python": "EXECUTE_CODE"}[t.payload["tool"]]
        assert need in granted and t.outcome != "denied"
    if res.answered:
        assert res.rule == "Q5" and res.plan.complete
        assert all(c["state"] == "SUPPORTED" for c in res.decision["report"]["verdict"]["claims"])
        assert res.decision["report"]["strict_ok"] is True
    if res.rule != "Q1" and res.plan is not None and res.plan.feasible:
        overhead = sum(1 for r in recs if r.kind in ("note", "decompose"))
        planned = res.plan.total_cost()
        assert st.spend.to_dict() == {**planned, "STEPS": planned["STEPS"] + overhead}
    assert res.calibrated is False and res.stub_only is True


# ---- C3 + C4 ---------------------------------------------------------------------------------------------------
def test_c3_c4_corpus_matches_reference_and_invariants():
    n_runs, seen = 0, Counter()
    for parts, g, beh, n, b in _corpus():
        q = _query(parts)
        res = run(q, PipelineConfig(grants=g, budget=b, n_candidates=n), _comps(beh))
        exp = reference(parts, g, beh, n, b)
        assert _observed(res) == exp, (parts, sorted(g), beh, n, _observed(res), exp)
        _check_invariants(res, b, g)
        seen[exp] += 1
        n_runs += 1
    assert n_runs == 1080          # (3*5 + 3*5 + 6*25) behaviour cases x 2 grants x 3 n
    for must in [("ANSWER_WITH_CITATIONS", "Q5", "D5"), ("ABSTAIN", "Q4", None), ("ABSTAIN", "Q5", "D3"),
                 ("ABSTAIN", "Q5", "D8")]:
        assert seen[must] > 0, must           # every outcome is exercised


def test_c3_cross_question_contradiction():
    # One prompt asked twice; the seed differs per sub-question, so a seed-driven stub answers 8 then 7. P6-04 rule
    # D2 (self-contradiction) covers FactClaims only and the pipeline extracts none, so this is D3 (the wrong claim
    # is CONTRADICTED by the calculator). Stated limit: D2 is unreachable through this pipeline.
    q = "احسب 3 + 5؟ احسب 3 + 5"
    res = run(q, PipelineConfig(), Components(generator=ScriptedStub(["3 + 5 = 8", "3 + 5 = 7"])))
    assert (res.action, res.rule, res.decision["rule"]) == ("ABSTAIN", "Q5", "D3")
    assert res.decision["targets"] == ["t2.c1"] and res.decision["report"]["claim_conflicts"] == []


def test_c3_c4_budget_sweep_matches_reference():
    seen = Counter()
    beh = tuple((p[0], "correct") for p in PARTS.values())
    for parts in SEQS:
        for g in GRANTS:
            for n in (1, 2):
                for steps, tools, cands, subs in itertools.product((0, 1, 3, 4, 5, 6, 7, 9, 64), (0, 1), (0, 1, 2),
                                                                   (1, 2)):
                    b = Budget(max_steps=steps, max_tool_calls=tools, max_candidates=cands, max_subtasks=subs)
                    res = run(_query(parts), PipelineConfig(grants=g, budget=b, n_candidates=n), _comps(beh))
                    exp = reference(parts, g, beh, n, b)
                    assert _observed(res) == exp, (parts, sorted(g), n, b, _observed(res), exp)
                    _check_invariants(res, b, g)
                    seen[exp[1]] += 1
    assert seen["Q1"] and seen["Q3"] and seen["Q5"]


def test_c4_no_denied_tool_call_and_audit_matches(tmp_path):
    regs = []

    def factory(grants):
        from nawa.tools.registry import Permission
        r = default_registry(grants=[Permission(x) for x in grants])
        regs.append(r)
        return r

    res = run(_query(("A", "B")), PipelineConfig(grants={"CALCULATE"}), _comps(tools=factory))
    assert res.answered and res.output == "3 + 5 = 8\n12 / 4 = 3"
    recs = regs[0].audit.records
    assert len(recs) == 2 and all(r.outcome == "ok" and r.caller == "pipeline" for r in recs)


# ---- C1 determinism --------------------------------------------------------------------------------------------
def test_c1_same_inputs_same_bytes_in_process():
    beh = tuple((p[0], "tie") for p in PARTS.values())
    for parts in SEQS:
        for n in (1, 2, 3):
            a = run(_query(parts), PipelineConfig(n_candidates=n), _comps(beh)).trace
            b = run(_query(parts), PipelineConfig(n_candidates=n), _comps(beh)).trace
            assert a == b


_CHILD = r"""
import hashlib, sys
sys.path.insert(0, {tests!r})
from test_pipeline import _query, _comps, PARTS, SEQS
from nawa.pipeline import run, PipelineConfig
beh = tuple((p[0], "correct") for p in PARTS.values())
h = hashlib.sha256()
for parts in SEQS:
    for g in (frozenset(), frozenset({{"CALCULATE"}})):
        h.update(run(_query(parts), PipelineConfig(grants=g, n_candidates=3), _comps(beh)).trace.encode())
print(h.hexdigest())
"""


def test_c1_same_bytes_across_processes_and_hash_seeds():
    tests = os.path.dirname(__file__)
    outs = set()
    for seed in ("0", "1", "12345"):
        env = {**os.environ, "PYTHONHASHSEED": seed}
        p = subprocess.run([sys.executable, "-c", _CHILD.format(tests=tests)], capture_output=True, text=True,
                           env=env, timeout=300)
        assert p.returncode == 0, p.stderr[-2000:]
        outs.add(p.stdout.strip())
    beh = tuple((p[0], "correct") for p in PARTS.values())
    h = hashlib.sha256()
    for parts in SEQS:
        for g in GRANTS:
            h.update(run(_query(parts), PipelineConfig(grants=g, n_candidates=3), _comps(beh)).trace.encode())
    outs.add(h.hexdigest())
    assert len(outs) == 1


# ---- C2 replay -------------------------------------------------------------------------------------------------
def test_c2_every_corpus_trace_replays():
    count = 0
    for parts, g, beh, n, b in _corpus():
        if n == 2:
            continue
        comps = _comps(beh)
        res = run(_query(parts), PipelineConfig(grants=g, budget=b, n_candidates=n), comps)
        rp = replay(res.trace, comps)
        assert rp.ok and rp.problems == () and rp.result.trace == res.trace
        count += 1
    assert count == 720            # the n = 1 and n = 3 runs of the corpus


def test_c2_tampering_and_replaced_components_are_reported():
    beh = (("ما لون زارِنا", "correct"),)
    comps = _comps(beh)
    res = run("ما لون زارِنا", PipelineConfig(), comps)
    assert res.answered
    t = res.trace
    d = json.loads(t)
    d["records"][0]["payload"]["query"] = "ما لون كولموت"          # change the query, keep the hashes
    assert not replay(json.dumps(d), comps).ok
    assert replay(json.dumps(d), comps).problems[0].startswith("invalid_trace")
    assert replay("not json", comps).problems[0].startswith("invalid_trace")
    # a different generator under another name, a different generator under the same name
    other = Components(generator=OracleStub({"ما لون زارِنا": "لون زارِنا أزرق [@d1#0]"}), index=INDEX)
    rp = replay(t, other)
    assert not rp.ok and "component:generator" in rp.problems
    same_name = _comps((("ما لون زارِنا", "wrong"),))
    rp = replay(t, same_name)
    assert not rp.ok and any(p.startswith("record:") for p in rp.problems)
    # another index, another reranker, other checkers
    idx2 = build([Document("d1", "لون زارِنا أخضر.", source="synthetic")])
    rp = replay(t, Components(generator=TableStub(beh), index=idx2))
    assert not rp.ok and "component:index_manifest_sha256" in rp.problems

    class Reverse:
        name = "reverse"

        def rerank(self, query, hits):
            return list(reversed(list(hits)))
    assert "component:reranker" in replay(t, _comps(beh, reranker=Reverse())).problems
    assert "component:checkers" in replay(t, _comps(beh, checkers=(CalculatorChecker(),))).problems


# ---- C5 refusals -----------------------------------------------------------------------------------------------
def test_c5_ambiguity_asks():
    res = run("ما هذا", PipelineConfig(), _comps())
    assert (res.action, res.rule) == ("ASK_CLARIFICATION", "Q0") and res.output == CLARIFY_TEXT["ar"]
    assert res.decision["rule"] == "D1" and not any(r.kind in ("tool", "generate") for r in res.state.records)


def test_c5_decomposer_failure_and_empty_plan_abstain():
    res = run("ما لون زارِنا " * 400, PipelineConfig(), _comps())
    assert (res.action, res.rule, res.reason) == ("ABSTAIN", "Q2", "no_subtasks")
    assert any(r.kind == "decompose" and r.outcome == "error" for r in res.state.records)
    res = run("ما لون زارِنا", PipelineConfig(), _comps(decomposer=lambda q: []))
    assert (res.action, res.rule) == ("ABSTAIN", "Q2") and res.output == AB


def test_c5_refuses_non_stub_generator_and_network():
    @dataclass(frozen=True)
    class Model:
        name: str = "model"
        is_stub: bool = False

        def generate(self, prompt, n, seed):
            return ["x"] * n
    with pytest.raises(ValueError, match="P6-03a"):
        Components(generator=Model())
    with pytest.raises(ValueError, match="generator"):
        Components(generator=object())
    for g in ({"NETWORK"}, {"READ_FILES"}, {"search"}):
        with pytest.raises(ValueError, match="OD-11"):
            PipelineConfig(grants=g)
    with pytest.raises(ValueError, match="components"):
        run("ما لون زارِنا")


def test_c5_web_search_request_performs_nothing():
    res = run("ابحث في الانترنت عن لون زارِنا", PipelineConfig(grants={"CALCULATE"}), _comps())
    route_rec = next(r for r in res.state.records if r.ref == "route")
    assert "web_search:requested" in route_rec.payload["directives"]
    assert not any(r.kind == "tool" for r in res.state.records)
    assert res.action == "ABSTAIN"


def test_c5_no_tools_directive_removes_the_tool():
    q = "احسب 3 + 5 بدون أدوات"
    beh = ((q, "correct"),)
    res = run(q, PipelineConfig(grants={"CALCULATE"}), _comps(beh))
    assert not any(r.kind == "tool" for r in res.state.records)
    assert res.plan.grants == () and any(r.kind == "generate" for r in res.state.records)


def test_c5_code_paths_tool_timeout_and_error():
    q = "```python\nprint(2 + 3)\n```"
    res = run(q, PipelineConfig(grants={"EXECUTE_CODE"}), _comps())
    assert res.answered and res.output == "5\n"
    assert [r.payload["tool"] for r in res.state.records if r.kind == "tool"] == ["python"]
    fast = lambda g: default_registry(grants=[__import__("nawa.tools.registry", fromlist=["x"]).Permission(x)  # noqa: E731
                                              for x in g], policy=SandboxPolicy(timeout_s=1.0, cpu_s=5))
    res = run("```python\nwhile True:\n    pass\n```", PipelineConfig(grants={"EXECUTE_CODE"}), _comps(tools=fast))
    assert (res.action, res.rule) == ("ABSTAIN", "Q4")
    assert next(r for r in res.state.records if r.kind == "tool").outcome == "timeout"
    res = run("احسب 1 / 0", PipelineConfig(grants={"CALCULATE"}), _comps())
    assert (res.action, res.rule, res.reason) == ("ABSTAIN", "Q4", "unanswered:t1")
    assert next(r for r in res.state.records if r.kind == "tool").outcome == "error"


# ---- C6 negative control ---------------------------------------------------------------------------------------
def test_c6_unanimous_wrong_stub_is_refused_and_oracle_answers():
    q = "احسب 3 + 5"
    wrong = run(q, PipelineConfig(n_candidates=5), Components(generator=WrongStub({q: "3 + 5 = 7"})))
    cons = next(r for r in wrong.state.records if r.kind == "consistency").payload
    assert cons["plurality_share"] == "1" and cons["is_verification"] is False
    assert (wrong.action, wrong.decision["rule"]) == ("ABSTAIN", "D3") and wrong.output == AB
    right = run(q, PipelineConfig(n_candidates=5), Components(generator=OracleStub({q: "3 + 5 = 8"})))
    assert right.answered and right.output == "3 + 5 = 8"


def test_c6_citation_of_a_retrieved_chunk_is_parsed():
    # P6-01 chunk ids contain "#"; before P6-07 the P6-04 citation pattern dropped them (defect fixed here).
    (c,) = extract_claims("لون زارِنا أزرق [@d1#0]")
    assert c.citations == ("d1#0",) and c.text == "لون زارِنا أزرق"
    (c,) = extract_claims("نص [@src:a-1_v2]")
    assert c.citations == ("src:a-1_v2",)
    # stated limit (P6-04 sentence split, unchanged): a dot inside a citation id splits the sentence
    assert len(extract_claims("نص [@a.b]")) == 2


# ---- C7 replaceability -----------------------------------------------------------------------------------------
def test_c7_components_are_replaceable_and_recorded():
    calls = []

    class Reverse:
        name = "reverse-reranker"

        def rerank(self, query, hits):
            calls.append(len(hits))
            return list(reversed(list(hits)))

    def one_task(q):
        return [SubTask("t1", q.strip(), decompose(q)[0].kind)]
    one_task.name = "one-task"
    beh = (("ما لون زارِنا", "correct"),)
    res = run("ما لون زارِنا", PipelineConfig(), _comps(beh, reranker=Reverse(), decomposer=one_task))
    man = res.state.records[0].payload["components"]
    assert man["reranker"] == "reverse-reranker" and man["decomposer"] == "one-task" and calls
    assert next(r for r in res.state.records if r.ref == "retrieve").payload["reranker"] == "reverse-reranker"
    only_calc = run("ما لون زارِنا", PipelineConfig(), _comps(beh, checkers=(CalculatorChecker(),)))
    assert only_calc.action == "ABSTAIN" and only_calc.decision["report"]["unchecked"] == ["t1.c1"]
    for bad in ({"index": "idx"}, {"reranker": object()}, {"router": 3}, {"decomposer": None}, {"tools": 1}):
        with pytest.raises(ValueError):
            Components(generator=TableStub(()), **bad)
    with pytest.raises(ValueError, match="Route"):
        run("ما لون زارِنا", PipelineConfig(), _comps(router=lambda q, c: "x"))


def test_c7_default_reranker_and_no_index():
    res = run("ما لون زارِنا", PipelineConfig(), Components(generator=TableStub((("ما لون زارِنا", "correct"),))))
    assert res.state.records[0].payload["components"]["reranker"] is None
    assert not any(r.ref == "retrieve" for r in res.state.records)
    assert res.action == "ABSTAIN"                       # no index: the citation has no evidence
    assert isinstance(_comps().resolved_reranker(), LexicalReranker)


# ---- C8 scope --------------------------------------------------------------------------------------------------
def test_c8_smoke_is_labelled_not_p6_09():
    beh = tuple((p[0], "correct") for p in PARTS.values())
    s = smoke([_query(p) for p in SEQS], _comps(beh))
    assert s["label"] == SMOKE_LABEL and "NOT P6-09" in s["label"]
    assert s["is_p6_09"] is False and s["quality_claim"] is False and s["stub_only"] is True
    assert s["n"] == len(SEQS) and sum(s["counts"].values()) == len(SEQS)
    assert smoke([_query(p) for p in SEQS], _comps(beh)) == s           # deterministic


def test_c8_final_record_never_claims_calibration():
    res = run("ما لون زارِنا", PipelineConfig(), _comps((("ما لون زارِنا", "correct"),)))
    p = res.state.records[-1].payload
    assert p["calibrated"] is False and p["stub_only"] is True and p["decision"]["calibrated"] is False


# ---- added after the first mutation round (3 survivors; code unchanged) ------------------------------------------
def test_c3_plurality_not_first_candidate_is_used():
    q = "احسب 3 + 5"
    res = run(q, PipelineConfig(n_candidates=3), Components(generator=ScriptedStub(["3 + 5 = 7", "3 + 5 = 8",
                                                                                       "3 + 5 = 8"])))
    assert res.answered and res.output == "3 + 5 = 8"


def test_c3_tie_is_recorded_as_no_plurality():
    res = run("احسب 3 + 5", PipelineConfig(n_candidates=2), _comps((("احسب 3 + 5", "tie"),)))
    assert (res.action, res.rule) == ("ABSTAIN", "Q4")
    assert next(r for r in res.state.records if r.kind == "verify").reason == "no_claims:no_plurality"


def test_c4_tool_is_never_called_when_its_record_cannot_be_paid(monkeypatch):
    import nawa.pipeline.pipeline as pl
    real = pl.plan_subtasks
    monkeypatch.setattr(pl, "plan_subtasks", lambda subs, **kw: real(subs, **{**kw, "budget": Budget()}))
    regs = []

    def factory(grants):
        from nawa.tools.registry import Permission
        regs.append(default_registry(grants=[Permission(x) for x in grants]))
        return regs[-1]
    b = Budget(max_tool_calls=0)
    res = run("احسب 3 + 5", PipelineConfig(grants={"CALCULATE"}, budget=b), _comps(tools=factory))
    assert (res.action, res.rule, res.reason) == ("ABSTAIN", "Q1", "budget_exhausted:TOOL_CALLS")
    assert regs and regs[0].audit.records == [] and res.state.verify() == []
