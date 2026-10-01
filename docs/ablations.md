# NAWA — P4 ablations register (ROADMAP P4-07, ADR-0007)

Every P4 experiment is listed here, including failures. A row points to its record in `experiments/log.jsonl`
(validated by `python -m nawa.experiments validate`).

Rules (ADR-0007):

- `data_kind = synthetic` rows are **evidence only**. They never support an improvement or adoption claim; the
  validator rejects such a claim.
- No technique is adopted from this table. Adoption is the ROADMAP §4 "technical decision" after an independent gate,
  on real text (P4-02a..P4-05a), after G3.
- No real data before OD-03 is resolved; no artifact upload while P4-08 is BLOCKED.

| Experiment | Task | Technique | data_kind | Registered criteria | Result | What it shows | What it does not show |
|---|---|---|---|---|---|---|---|
| EXP-0024 | P4-06 | none (record pipeline) | synthetic | rerun identical, finite loss, loss decreased; validator: legacy log valid, valid records accepted, 22 violation types detected, append refuses invalid | PASSED (all = 1.0 / true) | The P4 record is enforced by re-derivation and the pipeline is deterministic | Anything about model quality or any technique |
