"""Knowledge mutability classification and training-manifest enforcement (ROADMAP P7-06, ADR-0009).

NAWA must distinguish between stable knowledge (suitable for training data manifests) and changing
knowledge (facts that vary over time, like a status, a score, or a current holder of a role). Changing
knowledge is accepted in memory and retrieval — it can be stored, updated, searched and cited — but it
is rejected from any training data manifest, because training on a time-sensitive fact would freeze a
snapshot that is already stale.

This module is the single central enforcement point. It is intentionally simple and explicit:

- ``KnowledgeMutability`` is a three-valued enum: ``STABLE``, ``CHANGING``, ``UNKNOWN``.
- ``mutability_reasons`` inspects a manifest candidate dict and returns reason codes, never raising.
  The manifest gate (``data_verify.train_eligibility``) calls it; tests assert the reason is present.
- Missing mutability on a knowledge record is treated as ``UNKNOWN`` and rejected, so silence is never
  read as "stable".

Code-only scope (ADR-0009): synthetic facts only, no external model, no network, no real data.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import Enum


class KnowledgeMutability(str, Enum):
    """Whether a knowledge record may change over time.

    - ``STABLE``: a durable fact (e.g. a mathematical identity). May enter a training manifest.
    - ``CHANGING``: a time-sensitive fact (e.g. a status, a score, a current holder). May live in
      memory and retrieval, but must never enter a training data manifest.
    - ``UNKNOWN``: mutability was not recorded. Treated as not stable, so it is rejected from
      manifests — silence is never read as "stable".
    """

    STABLE = "stable"
    CHANGING = "changing"
    UNKNOWN = "unknown"


# Reason codes returned by ``mutability_reasons``. Closed vocabulary, never free text.
REASON_CHANGING_IN_MANIFEST = "changing_knowledge_not_train_eligible"
REASON_MUTABILITY_MISSING = "knowledge_mutability_missing"
REASON_MUTABILITY_INVALID = "knowledge_mutability_invalid"
REASON_MUTABILITY_ONLY_FOR_KNOWLEDGE = "mutability_only_for_knowledge"


def _is_knowledge_record(candidate: Mapping[str, object]) -> bool:
    """A record is 'knowledge' if it carries a knowledge kind, a fact_key, or a mutability field."""
    kind = str(candidate.get("kind", "")).lower()
    if kind == "knowledge":
        return True
    if candidate.get("fact_key"):
        return True
    if candidate.get("mutability") is not None:
        return True
    return False


def mutability_reasons(candidate: Mapping[str, object]) -> tuple[str, ...]:
    """Inspect a training-manifest candidate and return reason codes for mutability violations.

    Returns an empty tuple when the candidate is acceptable from a mutability standpoint.
    Non-knowledge records are not flagged here (their eligibility is decided elsewhere).

    The rules, in order:

    1. If the record is not a knowledge record, return no mutability reasons.
    2. Read ``mutability`` from the candidate. If absent or None, it is ``UNKNOWN``.
    3. Parse the value. An unrecognised string is ``UNKNOWN`` and flagged as invalid.
    4. ``STABLE`` only: no mutability reasons.
    5. ``CHANGING`` or ``UNKNOWN``: the record is not train-eligible.
    """
    if not _is_knowledge_record(candidate):
        return ()
    raw = candidate.get("mutability")
    if raw is None or raw == "":
        # Missing mutability on a knowledge record: reject, do not silently default to stable.
        return (REASON_MUTABILITY_MISSING,)
    try:
        m = KnowledgeMutability(str(raw).lower())
    except ValueError:
        return (REASON_MUTABILITY_INVALID,)
    if m is KnowledgeMutability.STABLE:
        return ()
    # CHANGING or UNKNOWN
    return (REASON_CHANGING_IN_MANIFEST,)


def is_train_eligible_by_mutability(candidate: Mapping[str, object]) -> bool:
    """Convenience: True when ``mutability_reasons`` returns no reasons."""
    return not mutability_reasons(candidate)
