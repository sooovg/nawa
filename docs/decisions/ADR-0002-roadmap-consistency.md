# ADR-0002: ROADMAP internal consistency fixes (R-01)

- **Status:** ACCEPTED (under the owner's standing instruction of 2026-09-30 to fix internal ROADMAP inconsistencies)
- **Date:** 2026-09-30
- **Resolves:** ADR-0001 items C4 and C5, plus the related gaps listed below

## Constraints respected

- The project goal and the S/B architectural tracks are unchanged.
- No evaluation criterion or target was lowered; T1–T6 are untouched.
- No task or result was deleted, and no used Task ID was renumbered.

## Changes

1. **Gates (§2.1 vs §4).** The §2.1 table used names that did not match the gate definitions in §4 and had no G10 row. The table now follows §4, where gate Gn closes phase Pn, and a G10 row was added. The existing G0 status was kept.
2. **Task ranges (§2.2 vs §4).** The table rows were changed to match the tasks actually defined in §4: `P3-01..P3-08`, `P4-01..P4-08`, `P5-01..P5-10`, `P6-01..P6-09`. P3-09, P3-10, and P4-09 were never defined anywhere, so nothing was removed. P5-09, P5-10, and P6-09 were defined in §4 but missing from the table, and are now tracked.
3. **Owner decisions register.** New §2.4, with IDs OD-01..OD-09. Unresolved decisions are now tracked in one place instead of scattered `[OWNER DECISION REQUIRED]` markers.
4. **Operating rules.** New subsection in §0 recording the owner's instructions of 2026-09-30: sequential execution, "owner decisions don't stop independent work", in-order gate *closure*, self-merge after CI with the `PENDING_REVIEW` independence safeguard, and the temporary public-repo policy.
5. **`RISK_REGISTER.md`.** P0-04 requires this file, but it was missing from the §3.1 tree. It was added to the tree.
6. **Suite names.** P1-02 said "Arabic, regression", while AGENTS.md §10 and T5 say `arabic` and `regression_general`. P1-02 now uses the AGENTS.md names.
7. **P1 execution order.** P1-07 (runner/report) is a prerequisite for P1-04 and P1-05, so the execution order is recorded explicitly without renumbering.

## ADR-0001 follow-up

| Item | Resolution |
|---|---|
| C1 public GitHub repo | Accepted as temporary by the owner (OD-07). No secrets, private data, weights, or frozen eval may go into Git. |
| C2 `vuuuv/nawa` | Still open (OD-08). |
| C3 Space template files | No action; to be replaced in P10-07. |
| C4, C5 | Resolved by this ADR. |
| C6 | `RISK_REGISTER.md` is created under P0-04. The `budget.yaml` values are OD-05. |
| C7, C8 | Informational; no action needed. |
