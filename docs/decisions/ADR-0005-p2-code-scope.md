# ADR-0005: Which P2 tasks can run before G0/G1 close (code-only scope)

- **Status:** ACCEPTED (owner instruction of 2026-10-01, 07:05 +03: merge PR #18 after PR #17). Proposed by agent R-05. Applies an existing ROADMAP §0 rule; it does not change any goal, gate,
  target, or task ID. It reverses a "no unblocked task" statement made by two earlier
  reports (P3-08 and R-03).
- **Date:** 2026-10-01
- **Task:** R-05

## Context

1. The P3-08 report on `main` ends with: "the next unblocked tasks are in P2, but they need G0 and G1 to close first". The R-03
   report (open PR #17) repeats it: "no unblocked tasks remain; P2 needs G0/G1 to close". With every P3 code task done, this
   statement stops all work.
2. ROADMAP §0 ("closing gates in order", owner rules of 2026-09-30) says something narrower:
   - tasks in a phase that **do not depend on a pending owner decision** may run;
   - **closing** a gate needs every earlier gate closed;
   - a phase **whose outputs depend on an earlier unclosed gate** (for example data and training) does not start.
3. P2 mixes two kinds of tasks under one row `P2-01..P2-08`:
   - **code and tests** (verifier, abstention-twin builder, preference-pair builder, cleaning/PII/dedup/decontamination/
     provenance tools). These can be built and tested on synthetic inputs made by code (as in P1-02 and P3-05) and on the
     dev-split Atlas records of P1-08. They ingest no external data, release nothing, and need no owner decision.
   - **data production** (mining failures from a model, building data layers from real sources, data cards, and upload to
     `nawa-data`). These depend on OD-01, OD-03, OD-10, or on a text model that does not exist yet.
4. So the earlier statement is stricter than §0 for the first kind and correct for the second kind. That is an internal
   inconsistency in the roadmap, which §0 lets an agent fix if the goal, tracks, and criteria do not change.

## Decision

### D1. Split the P2 status row. No ID changes, and no task is deleted.

| Task | Status | Why |
|---|---|---|
| P2-01 `mine.py` | BLOCKED | It runs models to collect failures. No NAWA text core exists yet (P5), and external models as tools need OD-10. The P1-08 Atlas already covers the deterministic eval-run path. |
| P2-02 `verify.py` | PLANNED (unblocked, code only) | Independent verification (calculation, code execution, licensed source check, expert review hook) can be built and tested on synthetic cases and P1-08 records. |
| P2-03 abstention twins | PLANNED (unblocked, code only) | Builder and checks on code-generated contexts. Nothing it makes is `train_eligible` before G2. |
| P2-04 preference pairs | PLANNED (unblocked, code only) | Builder and schema. Real grounded-versus-hallucinated pairs need model outputs (P2-01 or P5), so only the builder is in scope now. |
| P2-05 cleaning/PII/dedup/decontamination/provenance/license/quality | PLANNED (unblocked, code only) | Tools tested on synthetic fixtures. Decontamination uses the frozen item hashes already in Git (`eval/frozen_item_hashes.txt`) and never reads frozen content. |
| P2-06 data layers | BLOCKED | Needs licensed real sources (OD-03) and the first domain (OD-01). |
| P2-07 `DATA_SOURCES.md`, `LICENSES.md`, data cards | BLOCKED | Needs OD-03. |
| P2-08 upload `nawa-data:v1` | BLOCKED | Needs OD-03 and approved rights (G2). |

### D2. Limits on the unblocked P2 code tasks

- No external corpus is downloaded or ingested. Inputs are code-generated synthetic data, dev/calib items, or P1-08 Atlas records.
- Nothing they produce is training data. Any record they make is `train_eligible: false` until G2 closes.
- The frozen split is never read. Only its committed item hashes may be used for decontamination checks.
- Nothing is uploaded to Hugging Face.
- **G2 is not closed by these tasks.** G2 still needs 200 human-reviewed examples, zero known leakage into frozen, full record
  fields, and licensed data only. Closing G2 still needs G0 and G1 closed first.

### D3. Execution order inside P2 (no renumbering)

P2-02 → P2-05 → P2-03 → P2-04. P2-01, P2-06, P2-07, and P2-08 wait for their decisions. P2-02 comes first because the other
builders need its independent check before they can mark any record `verified`.

## Rejected alternatives

- **Keep "P2 needs G0/G1 closed" for all of P2:** rejected. It is stricter than §0 and stops all independent work, against the
  owner rule "owner decisions do not stop the whole project".
- **Unblock all of P2, including data production:** rejected. Data production depends on OD-01, OD-03, and OD-10, and §0 names
  data as an example of output that waits for an earlier gate.
- **Unblock P2-01 using an external open-weight model:** rejected by ADR-0003 (no external model is a condition for progress) and
  by OD-10 (not decided).

## Consequences

- The next unblocked task by ID is P2-02.
- The P3-08 report text on `main` is kept as written (history is not rewritten). The R-05 report in ROADMAP §2.3 records the
  correction.
- `tests/test_roadmap_consistency.py` checks that this split exists, that the data-production tasks stay BLOCKED, and that G2
  keeps its conditions.
