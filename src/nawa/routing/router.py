"""Deterministic query router (ROADMAP P6-06, ADR-0008): task classification, handler choice, escalation, fallback,
trace.

**Lexical rules only.** The router matches fixed word lists and patterns on the text after
``nawa.evaluation.normalize.normalize`` (reused, unchanged). The only morphology is a leading ``و`` on the first word
of a phrase. It does not understand meaning, synonyms, paraphrase or
context: ``أوجد ناتج`` is not ``احسب`` unless it is listed, and a pronoun attached to a word (``طوله``) is not seen as
a reference. Every outcome is explained by the rule ids in its trace.

**Classification.** Rules are checked in a fixed order, and a query may match several kinds:
- K1 ``ARITHMETIC``: an expression ``<number> <op> <number>``, or a calculation verb with a number.
- K2 ``CODE``: a code fence, ``def name(``, or a programming word.
- K3 ``REASONING``: why / how / explain / compare / prove / steps.
- K4 ``FACT``: a question word (who, what, when, where, how many…), only when K1–K3 found nothing. A question word
  alone is a weak signal.
- K5 ``OTHER``: nothing matched.

**Ambiguity** (any flag → ``ASK_CLARIFICATION``, then ``ABSTAIN``):
- A1 ``EMPTY``: no words.
- A2 ``NO_CONTENT``: only function words.
- A3 ``UNRESOLVED_REFERENCE``: a standalone pronoun or demonstrative that is last, or followed only by function
  words, and the caller has no conversation context. A demonstrative followed by a noun (``هذا المرفاد``) is not a
  reference.
- A4 ``CONFLICTING_DIRECTIVES``: the query gives two opposite instructions (tools / no tools, brief / detailed, cite /
  no sources, Arabic / English).

**Plan.** Each kind needs a set of handlers (``PLAN_FOR``). The plan is the union, in one fixed order:
tools, then retrieval, then reasoning (``HANDLER_ORDER``). It keeps only available handlers. It always ends with ``ABSTAIN``, so there is always a fallback.
- An unavailable handler is skipped and the reason is written in the trace (tool not granted, no retrieval index,
  P6-03 reasoning not built).
- A ``no tools`` directive removes the tool handlers.
- A request to search the web is recorded and never routed: there is no search handler (P6-02a, OD-11).

**Escalation.** :meth:`Route.escalate` moves from the current handler to the next one in the plan and records why.
``ABSTAIN`` is final.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from enum import Enum

from nawa.evaluation.normalize import normalize, normalize_digits


class Kind(str, Enum):
    ARITHMETIC = "ARITHMETIC"
    CODE = "CODE"
    REASONING = "REASONING"
    FACT = "FACT"
    OTHER = "OTHER"


class Handler(str, Enum):
    CALCULATOR = "CALCULATOR"
    CODE_SANDBOX = "CODE_SANDBOX"
    RETRIEVAL = "RETRIEVAL"
    REASONING = "REASONING"
    ASK_CLARIFICATION = "ASK_CLARIFICATION"
    ABSTAIN = "ABSTAIN"


class Flag(str, Enum):
    EMPTY = "EMPTY"
    NO_CONTENT = "NO_CONTENT"
    UNRESOLVED_REFERENCE = "UNRESOLVED_REFERENCE"
    CONFLICTING_DIRECTIVES = "CONFLICTING_DIRECTIVES"


KIND_ORDER = (Kind.ARITHMETIC, Kind.CODE, Kind.REASONING, Kind.FACT, Kind.OTHER)
PLAN_FOR = {
    Kind.ARITHMETIC: (Handler.CALCULATOR, Handler.REASONING),
    Kind.CODE: (Handler.CODE_SANDBOX, Handler.REASONING),
    Kind.REASONING: (Handler.REASONING, Handler.RETRIEVAL),
    Kind.FACT: (Handler.RETRIEVAL,),
    Kind.OTHER: (Handler.RETRIEVAL,),
}
HANDLER_ORDER = (Handler.CALCULATOR, Handler.CODE_SANDBOX, Handler.RETRIEVAL, Handler.REASONING)
TOOL_HANDLERS = {Handler.CALCULATOR: "CALCULATE", Handler.CODE_SANDBOX: "EXECUTE_CODE"}


def _phrases(*items: str) -> tuple[tuple[str, ...], ...]:
    return tuple(tuple(normalize(p).split()) for p in items)


CALC_WORDS = _phrases("احسب", "حساب", "ناتج", "مجموع", "حاصل ضرب", "كم يساوي", "calculate", "compute", "sum of",
                      "product of", "evaluate")
CODE_WORDS = _phrases("كود", "برمجة", "برنامج", "بايثون", "سكربت", "شيفرة", "code", "python", "script", "program",
                      "function", "compile", "debug")
REASON_WORDS = _phrases("لماذا", "كيف", "اشرح", "فسر", "قارن", "برهن", "اثبت", "خطوات", "why", "how", "explain",
                        "compare", "prove", "steps", "reason")
FACT_WORDS = _phrases("من", "ما", "ماذا", "متى", "اين", "كم", "هل", "اي", "اذكر", "who", "what", "when", "where",
                      "which", "how many", "how much", "is", "are", "does", "did", "name")
NOT_REASON = _phrases("how many", "how much")        # "how" inside these is a FACT question
REFERENCE_WORDS = frozenset(normalize("هو هي هم هذا هذه ذلك تلك it this that he she they them").split())
FUNCTION_WORDS = frozenset(normalize(
    "من ما ماذا متى اين كم هل اي في على عن الى الي و او ثم ان كان يكون هو هي هم هذا هذه ذلك تلك ال لا نعم "
    "who what when where which how is are was were be the a an of in on to and or it this that he she they them "
    "do does did can please").split())
WEB_SEARCH = _phrases("ابحث في الانترنت", "ابحث في الويب", "ابحث في جوجل", "search the web", "search online",
                      "google it", "look it up online")

DIRECTIVES = {
    "tools": (_phrases("استخدم الحاسبة", "استخدم الادوات", "use a calculator", "use the calculator", "use tools"),
              _phrases("بدون ادوات", "بلا ادوات", "دون ادوات", "without tools", "no tools", "without a calculator")),
    "length": (_phrases("باختصار", "بايجاز", "بكلمة واحدة", "briefly", "in one word", "short answer"),
               _phrases("بالتفصيل", "بشكل مفصل", "in detail", "detailed", "at length")),
    "sources": (_phrases("مع المصادر", "استشهد", "اذكر المصادر", "cite", "with sources"),
                _phrases("بدون مصادر", "بلا مصادر", "دون مصادر", "without sources", "no sources")),
    "language": (_phrases("بالعربية", "باللغة العربية", "in arabic"),
                 _phrases("بالانجليزية", "باللغة الانجليزية", "in english")),
}

_EXPR = re.compile(r"\d+(?:\.\d+)?\s*[-+*/×÷^%]\s*\(?\s*\d")
_DEF = re.compile(r"\bdef\s+\w+\s*\(|\bfunction\s+\w+\s*\(")
_DIGIT = re.compile(r"\d")
_AR = re.compile(r"[\u0621-\u064A\u0671-\u06D3\u06FA-\u06FF]")   # letters only, not ؟ ، ؛ or digits
_LAT = re.compile(r"[A-Za-z]")


def _find(tokens: list[str], phrases: tuple[tuple[str, ...], ...]) -> list[tuple[int, tuple[str, ...]]]:
    """Phrase positions. A phrase also matches when its first word carries the conjunction ``و`` (``وبالتفصيل``)."""
    out = set()
    for p in phrases:
        for i in range(len(tokens) - len(p) + 1):
            first = tokens[i]
            if tuple(tokens[i + 1:i + len(p)]) == p[1:] and (
                    first == p[0] or (first.startswith("و") and len(first) > 2 and first[1:] == p[0])):
                out.add((i, p))
    return sorted(out)


def language(text: str) -> str:
    a, b = len(_AR.findall(text)), len(_LAT.findall(text))
    if a and b:
        return "mixed"
    return "ar" if a else ("en" if b else "unknown")


@dataclass(frozen=True)
class RouterConfig:
    granted_tools: frozenset = frozenset()      # only "CALCULATE" / "EXECUTE_CODE"
    retrieval_available: bool = False           # a P6-01 index exists for this request
    reasoning_available: bool = False           # P6-03 is not built yet
    has_context: bool = False                   # earlier turns can resolve pronouns

    def __post_init__(self) -> None:
        object.__setattr__(self, "granted_tools", frozenset(self.granted_tools))
        bad = self.granted_tools - set(TOOL_HANDLERS.values())
        if bad:
            raise ValueError(f"tools {sorted(bad)} cannot be granted here (no NETWORK/SEARCH before OD-11)")
        for f in ("retrieval_available", "reasoning_available", "has_context"):
            if not isinstance(getattr(self, f), bool):
                raise ValueError(f"{f} must be a bool")


@dataclass(frozen=True)
class Step:
    rule: str
    detail: str

    def to_list(self) -> list[str]:
        return [self.rule, self.detail]


@dataclass(frozen=True)
class Route:
    kinds: tuple[Kind, ...]
    flags: tuple[Flag, ...]
    directives: tuple[str, ...]                  # e.g. "tools:-", "length:+"
    language: str
    plan: tuple[Handler, ...]                    # remaining handlers, current first; always ends with ABSTAIN
    trace: tuple[Step, ...] = field(default=())

    @property
    def current(self) -> Handler:
        return self.plan[0]

    @property
    def ambiguous(self) -> bool:
        return bool(self.flags)

    def escalate(self, failed: Handler, reason: str) -> Route:
        if failed is not self.current:
            raise ValueError(f"cannot escalate from {failed.value}: the current handler is {self.current.value}")
        if failed is Handler.ABSTAIN:
            raise ValueError("ABSTAIN is final")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("an escalation needs a reason")
        nxt = self.plan[1:]
        return replace(self, plan=nxt, trace=self.trace + (Step("E1", f"{failed.value} -> {nxt[0].value}: {reason}"),))

    def to_dict(self) -> dict:
        return {"kinds": [k.value for k in self.kinds], "flags": [f.value for f in self.flags],
                "directives": list(self.directives), "language": self.language,
                "plan": [h.value for h in self.plan], "trace": [s.to_list() for s in self.trace]}


def route(query: str, config: RouterConfig | None = None) -> Route:
    if not isinstance(query, str):
        raise ValueError("query must be a string")
    cfg = config or RouterConfig()
    trace: list[Step] = []
    raw = normalize_digits(query)
    tokens = normalize(query).split()
    lang = language(query)

    # ---- directives and contradictions --------------------------------------------------------------------------
    directives, flags = [], []
    for name in sorted(DIRECTIVES):
        pos, neg = (bool(_find(tokens, side)) for side in DIRECTIVES[name])
        if pos:
            directives.append(f"{name}:+")
        if neg:
            directives.append(f"{name}:-")
        if pos and neg:
            flags.append(Flag.CONFLICTING_DIRECTIVES)
            trace.append(Step("A4", f"conflicting directives on {name}"))
    if _find(tokens, WEB_SEARCH):
        directives.append("web_search:requested")
        trace.append(Step("W1", "web search requested; no search handler exists (P6-02a BLOCKED, OD-11)"))

    # ---- ambiguity -----------------------------------------------------------------------------------------------
    if not tokens:
        flags.append(Flag.EMPTY)
        trace.append(Step("A1", "no words"))
    elif all(t in FUNCTION_WORDS for t in tokens):          # a number is never a function word
        flags.append(Flag.NO_CONTENT)
        trace.append(Step("A2", "only function words"))
    elif not cfg.has_context:
        for i, t in enumerate(tokens):
            if t in REFERENCE_WORDS and all(x in FUNCTION_WORDS for x in tokens[i + 1:]):
                flags.append(Flag.UNRESOLVED_REFERENCE)
                trace.append(Step("A3", f"reference {t!r} with nothing it can refer to"))
                break

    # ---- classification ------------------------------------------------------------------------------------------
    kinds = []
    if _EXPR.search(raw) or (_find(tokens, CALC_WORDS) and _DIGIT.search(raw)):
        kinds.append(Kind.ARITHMETIC)
        trace.append(Step("K1", "arithmetic expression or calculation verb with a number"))
    if "```" in query or _DEF.search(raw) or _find(tokens, CODE_WORDS):
        kinds.append(Kind.CODE)
        trace.append(Step("K2", "code fence, definition or programming word"))
    blocked = {i + j for i, p in _find(tokens, NOT_REASON) for j in range(len(p))}
    if any(i not in blocked for i, _ in _find(tokens, REASON_WORDS)):
        kinds.append(Kind.REASONING)
        trace.append(Step("K3", "reasoning word"))
    if not kinds and _find(tokens, FACT_WORDS):
        kinds.append(Kind.FACT)
        trace.append(Step("K4", "question word"))
    if not kinds:
        kinds.append(Kind.OTHER)
        trace.append(Step("K5", "no rule matched"))

    # ---- plan ----------------------------------------------------------------------------------------------------
    if flags:
        plan = (Handler.ASK_CLARIFICATION, Handler.ABSTAIN)
        trace.append(Step("P0", "ambiguous: ask for clarification first"))
    else:
        needed = {h for k in kinds for h in PLAN_FOR[k]}
        wanted = [h for h in HANDLER_ORDER if h in needed]
        plan_l = []
        for h in wanted:
            why = None
            if h in TOOL_HANDLERS and "tools:-" in directives:
                why = "the query asks for no tools"
            elif h in TOOL_HANDLERS and TOOL_HANDLERS[h] not in cfg.granted_tools:
                why = f"tool {TOOL_HANDLERS[h]} not granted"
            elif h is Handler.RETRIEVAL and not cfg.retrieval_available:
                why = "no retrieval index"
            elif h is Handler.REASONING and not cfg.reasoning_available:
                why = "reasoning (P6-03) not available"
            if why:
                trace.append(Step("P1", f"skip {h.value}: {why}"))
            else:
                plan_l.append(h)
        plan = tuple(plan_l) + (Handler.ABSTAIN,)
        trace.append(Step("P2", "plan " + " > ".join(h.value for h in plan)))
    return Route(tuple(k for k in KIND_ORDER if k in kinds), tuple(dict.fromkeys(flags)), tuple(directives), lang,
                 plan, tuple(trace))


def abstention_context(r: Route, *, tool_calls_left: int = 0, mode=None, claim_kinds=None):
    """A P6-05 :class:`~nawa.abstention.decision.Context` consistent with the route. Tools are granted only when they
    are in the plan. Search is never allowed (OD-11)."""
    from nawa.abstention.decision import Context, Mode
    tools = frozenset(TOOL_HANDLERS[h] for h in r.plan if h in TOOL_HANDLERS)
    return Context(mode=mode or Mode.STRICT, ambiguous=r.ambiguous, search_allowed=False, searches_left=0,
                   granted_tools=tools, tool_calls_left=tool_calls_left, claim_kinds=dict(claim_kinds or {}))
