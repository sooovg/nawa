"""Expert specification schema (ROADMAP P7-02; code-only scope, ADR-0009).

Each expert has a goal, a data contract, test cases, limits, and a routing decision. The schema is frozen
and serializable. All data is synthetic: source refs start with ``synthetic:``, no real URLs, no HF repo
refs, no model IDs, no external APIs. Every stub is deterministic — same input produces the same output,
with no time, random, or network calls.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from nawa.routing.router import Handler, Kind


class ExpertDomain(str, Enum):
    """The seven expert domains from P7-01."""
    ARABIC = "arabic"
    PROGRAMMING = "programming"
    MATH = "math"
    DOCUMENTS = "documents"
    SEARCH = "search"
    PLANNING = "planning"
    SAFETY = "safety"


class FailureMode(str, Enum):
    """What an expert does when it cannot produce a confident answer."""
    ABORT = "abort"          # stop the pipeline; do not guess
    FALLBACK = "fallback"    # hand back to the core model or the next handler
    DELEGATE = "delegate"     # hand to another expert in the same plan


class DataPolicy(str, Enum):
    """Allowed data sources for an expert. Synthetic only (ADR-0009)."""
    SYNTHETIC_ONLY = "synthetic_only"


_SYNTHETIC_REF = re.compile(r"^synthetic:[a-z0-9_\-./#]+$")


@dataclass(frozen=True)
class DataContract:
    """What data an expert may consume and produce.

    ``allowed_sources`` is a tuple of source refs. Each must start with ``synthetic:``. No real URLs, no HF
    repo refs, no model IDs. ``input_fields`` and ``output_fields`` are simple field-name tuples, not JSON
    Schema — keeping the contract light and inspectable.
    """
    policy: DataPolicy = DataPolicy.SYNTHETIC_ONLY
    allowed_sources: tuple[str, ...] = ()
    input_fields: tuple[str, ...] = ()
    output_fields: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for s in self.allowed_sources:
            if not _SYNTHETIC_REF.match(s):
                raise ValueError(
                    f"data source {s!r} must match synthetic:<id> (ADR-0009: synthetic only; "
                    f"no real URLs, no HF repo refs, no model IDs)")
        if self.policy is not DataPolicy.SYNTHETIC_ONLY:
            raise ValueError(f"data policy must be SYNTHETIC_ONLY (ADR-0009); got {self.policy!r}")


@dataclass(frozen=True)
class ExpertLimits:
    """Hard limits on an expert's execution. Enforced by the caller, not by this module."""
    max_input_tokens: int = 512
    max_output_tokens: int = 256
    max_calls_per_turn: int = 1
    timeout_ticks: int = 10          # logical-clock ticks; 0 means no timeout
    max_retries: int = 0

    def __post_init__(self) -> None:
        for name in ("max_input_tokens", "max_output_tokens", "max_calls_per_turn"):
            v = getattr(self, name)
            if not isinstance(v, int) or v <= 0:
                raise ValueError(f"{name} must be a positive integer; got {v!r}")
        if self.timeout_ticks < 0:
            raise ValueError(f"timeout_ticks must be >= 0; got {self.timeout_ticks}")
        if self.max_retries < 0:
            raise ValueError(f"max_retries must be >= 0; got {self.max_retries}")


@dataclass(frozen=True)
class ExpertTestCase:
    """One synthetic test case for an expert.

    ``input`` and ``expected_output`` are synthetic strings. ``source`` must start with ``synthetic:``.
    These are not training data — they are correctness checks for the stub.
    """
    name: str
    input: str
    expected_output: str
    source: str = "synthetic:test"

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("test case name must not be empty")
        if not self.input:
            raise ValueError(f"test case {self.name!r}: input must not be empty")
        if not self.expected_output:
            raise ValueError(f"test case {self.name!r}: expected_output must not be empty")
        if not _SYNTHETIC_REF.match(self.source):
            raise ValueError(
                f"test case {self.name!r}: source {self.source!r} must match synthetic:<id> (ADR-0009)")


