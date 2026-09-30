# ADR-0004: Split P1-06 so target fixing is not circular and not anchored on a model that cannot read text

- **Status:** ACCEPTED (owner instruction of 2026-09-30, 17:37 +03: "merge, and fix the P1-06 conflict first")
- **Date:** 2026-09-30
- **Task:** R-04 (DONE with this ADR). Rescopes P1-06, adds subtask P1-06a. Amends the P1-06 row of ADR-0003's task table.

## Context

ADR-0003 made P1-06 ("fix T1–T6 numerically") wait for P3-05, on the idea that the NAWA reference core is the internal reference.
P3-05 is now done (EXP-0008, EXP-0009), and it showed two problems:

1. **The P3-05 model cannot be a T1–T6 anchor.** It is trained on a synthetic 29-symbol Markov source. It cannot read the
   evaluation suites of P1-02, so it has no hallucination rate, abstention recall, or regression accuracy to measure. Using
   its numbers would be a fake reference.
2. **A dependency loop.** A meaningful reference for T1, T2 (answerable accuracy), T5, and T6 is a NAWA core trained on real
   text. That needs licensed data (P2), a tokenizer (P3-01..P3-03), and training (P5). But ROADMAP §0 says a phase whose
   outputs depend on an earlier gate cannot start before that gate is closed, and P1 says "no large training before an
   internal reference and a frozen test exist". If P1-06, as written, were a condition of G1, then G1 would wait for P5,
   and P5 would wait for G1.

## Decision

### D1. P1-06 is split. No ID is renumbered, and no task is deleted.

| Task | Scope | Depends on | Condition of |
|---|---|---|---|
| **P1-06** (rescoped) | Fix the **definitions** of T1–T6 in `eval/targets.yaml` and `SUCCESS_CRITERIA.md`: metric, suites, split used (dev/calib, never frozen), direction, threshold, and **which internal reference** each target is relative to. Record the numbers that already exist: the trivial references of P1-07 (`oracle`, `always_abstain`). | P1-07 (DONE) | G1 |
| **P1-06a** (new) | **Numerically anchor** T1, T2, T5, and T6 on the first NAWA core candidate trained on real text, measured on dev/calib by the Eval role (the "model only" reference, P6-09). Write its `run_id` into `eval/targets.yaml` `baseline_reference`. Set T6 `min_citation_accuracy`. | first P5 candidate (P5-01/P5-02) | **G5** (added condition) |

### D2. Nothing is lowered.

- T1–T6 thresholds are unchanged. The rule "targets may only be raised" still applies to P1-06 and P1-06a.
- G1 keeps its conditions. "Internal-reference numbers saved (P1-07 references and the P3-05 core)" is already met by
  P1-07 and EXP-0008/EXP-0009. These P3-05 numbers are **training-sanity references**, not T1–T6 anchors.
- G5 gets one more condition (P1-06a done). This raises the bar and does not lower it: no training candidate can pass G5 until
  the targets it is judged by are anchored.

### D3. Safeguard carried from P1-07

T1 alone can be gamed by always abstaining (0% hallucination). P1-06 must define T1 together with T2 answerable accuracy, so a
model that always abstains fails.

## Rejected alternatives

- **Anchor T1–T6 on the P3-05 model:** rejected. It cannot answer the suites, so the numbers would be fabricated (AGENTS.md §2.5).
- **Keep P1-06 as a G1 condition and wait for P5:** rejected. This is the dependency loop in the context.
- **Anchor on an external open-weight model:** rejected by ADR-0003 (no external baseline is a condition for progress).
- **Drop the anchoring step:** rejected. T1, T2, and T5 are relative targets, so they need a measured reference.

## Consequences

- P1-06 (rescoped) is unblocked now (it depends only on P1-07) and is the next task by ID.
- P1-06a is PLANNED and blocks G5 only.
- `eval/targets.yaml` keeps `status: provisional` until P1-06. It becomes `definitions_fixed` after P1-06, and `anchored` after P1-06a.
- `tests/test_roadmap_consistency.py` checks that P1-06 no longer waits for P3-05, that P1-06a exists, and that G5 names it.
