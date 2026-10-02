"""Independent deterministic checkers (ROADMAP P6-04, ADR-0008).

Each checker:
- handles one claim kind;
- reads only the claim and the evidence it is given;
- keeps no state between calls;
- never sees another checker's findings;
- returns P6-08 :class:`~nawa.verification.states.Finding` objects. The five states are decided by the P6-08 rules,
  never by a checker.

==================  ===============  =====================================================================
checker             claim kind       method
==================  ===============  =====================================================================
``calculator``      ArithmeticClaim  exact rational arithmetic (``nawa.tools.calculator``)
``sandbox``         CodeClaim        execution without network (``nawa.tools.sandbox``); stdout compared
``records``         FactClaim        structured records (subject, attribute) in the provided evidence
``quote``           TextClaim        exact quote (normalised, token boundaries) in the *cited* evidence
==================  ===============  =====================================================================

Outcomes, by checker:

- ``calculator`` and ``sandbox``:
  - match → ``ENTAILS``; mismatch → ``CONTRADICTS``;
  - refusal, error, timeout or sandbox denial → ``UNDECIDED``. A failed tool never becomes support (rule C5).
  - Their ``evidence_id`` names the computation, ``calc:<hash>`` or ``exec:<hash>``. A computation checks the claim
    itself; it adds no outside fact.
- ``records``:
  - an equal value → ``ENTAILS``; a different value → ``CONTRADICTS``;
  - a different unit → ``UNDECIDED`` (no unit conversion);
  - no record about the claim → nothing (rule C1).
  - **Citations limit support, not contradiction:** if the claim cites evidence, only the cited evidence can
    entail it, but every provided record can contradict it. An answer cannot cherry-pick one source and hide a
    conflicting one; the conflict gives rule C3 (``UNCERTAIN``).
- ``quote``:
  - found → ``ENTAILS``;
  - a negation word right before the quote → ``UNDECIDED``;
  - not found → ``NEUTRAL``. Text never *contradicts*: a missing quote is not a refutation;
  - a citation to unknown evidence → ``NEUTRAL`` with ``unknown_citation``;
  - no citation → nothing (rule C1). An uncited sentence is never supported.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from nawa.tools.calculator import CalcError, calculate
from nawa.tools.sandbox import SandboxPolicy, run_code
from nawa.verification.claims import ArithmeticClaim, CodeClaim, FactClaim, TextClaim
from nawa.verification.evidence import Evidence, norm_text, norm_unit, norm_value, sha12
from nawa.verification.states import Finding, Relation

R = Relation
NEGATIONS = frozenset({"لا", "ليس", "ليست", "لم", "لن", "غير", "ما", "ليسوا", "not", "no", "never", "isn't", "isnt",
                       "wasn't", "wasnt", "aren't", "arent", "doesn't", "doesnt", "didn't", "didnt", "nor", "without"})
NEGATION_WINDOW = 3


@dataclass(frozen=True)
class CalculatorChecker:
    name: str = "calculator"
    kind: type = ArithmeticClaim

    def check(self, claim: ArithmeticClaim, evidence: Mapping[str, Evidence]) -> list[Finding]:
        eid = f"calc:{sha12(claim.expression)}"
        try:
            got = calculate(claim.expression).value
        except CalcError as e:
            return [Finding(claim.claim_id, R.UNDECIDED, self.name, None, f"calculator_refused:{e.code}")]
        try:
            want = norm_value(claim.value)
        except ValueError:
            want = None
        if not isinstance(want, type(got)):
            return [Finding(claim.claim_id, R.UNDECIDED, self.name, None, "claimed_value_not_a_number")]
        rel = R.ENTAILS if got == want else R.CONTRADICTS
        return [Finding(claim.claim_id, rel, self.name, eid, f"computed={got}")]


@dataclass(frozen=True)
class SandboxChecker:
    name: str = "sandbox"
    kind: type = CodeClaim
    policy: SandboxPolicy = SandboxPolicy()

    def check(self, claim: CodeClaim, evidence: Mapping[str, Evidence]) -> list[Finding]:
        r = run_code(claim.code, self.policy)
        if not r.ok:
            why = "timeout" if r.timed_out else ("denied:" + ",".join(d.split()[0] for d in r.denied)) if r.denied \
                else f"returncode={r.returncode}"
            return [Finding(claim.claim_id, R.UNDECIDED, self.name, None, f"execution_failed:{why}")]
        if r.truncated:
            return [Finding(claim.claim_id, R.UNDECIDED, self.name, None, "output_truncated")]
        eid = f"exec:{sha12(claim.code)}"
        same = r.stdout.rstrip("\n") == claim.expected_stdout.rstrip("\n")
        return [Finding(claim.claim_id, R.ENTAILS if same else R.CONTRADICTS, self.name, eid,
                        "stdout_matches" if same else "stdout_differs")]


def _scope(citations: tuple[str, ...], evidence: Mapping[str, Evidence], claim_id: str, checker: str):
    """The evidence a claim may use, plus a NEUTRAL finding for each unknown citation."""
    unknown = [Finding(claim_id, R.NEUTRAL, checker, None, f"unknown_citation:{c}")
               for c in citations if c not in evidence]
    ids = [c for c in citations if c in evidence] if citations else sorted(evidence)
    return [evidence[i] for i in ids], unknown


@dataclass(frozen=True)
class RecordChecker:
    name: str = "records"
    kind: type = FactClaim

    def check(self, claim: FactClaim, evidence: Mapping[str, Evidence]) -> list[Finding]:
        scope, out = _scope(claim.citations, evidence, claim.claim_id, self.name)
        in_scope = {e.evidence_id for e in scope}
        key = (norm_text(claim.subject), norm_text(claim.attribute))
        want, unit = norm_value(claim.value), norm_unit(claim.unit)
        for eid in sorted(evidence):
            e = evidence[eid]
            for r in e.records:
                if r.key != key:
                    continue
                if norm_unit(r.unit) != unit:
                    if e.evidence_id not in in_scope:
                        continue
                    out.append(Finding(claim.claim_id, R.UNDECIDED, self.name, e.evidence_id,
                                       f"unit_mismatch:{r.unit}!={claim.unit}"))
                elif norm_value(r.value) == want:
                    if e.evidence_id in in_scope:
                        out.append(Finding(claim.claim_id, R.ENTAILS, self.name, e.evidence_id, "record_equal"))
                else:
                    out.append(Finding(claim.claim_id, R.CONTRADICTS, self.name, e.evidence_id,
                                       f"record_value={r.value}"))
        return out


def _tokens(text: str) -> list[str]:
    return norm_text(text).split()


def find_quote(quote: str, text: str) -> tuple[bool, bool]:
    """(found, negated): an exact token-sequence match after normalisation. ``negated`` is true when *every*
    occurrence has a negation word within ``NEGATION_WINDOW`` tokens before it. A negation inside the quote is part
    of the quote and is matched literally."""
    q, t = _tokens(quote), _tokens(text)
    if not q:
        return False, False
    hits = [i for i in range(len(t) - len(q) + 1) if t[i:i + len(q)] == q]
    if not hits:
        return False, False
    negated = all(any(w in NEGATIONS for w in t[max(0, i - NEGATION_WINDOW):i]) for i in hits)
    return True, negated


@dataclass(frozen=True)
class QuoteChecker:
    name: str = "quote"
    kind: type = TextClaim

    def check(self, claim: TextClaim, evidence: Mapping[str, Evidence]) -> list[Finding]:
        if not claim.citations:
            return []
        scope, out = _scope(claim.citations, evidence, claim.claim_id, self.name)
        for e in scope:
            found, negated = find_quote(claim.text, e.text)
            if found and negated:
                out.append(Finding(claim.claim_id, R.UNDECIDED, self.name, e.evidence_id, "negation_before_quote"))
            elif found:
                out.append(Finding(claim.claim_id, R.ENTAILS, self.name, e.evidence_id, "quote_found"))
            else:
                out.append(Finding(claim.claim_id, R.NEUTRAL, self.name, e.evidence_id, "quote_not_found"))
        return out


def default_checkers(policy: SandboxPolicy | None = None) -> tuple:
    return (CalculatorChecker(), SandboxChecker(policy=policy or SandboxPolicy()), RecordChecker(), QuoteChecker())
