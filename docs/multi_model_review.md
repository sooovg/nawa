# Multi-Model Development Review (R-03)

**Status:** Active (ADR-0003 D1)
**Date:** 2026-09-30

## Purpose

This document defines the harness for using external models as development tools
during NAWA's construction. It implements ADR-0003 D1: authorized models may be
used as experts, reviewers, designers, and testers, but no decision rests on a
single model, and no frozen data, user data, or secrets are sent to any external
model.

## Scope

This harness covers:

1. **Role registry** — what roles external models may play.
2. **Isolation rules** — what data may and may not be sent.
3. **Review records** — how each review is logged.
4. **Disagreement logging** — how conflicts between models are recorded.
5. **Decision rule** — preventing single-model decisions.

## 1. Role Registry

Each external model used in development is registered with a role. A model may
hold multiple roles, but each review instance assigns exactly one role.

| Role | What it does | What it does NOT do |
|---|---|---|
| `reviewer` | Reviews code, architecture, or docs; proposes improvements | Does not merge or approve; proposals are hypotheses |
| `designer` | Proposes designs, architectures, or approaches | Does not decide; proposals need measurement |
| `tester` | Generates test cases, finds edge cases, red-teams | Does not pass/fail gates; tests must be deterministic |
| `error_hunter` | Finds bugs, hallucinations, or failures in outputs | Does not verify; findings need independent verification |
| `doc_writer` | Drafts documentation or comments | Does not approve; docs need review |

A model not in the registry is not used. The registry is `ModelRegistry` in
`src/nawa/review.py` and is enforced by `tests/test_multi_model_review.py`. Only the
owner can authorize a model (`authorized_by: owner`, OD-10); an entry authorized by an
agent is rejected. The registry for open-weight models that NAWA runs itself is a
different file, `configs/model_registry.yaml` (ADR-0003 D2).

## 2. Isolation Rules

**Never sent to any external model:**

- The `frozen` evaluation split (ADR-0003 D3).
- User data, personal information, or PII.
- Secrets, tokens, or credentials.
- Proprietary NAWA training data or weights.

**May be sent (with care):**

- Public code snippets for review.
- Architecture descriptions (without internal data).
- Synthetic test cases.
- Public documentation.

The review harness includes a `check_payload` function that scans payloads for
known patterns of secrets, tokens, and frozen references before sending.

## 3. Review Records

Every review by an external model is summarized in `experiments/log.jsonl` with the
fields below. `ReviewLog` keeps the full append-only record in its own JSONL file
(path chosen by the task; never a Git-tracked data file with secrets).

```json
{
  "experiment_id": "EXP-xxxx",
  "task_id": "R-03",
  "track": "meta",
  "purpose": "review: <role> on <artifact>",
  "review": {
    "model": "<provider/model>",
    "role": "reviewer|designer|tester|error_hunter|doc_writer",
    "artifact": "<file or component reviewed>",
    "date": "YYYY-MM-DD",
    "findings": ["..."],
    "recommendations": ["..."],
    "accepted": ["...", "..."],
    "rejected": ["...", "..."]
  },
  "conclusion": "...",
  "next_action": "..."
}
```

## 4. Disagreement Logging

When two or more external models produce conflicting recommendations on the same
artifact, a disagreement record is created:

```json
{
  "disagreement_id": "DIS-xxx",
  "artifact": "<file or component>",
  "positions": [
    {"model": "...", "position": "..."},
    {"model": "...", "position": "..."}
  ],
  "resolution": "measurement|test|owner_decision|deferred",
  "resolved": false,
  "resolution_note": "..."
}
```

A disagreement is resolved only by:
- A deterministic check or test.
- A measurement with confidence intervals.
- An owner decision (for non-technical conflicts).
- Deferral (recorded, not silently dropped).

## 5. Decision Rule

**No decision in NAWA rests on a single external model.**

A model's output is a hypothesis. It becomes a project fact only through:

1. A deterministic check, or
2. An executed test, or
3. A measurement with confidence intervals, or
4. Independent review followed by one of the above.

The model that produced an artifact is never its sole reviewer.

`can_decide()` enforces this: it refuses a decision when there is no review, when a
reviewer is not registered for its role (if a registry is passed), when the producer
model is the only reviewer, or when no deterministic check / executed test /
measurement has passed. **Agreement between several models is never enough on its
own** (review fix on PR #17, 2026-10-01).

## 6. Implementation

The harness is implemented in `src/nawa/review.py`:

- `ReviewRole` — enum of allowed roles.
- `ReviewRecord` — dataclass for a single review.
- `DisagreementRecord` — dataclass for a disagreement.
- `ReviewLog` — append-only log of reviews and disagreements.
- `check_payload` — scans payloads for secrets/frozen references.
- `ModelEntry` / `ModelRegistry` — owner-authorized models and their roles
  (`ModelRegistry.register`, `ModelRegistry.require_role`).
- `can_decide` — the decision gate in §5.

## 7. OD-10 Dependency

OD-10 (authorized providers and whether outputs may become training data) is
OPEN. This harness does not authorize specific providers — it provides the
framework. When OD-10 is resolved, providers are added to the registry without
changing the harness.
