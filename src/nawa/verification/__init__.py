"""NAWA verification (ROADMAP P6-04, P6-08; code-only scope, ADR-0008).

P6-08: the five states and their rules (:mod:`.states`). P6-04: claims, provided evidence, independent deterministic
checkers, contradiction, consensus and uncertainty (:mod:`.claims`, :mod:`.evidence`, :mod:`.checkers`,
:mod:`.consistency`, :mod:`.verifier`). No external model, no network, no real data.
"""

from nawa.verification.checkers import (CalculatorChecker, QuoteChecker, RecordChecker, SandboxChecker,
                                        default_checkers, find_quote)
from nawa.verification.claims import ArithmeticClaim, CodeClaim, FactClaim, TextClaim, extract_claims
from nawa.verification.consistency import (Conflict, Consensus, claim_conflicts, consensus, evidence_conflicts,
                                           uncertainty)
from nawa.verification.evidence import Evidence, FactRecord, evidence_from_files, norm_value
from nawa.verification.states import (AnswerVerdict, ClaimVerdict, Finding, Relation, VerificationState,
                                      answer_state, claim_state, flagged_claims, passes_strict, verify)
from nawa.verification.verifier import Report, check

__all__ = ["AnswerVerdict", "ArithmeticClaim", "CalculatorChecker", "ClaimVerdict", "CodeClaim", "Conflict",
           "Consensus", "Evidence", "FactClaim", "FactRecord", "Finding", "QuoteChecker", "RecordChecker", "Relation",
           "Report", "SandboxChecker", "TextClaim", "VerificationState", "answer_state", "check", "claim_conflicts",
           "claim_state", "consensus", "default_checkers", "evidence_conflicts", "evidence_from_files",
           "extract_claims", "find_quote", "flagged_claims", "norm_value", "passes_strict", "uncertainty", "verify"]
