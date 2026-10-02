"""Reasoning state: an append-only, hash-chained record of one run (ROADMAP P6-03, ADR-0008).

Every step a run takes (plan, tool call, candidate generation, verification, decision) is recorded as a
:class:`StepRecord` with its cost. Rules:

* **Budget first.** :meth:`State.record` charges the step's cost (plus one ``STEPS``) before appending. If the charge
  does not fit, the state records one final ``stop`` step with reason ``budget_exhausted:<RESOURCE>`` (that step costs
  nothing) and closes. A refused step is never dropped silently, and nothing is recorded after a stop.
* **Append-only, hash-chained.** Each record holds the hash of the previous one; the hash covers every field in
  canonical JSON. :meth:`State.verify` and :meth:`State.from_json` recompute the chain, so editing, inserting, removing
  or reordering a record is detected.
* **Deterministic.** No clock, no randomness, no process ids: the same calls give byte-identical JSON. So a trace can be
  replayed and compared exactly (the P6-07 replay check builds on this).
* **JSON only.** Payloads must be JSON values (``dict``, ``list``, ``str``, ``int``, ``bool``, ``None``). Floats are
  refused, so no value is rounded on the way to the log; use exact strings such as ``"1/3"``.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass

from nawa.reasoning.budget import Budget, BudgetExhausted, Resource, Spend

STEP_KINDS = ("plan", "decompose", "tool", "generate", "consistency", "verify", "decide", "note", "stop")
OUTCOMES = ("ok", "error", "denied", "timeout", "refused")
GENESIS = "0" * 64


def _json_value(value: object, where: str) -> None:
    if value is None or isinstance(value, (bool, str)):
        return
    if isinstance(value, int):
        return
    if isinstance(value, float):
        raise ValueError(f"{where}: float values are refused; pass an exact string")
    if isinstance(value, (list, tuple)):
        for i, v in enumerate(value):
            _json_value(v, f"{where}[{i}]")
        return
    if isinstance(value, dict):
        for k, v in value.items():
            if not isinstance(k, str):
                raise ValueError(f"{where}: keys must be strings")
            _json_value(v, f"{where}.{k}")
        return
    raise ValueError(f"{where}: {type(value).__name__} is not a JSON value")


def canonical(obj: object) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True)
class StepRecord:
    seq: int
    kind: str
    ref: str                 # plan step id, subtask id or "" for run-level steps
    outcome: str
    reason: str
    payload: object
    cost: dict               # Resource.value -> int, as charged
    spend_after: dict        # Resource.value -> int
    prev_hash: str
    hash: str

    def body(self) -> dict:
        return {"seq": self.seq, "kind": self.kind, "ref": self.ref, "outcome": self.outcome, "reason": self.reason,
                "payload": self.payload, "cost": self.cost, "spend_after": self.spend_after,
                "prev_hash": self.prev_hash}

    def to_dict(self) -> dict:
        return {**self.body(), "hash": self.hash}


def _hash(body: dict) -> str:
    return hashlib.sha256(canonical(body).encode("utf-8")).hexdigest()


class StateClosed(Exception):
    """The run has stopped (budget exhausted or explicit stop); nothing more can be recorded."""


class State:
    def __init__(self, budget: Budget, run_id: str = "run") -> None:
        if not isinstance(budget, Budget):
            raise ValueError("budget must be a Budget")
        if not isinstance(run_id, str) or not run_id.strip():
            raise ValueError("run_id must be a non-empty string")
        self.budget = budget
        self.run_id = run_id
        self.spend = Spend()
        self.records: list[StepRecord] = []
        self.closed = False
        self.stop_reason: str | None = None

    @property
    def head(self) -> str:
        return self.records[-1].hash if self.records else GENESIS

    def _append(self, kind: str, ref: str, outcome: str, reason: str, payload: object,
                cost: dict[Resource, int]) -> StepRecord:
        body = {"seq": len(self.records) + 1, "kind": kind, "ref": ref, "outcome": outcome, "reason": reason,
                "payload": payload, "cost": {r.value: cost.get(r, 0) for r in Resource},
                "spend_after": self.spend.to_dict(), "prev_hash": self.head}
        rec = StepRecord(**body, hash=_hash(body))
        self.records.append(rec)
        return rec

    def record(self, kind: str, *, ref: str = "", outcome: str = "ok", reason: str = "", payload: object = None,
               cost: Mapping[Resource, int] | None = None) -> StepRecord:
        """Charge ``cost`` + 1 STEP, then append. On exhaustion: append a free ``stop`` record, close, and return it."""
        if self.closed:
            raise StateClosed(f"run {self.run_id!r} stopped: {self.stop_reason}")
        if kind not in STEP_KINDS or kind == "stop":
            raise ValueError(f"kind must be one of {[k for k in STEP_KINDS if k != 'stop']}")
        if outcome not in OUTCOMES:
            raise ValueError(f"outcome must be one of {OUTCOMES}")
        if not isinstance(ref, str) or not isinstance(reason, str):
            raise ValueError("ref and reason must be strings")
        _json_value(payload, "payload")
        c = dict(cost or {})
        c[Resource.STEPS] = c.get(Resource.STEPS, 0) + 1
        try:
            self.spend = self.budget.charge(self.spend, c)
        except BudgetExhausted as e:
            return self.stop(e.reason, payload={"refused_kind": kind, "refused_ref": ref,
                                                "requested": {r.value: n for r, n in sorted(c.items())}})
        return self._append(kind, ref, outcome, reason, payload, c)

    def stop(self, reason: str, payload: object = None) -> StepRecord:
        """Close the run with a free ``stop`` record (it is recorded even when the step budget is used up)."""
        if self.closed:
            raise StateClosed(f"run {self.run_id!r} stopped: {self.stop_reason}")
        if not isinstance(reason, str) or not reason:
            raise ValueError("stop needs a reason")
        _json_value(payload, "payload")
        rec = self._append("stop", "", "refused" if reason.startswith("budget_exhausted") else "ok", reason, payload, {})
        self.closed = True
        self.stop_reason = reason
        return rec

    # ---- integrity ---------------------------------------------------------------------------------------------
    def to_dict(self) -> dict:
        return {"run_id": self.run_id, "budget": self.budget.to_dict(), "records": [r.to_dict() for r in self.records],
                "closed": self.closed, "stop_reason": self.stop_reason, "head": self.head}

    def to_json(self) -> str:
        return canonical(self.to_dict())

    def verify(self) -> list[str]:
        return verify_records(self.budget, [r.to_dict() for r in self.records])

    @classmethod
    def from_json(cls, text: str) -> State:
        d = json.loads(text)
        budget = Budget.from_dict(d["budget"])
        problems = verify_records(budget, d["records"])
        if d.get("head") != (d["records"][-1]["hash"] if d["records"] else GENESIS):
            problems.append("head does not match the last record")
        stops = [i for i, r in enumerate(d["records"]) if r["kind"] == "stop"]
        if stops and stops != [len(d["records"]) - 1]:
            problems.append("a stop record must be the last record")
        if bool(stops) != bool(d.get("closed")) or (stops and d["records"][-1]["reason"] != d.get("stop_reason")):
            problems.append("closed/stop_reason do not match the records")
        if problems:
            raise ValueError("state does not verify: " + "; ".join(problems))
        s = cls(budget, d["run_id"])
        for r in d["records"]:
            s.records.append(StepRecord(**r))
        s.spend = Spend(**{k.lower(): v for k, v in (d["records"][-1]["spend_after"] if d["records"] else {}).items()})
        s.closed = bool(d["closed"])
        s.stop_reason = d["stop_reason"]
        return s


def verify_records(budget: Budget, records: list[dict]) -> list[str]:
    """Recompute the chain and the spend; return every problem found (empty list = valid)."""
    problems = []
    prev = GENESIS
    spend = {r.value: 0 for r in Resource}
    for i, r in enumerate(records):
        body = {k: r.get(k) for k in ("seq", "kind", "ref", "outcome", "reason", "payload", "cost", "spend_after",
                                       "prev_hash")}
        if set(r) != set(body) | {"hash"}:
            problems.append(f"record {i + 1}: unexpected fields")
        if r.get("seq") != i + 1:
            problems.append(f"record {i + 1}: seq {r.get('seq')!r}")
        if r.get("prev_hash") != prev:
            problems.append(f"record {i + 1}: broken chain")
        if _hash(body) != r.get("hash"):
            problems.append(f"record {i + 1}: hash mismatch")
        if r.get("kind") not in STEP_KINDS or r.get("outcome") not in OUTCOMES:
            problems.append(f"record {i + 1}: bad kind/outcome")
        cost = r.get("cost") or {}
        for k in spend:
            spend[k] += cost.get(k, 0) if isinstance(cost.get(k, 0), int) else 0
        if r.get("spend_after") != spend:
            problems.append(f"record {i + 1}: spend does not add up")
        if any(spend[res.value] > budget.limit(res) for res in Resource):
            problems.append(f"record {i + 1}: spend exceeds the budget")
        prev = r.get("hash")
    return problems