@dataclass(frozen=True)
class ExpertSpec:
    """A complete expert specification: goal, data, tests, limits, routing decision.

    Frozen and serializable. The ``routing_kinds`` and ``routing_handler`` fields express the expert's
    routing decision in terms of the existing ``nawa.routing`` types (P6-06) — they are data for P7-03's
    router to consume, not a second router.
    """
    expert_id: str
    domain: ExpertDomain
    goal: str
    data_contract: DataContract
    test_cases: tuple[ExpertTestCase, ...]
    limits: ExpertLimits
    routing_kinds: tuple[Kind, ...]          # query kinds this expert can serve
    routing_handler: Handler                  # the handler it acts as
    routing_priority: int = 0                 # lower = higher priority; ties broken by expert_id
    failure_mode: FailureMode = FailureMode.FALLBACK
    stub_response: str = ""                   # deterministic stub output; no model

    def __post_init__(self) -> None:
        if not self.expert_id:
            raise ValueError("expert_id must not be empty")
        if not self.goal:
            raise ValueError(f"expert {self.expert_id!r}: goal must not be empty")
        if not self.test_cases:
            raise ValueError(f"expert {self.expert_id!r}: must have at least one test case")
        if not self.routing_kinds:
            raise ValueError(f"expert {self.expert_id!r}: must declare at least one routing kind")
        if not self.stub_response:
            raise ValueError(
                f"expert {self.expert_id!r}: stub_response must not be empty (deterministic stub, ADR-0009)")

    def to_dict(self) -> dict[str, Any]:
        return {
            "expert_id": self.expert_id,
            "domain": self.domain.value,
            "goal": self.goal,
            "data_contract": {
                "policy": self.data_contract.policy.value,
                "allowed_sources": list(self.data_contract.allowed_sources),
                "input_fields": list(self.data_contract.input_fields),
                "output_fields": list(self.data_contract.output_fields),
            },
            "test_cases": [
                {"name": tc.name, "input": tc.input, "expected_output": tc.expected_output, "source": tc.source}
                for tc in self.test_cases
            ],
            "limits": {
                "max_input_tokens": self.limits.max_input_tokens,
                "max_output_tokens": self.limits.max_output_tokens,
                "max_calls_per_turn": self.limits.max_calls_per_turn,
                "timeout_ticks": self.limits.timeout_ticks,
                "max_retries": self.limits.max_retries,
            },
            "routing_kinds": [k.value for k in self.routing_kinds],
            "routing_handler": self.routing_handler.value,
            "routing_priority": self.routing_priority,
            "failure_mode": self.failure_mode.value,
            "stub_response": self.stub_response,
        }


# ---------------------------------------------------------------------------
# The seven experts (P7-01 domains). All synthetic, all deterministic.
# ---------------------------------------------------------------------------

_EXPERT_ARABIC = ExpertSpec(
    expert_id="expert.arabic",
    domain=ExpertDomain.ARABIC,
    goal="معالجة النص العربي: تحليل، إعراب، وتصحيح إملائي على بيانات اصطناعية فقط",
    data_contract=DataContract(
        allowed_sources=("synthetic:arabic/corpus/1",),
        input_fields=("text",),
        output_fields=("analysis", "corrections"),
    ),
    test_cases=(
        ExpertTestCase("ar_diacritics", "كتب", "كَتَبَ", "synthetic:arabic/test/diacritics"),
        ExpertTestCase("ar_spelling", "الرمز", "الرّمز", "synthetic:arabic/test/spelling"),
    ),
    limits=ExpertLimits(max_input_tokens=256, max_output_tokens=128),
    routing_kinds=(Kind.FACT, Kind.OTHER),
    routing_handler=Handler.REASONING,
    routing_priority=10,
    failure_mode=FailureMode.FALLBACK,
    stub_response="[stub:arabic] تحليل اصطناعي للنص العربي",
)

