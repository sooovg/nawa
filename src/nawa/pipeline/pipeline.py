"""The full NAWA inference pipeline, deterministic and replayable (ROADMAP P6-07, ADR-0008). Code only.

One call, :func:`run`, wires the components built in P6-01..P6-06 in a fixed order and writes every stage to a
hash-chained P6-03 :class:`~nawa.reasoning.state.State`. Nothing here understands language, and nothing here is a
model: the generator must be a stub (P6-03a is BLOCKED; external models need OD-10). **There is no quality claim**:
this proves the wiring, the budget accounting, the refusal paths and the replay, not that NAWA answers well (P6-09).

Stages (each is one record in the trace, in this order):

1. ``note:manifest`` — pipeline version, the query, the config, and the name of every component.
2. ``note:route`` — the P6-06 router. ``RouterConfig`` is derived from the config and the components: tools granted
   by the caller, retrieval available iff an index is given, reasoning available (P6-03 with a stub generator).
3. ``note:retrieve`` — only when ``RETRIEVAL`` is in the route's plan. Search, rerank (any
   :class:`~nawa.retrieval.rerank.Reranker`), and convert the hits to P6-04 evidence. BM25 scores are written as fixed
   12-significant-digit strings (the state refuses floats).
4. ``decompose`` — the P6-03 decomposer (or a replacement).
5. ``plan`` — the P6-03 planner, given only the budget that is left. Granted tools are the caller's grants **and**
   in the route's plan, so a "no tools" directive in the query also removes the tool from the plan.
6. the plan's steps, in order:
   - ``tool`` — the calculator or the sandbox through the P6-02 registry (allow-list, permissions, audit). The
     answer of the sub-question is the tool output, written as a claim (``expr = value`` or ``code -> stdout``).
     **The P6-04 checker then recomputes it with the same tool: this is a consistency check of the wiring, not
     independent evidence.**
   - ``generate`` — the stub generator, with seed ``config.seed + i`` for sub-question ``t<i+1>``.
   - ``consistency`` — P6-03 agreement. Its plurality answer is used only if there is a strict plurality and it is
     not an abstention. Agreement is never verification.
   - ``verify`` — P6-04 ``check`` on the sub-question's claims (``extract_claims`` for generated text) against the
     retrieved evidence.
7. ``decide`` — one final decision, by the first rule that applies:

   ====  ================================================  ====================================================
   rule  condition                                         action
   ====  ================================================  ====================================================
   Q0    the route is ambiguous                            ``ASK_CLARIFICATION`` (P6-05 rule D1)
   Q1    the run stopped (budget, see below)               ``ABSTAIN``, reason = the stop reason
   Q2    the decomposer failed or found no sub-question    ``ABSTAIN`` ``no_subtasks``
   Q3    the plan dropped a sub-question                   ``ABSTAIN`` ``plan_incomplete``
   Q4    a scheduled sub-question has no claim             ``ABSTAIN`` ``unanswered:<ids>``
   Q5    otherwise: P6-05 ``decide`` on P6-04 ``check``    ``ANSWER_WITH_CITATIONS`` or ``ABSTAIN``; a
         over **all** claims (so cross-question            ``RUN_TOOL`` or ``SEARCH`` decision is recorded and
         contradictions count)                             not performed here → ``ABSTAIN``
                                                           ``action_not_performed:<action>``
   ====  ================================================  ====================================================

   Q3 and Q4 are stricter than answering the parts that were answered: an answer that silently skips part of the
   question is not allowed.

Budget. Every record costs one STEP; tool calls, candidates and sub-questions cost their own resource. The planner
sees only what is left after stages 1–4 and reserves the ``plan`` and ``decide`` records. When the budget runs out
anywhere, the state writes a ``stop`` record and the run ends with Q1. A tool is never called unless its record can
be paid for first.

Determinism and replay. No clock, no randomness, no environment value enters the trace (the tool audit log keeps
its own timestamps, outside the trace). The same query, config and components give the same bytes. :func:`replay`
re-runs a saved trace with the given components and reports every difference; a tampered trace is refused by the
hash chain, and a different component is reported by name or by its effect, never passed silently.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from nawa.abstention.decision import Action as Decision_
from nawa.abstention.decision import Context, Mode, abstention_text, claim_kinds, decide
from nawa.evaluation.normalize import is_abstention
from nawa.reasoning.budget import Budget, Resource
from nawa.reasoning.consistency import agreement
from nawa.reasoning.decomposer import SubTask, decompose
from nawa.reasoning.generator import Generator, generate_candidates
from nawa.reasoning.planner import Action as Step_
from nawa.reasoning.planner import Plan, plan_subtasks
from nawa.reasoning.state import State, canonical
from nawa.retrieval.index import LexicalIndex
from nawa.retrieval.rerank import LexicalReranker, Reranker, apply_reranker, to_evidence
from nawa.routing.router import TOOL_HANDLERS, Handler, Route, RouterConfig, route
from nawa.tools.registry import Permission, ToolRegistry, default_registry
from nawa.verification.claims import ArithmeticClaim, CodeClaim, extract_claims
from nawa.verification.checkers import default_checkers
from nawa.verification.verifier import Report, check

PIPELINE_VERSION = "p6-07.1"
CLARIFY_TEXT = {"ar": "السؤال غير واضح بما يكفي. يرجى توضيحه.",
                "en": "The question is not clear enough. Please clarify it."}
TOOL_NAME = {"calculator": Permission.CALCULATE, "python": Permission.EXECUTE_CODE}
_GRANTABLE = frozenset(TOOL_HANDLERS.values())       # CALCULATE, EXECUTE_CODE; NETWORK can never be granted (OD-11)


def _name(obj: object) -> str:
    n = getattr(obj, "name", None)
    if isinstance(n, str) and n:
        return n
    q = getattr(obj, "__qualname__", None) or type(obj).__qualname__
    return f"{getattr(obj, '__module__', type(obj).__module__)}.{q}"


# ---- configuration and components -----------------------------------------------------------------------------
@dataclass(frozen=True)
class PipelineConfig:
    grants: frozenset = frozenset()          # "CALCULATE" / "EXECUTE_CODE" only
    budget: Budget = field(default_factory=Budget)
    n_candidates: int = 1
    seed: int = 0
    mode: Mode = Mode.STRICT
    has_context: bool = False
    retrieval_k: int = 5
    run_id: str = "run"

    def __post_init__(self) -> None:
        g = frozenset(x.value if isinstance(x, Permission) else x for x in self.grants)
        bad = sorted(str(x) for x in g - _GRANTABLE)
        if bad:
            raise ValueError(f"cannot grant {bad}: only {sorted(_GRANTABLE)} (no NETWORK/search before OD-11)")
        object.__setattr__(self, "grants", g)
        if not isinstance(self.budget, Budget):
            raise ValueError("budget must be a Budget")
        for f in ("n_candidates", "retrieval_k"):
            v = getattr(self, f)
            if isinstance(v, bool) or not isinstance(v, int) or v < 1:
                raise ValueError(f"{f} must be a positive int")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise ValueError("seed must be an int")
        if not isinstance(self.mode, Mode):
            raise ValueError("mode must be a Mode")
        if not isinstance(self.has_context, bool):
            raise ValueError("has_context must be a bool")
        if not isinstance(self.run_id, str) or not self.run_id.strip():
            raise ValueError("run_id must be a non-empty string")

    def to_dict(self) -> dict:
        return {"grants": sorted(self.grants), "budget": self.budget.to_dict(), "n_candidates": self.n_candidates,
                "seed": self.seed, "mode": self.mode.value, "has_context": self.has_context,
                "retrieval_k": self.retrieval_k, "run_id": self.run_id}

    @classmethod
    def from_dict(cls, d: dict) -> PipelineConfig:
        return cls(frozenset(d["grants"]), Budget.from_dict(d["budget"]), d["n_candidates"], d["seed"],
                   Mode(d["mode"]), d["has_context"], d["retrieval_k"], d["run_id"])


@dataclass(frozen=True)
class Components:
    """Every replaceable part. Defaults are the P6-01..P6-06 implementations; the generator has no default."""

    generator: object
    index: LexicalIndex | None = None
    reranker: object | None = None                       # defaults to LexicalReranker when an index is given
    checkers: tuple | None = None                        # defaults to P6-04 default_checkers()
    router: Callable[[str, RouterConfig], Route] = route
    decomposer: Callable[[str], list[SubTask]] = decompose
    tools: Callable[[frozenset], ToolRegistry] | None = None   # grants -> registry; defaults to default_registry

    def __post_init__(self) -> None:
        if not isinstance(self.generator, Generator):
            raise ValueError("generator must implement the Generator interface (name, is_stub, generate)")
        if self.generator.is_stub is not True:
            raise ValueError("only stub generators in P6-07: model generation is P6-03a (BLOCKED); external models "
                             "need OD-10")
        if self.index is not None and not isinstance(self.index, LexicalIndex):
            raise ValueError("index must be a P6-01 LexicalIndex")
        if self.reranker is not None and not isinstance(self.reranker, Reranker):
            raise ValueError("reranker must implement rerank(query, hits)")
        if self.checkers is not None:
            object.__setattr__(self, "checkers", tuple(self.checkers))
        for f in ("router", "decomposer"):
            if not callable(getattr(self, f)):
                raise ValueError(f"{f} must be callable")
        if self.tools is not None and not callable(self.tools):
            raise ValueError("tools must be a callable grants -> ToolRegistry")

    def resolved_reranker(self):
        if self.index is None:
            return None
        return self.reranker if self.reranker is not None else LexicalReranker()

    def resolved_checkers(self) -> tuple:
        return self.checkers if self.checkers is not None else default_checkers()

    def manifest(self) -> dict:
        idx = None
        if self.index is not None:
            idx = hashlib.sha256(canonical(self.index.manifest()).encode("utf-8")).hexdigest()
        rr = self.resolved_reranker()
        return {"generator": _name(self.generator), "generator_is_stub": True, "index_manifest_sha256": idx,
                "reranker": None if rr is None else _name(rr),
                "checkers": [k.name for k in self.resolved_checkers()],
                "router": _name(self.router), "decomposer": _name(self.decomposer),
                "tools": "default_registry" if self.tools is None else _name(self.tools)}


# ---- result ---------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class RunResult:
    action: str                 # ANSWER_WITH_CITATIONS | ABSTAIN | ASK_CLARIFICATION
    rule: str                   # Q0..Q5
    reason: str
    output: str
    state: State
    route: Route | None = None
    plan: Plan | None = None
    decision: dict | None = None       # P6-05 decision (Q0, Q5)

    calibrated: bool = False           # nothing here is a probability
    stub_only: bool = True             # every generated text came from a stub

    @property
    def trace(self) -> str:
        return self.state.to_json()

    @property
    def answered(self) -> bool:
        return self.action == Decision_.ANSWER_WITH_CITATIONS.value


def _lang(r: Route | None) -> str:
    return r.language if r is not None and r.language in ("ar", "en") else "ar"


def _score(x: float) -> str:
    return format(x, ".12g")


class _Stopped(Exception):
    pass


def run(query: str, config: PipelineConfig | None = None, components: Components | None = None) -> RunResult:
    if not isinstance(query, str):
        raise ValueError("query must be a string")
    if components is None:
        raise ValueError("components are required (there is no default generator)")
    cfg = config or PipelineConfig()
    if not isinstance(cfg, PipelineConfig):
        raise ValueError("config must be a PipelineConfig")
    st = State(cfg.budget, cfg.run_id)
    ctx: dict = {"route": None, "plan": None}

    def rec(kind: str, **kw):
        r = st.record(kind, **kw)
        if st.closed:
            raise _Stopped
        return r

    def finish(action: str, rule: str, reason: str, output: str, decision: dict | None = None) -> RunResult:
        if not st.closed:
            st.record("decide", ref="final", outcome="ok", reason=f"{rule}:{reason}",
                      payload={"action": action, "rule": rule, "reason": reason, "output": output,
                               "decision": decision, "calibrated": False, "stub_only": True})
        if st.closed:     # the decide record itself did not fit
            return RunResult(Decision_.ABSTAIN.value, "Q1", st.stop_reason or "stopped",
                             abstention_text(_lang(ctx["route"])), st, ctx["route"], ctx["plan"])
        return RunResult(action, rule, reason, output, st, ctx["route"], ctx["plan"], decision)

    try:
        return _run(query, cfg, components, st, rec, finish, ctx)
    except _Stopped:
        return RunResult(Decision_.ABSTAIN.value, "Q1", st.stop_reason or "stopped",
                         abstention_text(_lang(ctx["route"])), st, ctx["route"], ctx["plan"])


def _run(query, cfg, comp, st, rec, finish, ctx) -> RunResult:
    rec("note", ref="manifest", payload={"pipeline": PIPELINE_VERSION, "query": query,
                                         "query_sha256": hashlib.sha256(query.encode("utf-8")).hexdigest(),
                                         "config": cfg.to_dict(), "components": comp.manifest()})
    # 2. route
    rcfg = RouterConfig(granted_tools=cfg.grants, retrieval_available=comp.index is not None,
                        reasoning_available=True, has_context=cfg.has_context)
    r = comp.router(query, rcfg)
    if not isinstance(r, Route):
        raise ValueError("router must return a Route")
    ctx["route"] = r
    rec("note", ref="route", payload=r.to_dict())
    lang = _lang(r)
    if r.ambiguous:
        d = decide(check([]), Context(ambiguous=True))
        return finish(d.action.value, "Q0", d.reason, CLARIFY_TEXT[lang], d.to_dict())

    # 3. retrieve
    evidence = []
    if Handler.RETRIEVAL in r.plan and comp.index is not None:
        hits = comp.index.search(query, k=cfg.retrieval_k)
        rr = comp.resolved_reranker()
        hits = apply_reranker(rr, query, hits)
        evidence = to_evidence(comp.index, hits)
        rec("note", ref="retrieve", payload={"k": cfg.retrieval_k, "reranker": _name(rr),
                                             "hits": [{"chunk_id": h.chunk_id, "doc_id": h.doc_id,
                                                       "score": _score(h.score), "matched": list(h.matched)}
                                                      for h in hits]})

    # 4. decompose
    try:
        subs = list(comp.decomposer(query))
    except ValueError as e:
        rec("decompose", outcome="error", reason=f"decomposer_error:{e}"[:200], payload={"subtasks": []})
        return finish(Decision_.ABSTAIN.value, "Q2", "no_subtasks", abstention_text(lang))
    rec("decompose", payload={"subtasks": [t.to_dict() for t in subs]})
    if not subs:
        return finish(Decision_.ABSTAIN.value, "Q2", "no_subtasks", abstention_text(lang))

    # 5. plan, with what is left
    left = Budget.from_dict({res.value: st.budget.remaining(st.spend, res) for res in Resource})
    in_route = {TOOL_HANDLERS[h] for h in r.plan if h in TOOL_HANDLERS}
    grants = sorted(cfg.grants & in_route)
    p = plan_subtasks(subs, grants=grants, budget=left, n_candidates=cfg.n_candidates)
    ctx["plan"] = p
    rec("plan", payload=p.to_dict(), cost={Resource.SUBTASKS: len(p.scheduled())})
    if not p.feasible:
        return finish(Decision_.ABSTAIN.value, "Q3", "plan_incomplete", abstention_text(lang))

    # 6. execute
    registry = (comp.tools or (lambda g: default_registry(grants=[Permission(x) for x in g])))(frozenset(grants))
    by_id = {t.task_id: t for t in subs}
    cands: dict[str, tuple] = {}
    answer: dict[str, str | None] = {}
    why_none: dict[str, str] = {}
    claims: dict[str, list] = {}
    for s in p.steps:
        t = by_id.get(s.subtask) if s.subtask else None
        if s.action is Step_.TOOL:
            if not st.budget.allows(st.spend, {Resource.STEPS: 1, Resource.TOOL_CALLS: 1}):
                rec("tool", ref=s.step_id, cost={Resource.TOOL_CALLS: 1})      # records the stop and raises
            payload = {"expression": t.expression} if s.tool == "calculator" else {"code": t.code}
            res = registry.call(s.tool, payload, caller="pipeline")
            rec("tool", ref=s.step_id, outcome=res.outcome, reason=res.reason,
                payload={"tool": s.tool, "subtask": t.task_id, "input": payload, "output": res.output},
                cost={Resource.TOOL_CALLS: 1})
            if not res.ok:
                answer[t.task_id], why_none[t.task_id] = None, f"tool_{res.outcome}:{res.reason}"
            elif s.tool == "calculator":
                v = res.output["exact"]
                answer[t.task_id] = f"{t.expression} = {v}"
                claims[t.task_id] = [ArithmeticClaim(f"{t.task_id}.c1", t.expression, v)]
            else:
                out = res.output["stdout"]
                answer[t.task_id] = out
                claims[t.task_id] = [CodeClaim(f"{t.task_id}.c1", t.code, out)]
        elif s.action is Step_.GENERATE:
            seed = cfg.seed + int(t.task_id[1:]) - 1
            c = generate_candidates(comp.generator, t.text, cfg.n_candidates, seed=seed, state=st, ref=s.step_id)
            if st.closed:
                raise _Stopped
            cands[t.task_id] = c
            if not c:
                answer[t.task_id], why_none[t.task_id] = None, "generator_failed"
            elif cfg.n_candidates == 1:
                answer[t.task_id] = c[0].text
        elif s.action is Step_.CONSISTENCY:
            a = agreement(cands.get(t.task_id, ()))
            rec("consistency", ref=s.step_id, payload=a.to_dict())
            if answer.get(t.task_id, "") is None:
                pass
            elif a.plurality is None:
                answer[t.task_id], why_none[t.task_id] = None, "no_plurality"
            else:
                answer[t.task_id] = a.representative
        elif s.action is Step_.VERIFY:
            text = answer.get(t.task_id)
            if text is not None and t.task_id not in claims:
                if is_abstention(text):
                    answer[t.task_id], why_none[t.task_id] = None, "generator_abstained"
                else:
                    claims[t.task_id] = extract_claims(text, prefix=f"{t.task_id}.c")
                    if not claims[t.task_id]:
                        why_none[t.task_id] = "no_claims"
            cl = claims.get(t.task_id, [])
            if not cl:
                rec("verify", ref=s.step_id, outcome="refused",
                    reason=f"no_claims:{why_none.get(t.task_id, 'no_claims')}", payload={"subtask": t.task_id})
                continue
            rep = check(cl, evidence, comp.resolved_checkers())
            rec("verify", ref=s.step_id, payload={"subtask": t.task_id, "report": rep.to_dict()})

    # 7. decide
    if p.dropped:
        return finish(Decision_.ABSTAIN.value, "Q3", "plan_incomplete", abstention_text(lang))
    missing = [tid for tid in p.scheduled() if not claims.get(tid)]
    if missing:
        return finish(Decision_.ABSTAIN.value, "Q4", "unanswered:" + ",".join(missing), abstention_text(lang))
    all_claims = [c for tid in p.scheduled() for c in claims[tid]]
    rep: Report = check(all_claims, evidence, comp.resolved_checkers())
    d = decide(rep, Context(mode=cfg.mode, granted_tools=frozenset(grants),
                            tool_calls_left=st.budget.remaining(st.spend, Resource.TOOL_CALLS),
                            claim_kinds=claim_kinds(all_claims)))
    dd = {**d.to_dict(), "report": rep.to_dict()}
    if d.action is Decision_.ANSWER_WITH_CITATIONS:
        return finish(d.action.value, "Q5", d.reason, "\n".join(answer[tid] for tid in p.scheduled()), dd)
    if d.action is Decision_.ABSTAIN:
        return finish(d.action.value, "Q5", d.reason, abstention_text(lang), dd)
    return finish(Decision_.ABSTAIN.value, "Q5", f"action_not_performed:{d.action.value}", abstention_text(lang), dd)


# ---- replay ---------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Replay:
    ok: bool
    problems: tuple[str, ...]
    result: RunResult | None = None


def replay(trace: str, components: Components) -> Replay:
    """Re-run a saved trace with ``components`` and compare byte for byte. Never raises on a bad trace."""
    try:
        saved = State.from_json(trace)
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as e:
        return Replay(False, (f"invalid_trace:{e}",))
    if not saved.records or saved.records[0].kind != "note" or saved.records[0].ref != "manifest":
        return Replay(False, ("invalid_trace:no manifest record",))
    m = saved.records[0].payload
    if m.get("pipeline") != PIPELINE_VERSION:
        return Replay(False, (f"pipeline_version:{m.get('pipeline')}!={PIPELINE_VERSION}",))
    problems = []
    try:
        cm = components.manifest()
    except Exception as e:      # noqa: BLE001 - a broken component is a reported problem, not a crash
        return Replay(False, (f"components:{type(e).__name__}",))
    for k in sorted(set(m["components"]) | set(cm)):
        if m["components"].get(k) != cm.get(k):
            problems.append(f"component:{k}")
    res = run(m["query"], PipelineConfig.from_dict(m["config"]), components)
    new = res.state.to_dict()["records"]
    old = saved.to_dict()["records"]
    for i in range(max(len(old), len(new))):
        a = old[i] if i < len(old) else None
        b = new[i] if i < len(new) else None
        if a != b:
            problems.append(f"record:{i + 1}:" + ("missing" if b is None else "extra" if a is None
                                                   else f"{(a['kind'], a['ref'])}"))
            break
    if res.trace != trace and not problems:
        problems.append("bytes_differ")
    return Replay(not problems, tuple(problems), res)


# ---- stub smoke (labelled; never P6-09 output) ---------------------------------------------------------------
SMOKE_LABEL = "P6-07 stub smoke: wiring check with stub generators; NOT P6-09 output; no quality claim (ADR-0008)"


def smoke(queries: Iterable[str], components: Components, config: PipelineConfig | None = None) -> dict:
    counts: dict[str, int] = {}
    heads = []
    for q in queries:
        r = run(q, config, components)
        counts[f"{r.action}/{r.rule}"] = counts.get(f"{r.action}/{r.rule}", 0) + 1
        heads.append(r.state.head)
    return {"label": SMOKE_LABEL, "is_p6_09": False, "quality_claim": False, "stub_only": True,
            "n": len(heads), "counts": dict(sorted(counts.items())),
            "traces_sha256": hashlib.sha256("".join(heads).encode()).hexdigest()}
