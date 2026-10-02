"""Candidate generator interface and deterministic stub generators (ROADMAP P6-03, ADR-0008 D2).

A generator turns a prompt into ``n`` candidate answers. P6-03 declares the interface and tests it **only with stubs**.
A real NAWA generator is P6-03a (BLOCKED until G5), and no external model may be used at all (OD-10). So
:func:`generate_candidates` refuses any generator that is not a stub unless ``allow_model=True``; that switch exists
for P6-03a and is never set in this task.

Stubs (all deterministic, no randomness beyond the given seed):

* :class:`OracleStub`: the gold answer from a table, or the abstention text for an unknown prompt.
* :class:`WrongStub`: a deliberately wrong answer from a table (a negative control: agreement is not truth).
* :class:`ScriptedStub`: answers from a fixed list, rotated by the seed (to build split votes and ties).
* :class:`FailingStub`: always raises (to prove a generator failure is recorded, not hidden).

Results with stubs show that the machinery is correct. They never show that NAWA answers better (ADR-0008 D4).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from nawa.abstention.decision import abstention_text
from nawa.reasoning.budget import Resource
from nawa.reasoning.state import State, StateClosed

MAX_CANDIDATE_CHARS = 4000


class GeneratorError(Exception):
    pass


@runtime_checkable
class Generator(Protocol):
    name: str
    is_stub: bool

    def generate(self, prompt: str, n: int, seed: int) -> list[str]: ...


@dataclass(frozen=True)
class Candidate:
    index: int
    text: str
    generator: str
    stub: bool

    def to_dict(self) -> dict:
        return {"index": self.index, "text": self.text, "generator": self.generator, "stub": self.stub}


@dataclass(frozen=True)
class OracleStub:
    table: Mapping[str, str]
    name: str = "oracle-stub"
    is_stub: bool = True

    def generate(self, prompt: str, n: int, seed: int) -> list[str]:
        return [self.table.get(prompt, abstention_text("ar"))] * n


@dataclass(frozen=True)
class WrongStub:
    table: Mapping[str, str]        # prompt -> a deliberately wrong answer
    name: str = "wrong-stub"
    is_stub: bool = True

    def generate(self, prompt: str, n: int, seed: int) -> list[str]:
        if prompt not in self.table:
            raise GeneratorError(f"no wrong answer scripted for {prompt!r}")
        return [self.table[prompt]] * n


@dataclass(frozen=True)
class ScriptedStub:
    answers: Sequence[str]
    name: str = "scripted-stub"
    is_stub: bool = True

    def generate(self, prompt: str, n: int, seed: int) -> list[str]:
        k = len(self.answers)
        if k == 0:
            raise GeneratorError("no scripted answers")
        return [self.answers[(seed + i) % k] for i in range(n)]


@dataclass(frozen=True)
class FailingStub:
    name: str = "failing-stub"
    is_stub: bool = True

    def generate(self, prompt: str, n: int, seed: int) -> list[str]:
        raise GeneratorError("this stub always fails")


def generate_candidates(generator: object, prompt: str, n: int, *, seed: int, state: State, ref: str = "",
                        allow_model: bool = False) -> tuple[Candidate, ...]:
    """Ask ``generator`` for ``n`` candidates, charging ``n`` CANDIDATES and recording one ``generate`` step.

    Returns the candidates, or ``()`` when the generator failed, returned a malformed result, or the budget ran out.
    Every one of those cases is recorded in ``state`` with its reason; none is hidden.
    """
    if not isinstance(generator, Generator):
        raise ValueError("generator must implement the Generator interface (name, is_stub, generate)")
    if not isinstance(prompt, str):
        raise ValueError("prompt must be a string")
    if isinstance(n, bool) or not isinstance(n, int) or n < 1:
        raise ValueError("n must be a positive int")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("seed must be an int")
    if not generator.is_stub and not allow_model:
        raise ValueError("only stub generators before G5: model generation is P6-03a (BLOCKED); external models "
                         "need OD-10")
    if state.closed:
        raise StateClosed(f"run {state.run_id!r} stopped: {state.stop_reason}")
    for res, need in ((Resource.STEPS, 1), (Resource.CANDIDATES, n)):     # check before calling the generator
        if state.budget.remaining(state.spend, res) < need:
            state.stop(f"budget_exhausted:{res.value}", payload={"refused_kind": "generate", "refused_ref": ref,
                                                                 "requested": {"CANDIDATES": n, "STEPS": 1}})
            return ()
    base = {"generator": generator.name, "stub": bool(generator.is_stub), "n": n, "seed": seed, "prompt": prompt}
    try:
        out = generator.generate(prompt, n, seed)
    except Exception as e:      # a generator failure is a recorded outcome, never a crash or a silent skip
        state.record("generate", ref=ref, outcome="error", reason=f"generator_error:{type(e).__name__}",
                     payload=base, cost={Resource.CANDIDATES: n})
        return ()
    if not isinstance(out, list) or len(out) != n or any(not isinstance(t, str) for t in out):
        state.record("generate", ref=ref, outcome="error", reason="malformed_output", payload=base,
                     cost={Resource.CANDIDATES: n})
        return ()
    if any(len(t) > MAX_CANDIDATE_CHARS for t in out):
        state.record("generate", ref=ref, outcome="error", reason="candidate_too_long", payload=base,
                     cost={Resource.CANDIDATES: n})
        return ()
    rec = state.record("generate", ref=ref, payload={**base, "candidates": list(out)}, cost={Resource.CANDIDATES: n})
    if rec.kind == "stop":
        return ()
    return tuple(Candidate(i, t, generator.name, bool(generator.is_stub)) for i, t in enumerate(out))