_EXPERT_PROGRAMMING = ExpertSpec(
    expert_id="expert.programming",
    domain=ExpertDomain.PROGRAMMING,
    goal="كتابة ومراجعة الشيفرة البرمجية على مهام اصطناعية فقط",
    data_contract=DataContract(
        allowed_sources=("synthetic:code/snippets/1",),
        input_fields=("prompt", "language"),
        output_fields=("code", "review"),
    ),
    test_cases=(
        ExpertTestCase("py_hello", "اكتب دالة ترحب", "def greet(): return 'مرحبا'", "synthetic:code/test/hello"),
        ExpertTestCase("py_factorial", "دالة مضروب", "def factorial(n): return 1 if n <= 1 else n * factorial(n-1)",
                       "synthetic:code/test/factorial"),
    ),
    limits=ExpertLimits(max_input_tokens=512, max_output_tokens=256, timeout_ticks=20),
    routing_kinds=(Kind.CODE,),
    routing_handler=Handler.CODE_SANDBOX,
    routing_priority=5,
    failure_mode=FailureMode.ABORT,
    stub_response="[stub:programming] شيفرة اصطناعية للمراجعة",
)

_EXPERT_MATH = ExpertSpec(
    expert_id="expert.math",
    domain=ExpertDomain.MATH,
    goal="حل المسائل الرياضية وتحقق النتائج على أرقام اصطناعية فقط",
    data_contract=DataContract(
        allowed_sources=("synthetic:math/problems/1",),
        input_fields=("expression",),
        output_fields=("result", "steps"),
    ),
    test_cases=(
        ExpertTestCase("add", "2 + 3", "5", "synthetic:math/test/add"),
        ExpertTestCase("multiply", "4 × 6", "24", "synthetic:math/test/multiply"),
    ),
    limits=ExpertLimits(max_input_tokens=128, max_output_tokens=64),
    routing_kinds=(Kind.ARITHMETIC,),
    routing_handler=Handler.CALCULATOR,
    routing_priority=5,
    failure_mode=FailureMode.ABORT,
    stub_response="[stub:math] ناتج اصطناعي محسوب",
)

_EXPERT_DOCUMENTS = ExpertSpec(
    expert_id="expert.documents",
    domain=ExpertDomain.DOCUMENTS,
    goal="معالجة الوثائق واستخراج النص على وثائق اصطناعية فقط",
    data_contract=DataContract(
        allowed_sources=("synthetic:docs/samples/1",),
        input_fields=("document_ref",),
        output_fields=("extracted_text", "metadata"),
    ),
    test_cases=(
        ExpertTestCase("extract_para", "synthetic:docs/sample/1", "فقرة اصطناعية مستخرجة", "synthetic:docs/test/extract"),
    ),
    limits=ExpertLimits(max_input_tokens=512, max_output_tokens=256),
    routing_kinds=(Kind.FACT,),
    routing_handler=Handler.RETRIEVAL,
    routing_priority=15,
    failure_mode=FailureMode.FALLBACK,
    stub_response="[stub:documents] نص اصطناعي مستخرج من وثيقة",
)

_EXPERT_SEARCH = ExpertSpec(
    expert_id="expert.search",
    domain=ExpertDomain.SEARCH,
    goal="البحث في فهرس اصطناعي محلي فقط؛ لا بحث في الويب (OD-11)",
    data_contract=DataContract(
        allowed_sources=("synthetic:search/index/1",),
        input_fields=("query",),
        output_fields=("results", "snippets"),
    ),
    test_cases=(
        ExpertTestCase("local_search", "بسيط", "نتيجة اصطناعية محلية", "synthetic:search/test/local"),
    ),
    limits=ExpertLimits(max_input_tokens=128, max_output_tokens=128),
    routing_kinds=(Kind.FACT, Kind.OTHER),
    routing_handler=Handler.RETRIEVAL,
    routing_priority=20,
    failure_mode=FailureMode.FALLBACK,
    stub_response="[stub:search] نتائج اصطناعية محلية",
)

_EXPERT_PLANNING = ExpertSpec(
    expert_id="expert.planning",
    domain=ExpertDomain.PLANNING,
    goal="تخطيط المهام وتفكيكها على سيناريوهات اصطناعية فقط",
    data_contract=DataContract(
        allowed_sources=("synthetic:planning/scenarios/1",),
        input_fields=("task",),
        output_fields=("plan", "steps"),
    ),
    test_cases=(
        ExpertTestCase("simple_plan", "خطط لزيارة", "1. حدد الموعد 2. جهّز القائمة 3. انطلق",
                       "synthetic:planning/test/simple"),
    ),
    limits=ExpertLimits(max_input_tokens=256, max_output_tokens=256),
    routing_kinds=(Kind.REASONING,),
    routing_handler=Handler.REASONING,
    routing_priority=15,
    failure_mode=FailureMode.DELEGATE,
    stub_response="[stub:planning] خطة اصطناعية للمهمة",
)

_EXPERT_SAFETY = ExpertSpec(
    expert_id="expert.safety",
    domain=ExpertDomain.SAFETY,
    goal="فحص السلامة والحدود على مدخلات اصطناعية فقط؛ ليس قرارًا طبيًا أو قانونيًا",
    data_contract=DataContract(
        allowed_sources=("synthetic:safety/rules/1",),
        input_fields=("content",),
        output_fields=("safe", "reason"),
    ),
    test_cases=(
        ExpertTestCase("safe_content", "نص آمن", "safe: true", "synthetic:safety/test/safe"),
        ExpertTestCase("unsafe_content", "تخلّص من", "safe: false", "synthetic:safety/test/unsafe"),
    ),
    limits=ExpertLimits(max_input_tokens=128, max_output_tokens=64, max_calls_per_turn=1),
    routing_kinds=(Kind.CODE, Kind.REASONING, Kind.FACT, Kind.OTHER),
    routing_handler=Handler.ABSTAIN,
    routing_priority=1,
    failure_mode=FailureMode.ABORT,
    stub_response="[stub:safety] فحص سلامة اصطناعي",
)


EXPERT_SPECS: tuple[ExpertSpec, ...] = (
    _EXPERT_ARABIC,
    _EXPERT_PROGRAMMING,
    _EXPERT_MATH,
    _EXPERT_DOCUMENTS,
    _EXPERT_SEARCH,
    _EXPERT_PLANNING,
    _EXPERT_SAFETY,
)


def get_expert_spec(expert_id: str) -> ExpertSpec:
    """Return the spec for ``expert_id`` or raise KeyError."""
    for spec in EXPERT_SPECS:
        if spec.expert_id == expert_id:
            return spec
    raise KeyError(f"unknown expert: {expert_id!r}")


def validate_expert_specs() -> list[str]:
    """Validate the expert specs and return a list of problems (empty = all valid).

    Checks:
    1. Every P7-01 domain has exactly one expert.
    2. No duplicate expert IDs.
    3. Routing priority ties are broken deterministically by expert_id.
    4. No real data refs (enforced by DataContract/ExpertTestCase __post_init__, but checked again here).
    """
    problems: list[str] = []
    # 1. Domain coverage
    domains = [s.domain for s in EXPERT_SPECS]
    missing = set(ExpertDomain) - set(domains)
    if missing:
        problems.append(f"missing domains: {sorted(d.value for d in missing)}")
    # 2. Duplicate IDs
    ids = [s.expert_id for s in EXPERT_SPECS]
    seen: set[str] = set()
    for eid in ids:
        if eid in seen:
            problems.append(f"duplicate expert_id: {eid!r}")
        seen.add(eid)
    # 3. Priority ties: same (kind, handler) pair with equal priority must be deterministically orderable
    kind_handler_priority: dict[tuple, list[str]] = {}
    for s in EXPERT_SPECS:
        for k in s.routing_kinds:
            key = (k, s.routing_handler)
            kind_handler_priority.setdefault(key, []).append(s.expert_id)
    for key, experts in kind_handler_priority.items():
        if len(experts) > 1:
            # check if priorities differ
            prios = [get_expert_spec(e).routing_priority for e in experts]
            if len(set(prios)) == 1:
                problems.append(
                    f"routing kind/handler {key} has {len(experts)} experts with identical priority "
                    f"{prios[0]}; tie-break is expert_id (deterministic), but consider distinct priorities")
    # 4. Synthetic refs (redundant with __post_init__, but explicit)
    for s in EXPERT_SPECS:
        for src in s.data_contract.allowed_sources:
            if not _SYNTHETIC_REF.match(src):
                problems.append(f"expert {s.expert_id!r}: non-synthetic data source {src!r}")
        for tc in s.test_cases:
            if not _SYNTHETIC_REF.match(tc.source):
                problems.append(f"expert {s.expert_id!r}: test case {tc.name!r} has non-synthetic source {tc.source!r}")
    return problems
