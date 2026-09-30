# ADR-0003: NAWA is an original system; no external baseline is required; the model-use policy

- **Status:** ACCEPTED (owner directives of 2026-09-30, 16:27 and 16:35 +03)
- **Date:** 2026-09-30
- **Task:** R-02 (DONE with this ADR). Supersedes P1-04 and P1-05. Adds R-03 and OD-10.

## Context

The owner issued two directives on the same day.

**Directive 1 (16:27).** NAWA is an original system. It is not a copy of Qwen, Llama, or any other model, and it is not built to win a leaderboard. It must address the weaknesses of current models: hallucination, false confidence, weak verification, not knowing the limits of knowledge, weak planning and task execution, weak memory and learning from mistakes, weak Arabic/document/complex-task handling, and unnecessary size and cost. The strongest authorized models may be used during development as experts, reviewers, designers, and testers, and no decision may rest on a single model. Open-weight models are not used by default. They are used only when a specific need is shown and six questions are answered.

**Directive 2 (16:35).** Stop the Qwen runs and any comparison between Qwen or other models immediately. No external model is a condition for progress in NAWA. Do not wait for that comparison, and do not update the roadmap with its results. Treat the Qwen tests as a cancelled optional experiment: do not delete the reports, record them as SUPERSEDED. Change ROADMAP.md and AGENTS.md so that the goal is to invent and build an original system, there is no mandatory task to run Qwen or any open-weight model, no external baseline is a condition for moving on, open weights are used only for a specific documented technical need, and work continues on the highest task that builds NAWA itself.

## What happened before Directive 2 (kept for the record)

Before Directive 1, the agent had started P1-04 as it was then written ("run several open models of different sizes"). It measured three models on `dev` (EXP-0001..EXP-0003) and started a fourth one (Qwen2.5-1.5B-Instruct). After Directive 1, the agent recorded justifications for these models. When Directive 2 arrived, the 1.5B run was killed after 6 of 9 suites. It left no report and is recorded as EXP-0004 (aborted). Nothing was deleted. The three reports stay in `eval/reports/`, marked SUPERSEDED in `eval/reports/README.md`. **Their numbers are not used in any target, gate, or roadmap status.**

## Decision

### D0. Goal and meaning of "baseline"

- The goal of NAWA is to invent and build an original system. Comparing models is not a goal.
- No task requires running Qwen or any open-weight model. No external baseline is a condition for any gate or phase.
- In ROADMAP.md, **"baseline" means an internal NAWA reference** unless stated otherwise: the trivial evaluation references (`oracle`, `always_abstain`, P1-07), NAWA's reference core (P3-04/P3-05), the core alone without the system layers (the "model only" ablation in P6-09), and the previously accepted NAWA release (T5, P9-06).
- T1, T2, T5, and T6 keep their thresholds. Only their reference point is now internal. **No threshold was lowered.**
- T3 ("match or exceed a 4–8× larger model in the first domain") is kept, and its number is unchanged. It becomes **optional**: an efficiency indicator that is not a gate condition. It is measured only if a documented need appears.

### D1. Two classes of external models

| Class | Use | Enters the NAWA product? | Record |
|---|---|---|---|
| **Development tools** (authorized models, open or closed, through an approved channel) | design review, code review, red-teaming, error hunting, alternative proposals | **No.** Outputs are proposals, accepted only through tests, measurements, or independent review | Role, provider, date, and the reviewed artifact, in the task report or `experiments/log.jsonl`. The harness is task R-03 |
| **Open-weight models** (weights run by NAWA) | only a specific documented technical need: local/private run, owned weights, no API dependency, customization closed models do not allow, long-term cost, testing a technique or architecture, a final component that must run independently | Only by owner decision and an ADR (Track S rule) | A `configs/model_registry.yaml` entry with the six answers. Enforced by `tests/test_model_registry.py` |

### D2. The six questions (before any open-weight model is used)

`need`, `why_not_others`, `nawa_part`, `affects_final_product` (`false` unless an ADR says otherwise), `license` + `license_limits`, and `fallback`. If any answer is unclear, the model is not used.

### D3. Data protection with external models

- The `frozen` split is never sent to an external model or API.
- User data, secrets, and tokens are never sent to external models.
- Outputs of external models are not used for training or distillation until the provider's terms are checked and a decision is recorded (OD-10).

### D4. What counts as evidence

A model's opinion is a hypothesis. It becomes a project fact only through a deterministic check, an executed test, a measurement with confidence intervals, or independent reviewers followed by one of those checks. A model that produced an artifact is never its sole reviewer. Gates are judged by frozen measurements run by the Eval role.

## Task changes (nothing deleted; no ID renumbered)

| Task | Before | After | Reason |
|---|---|---|---|
| P1-04 | PLANNED: run several open models | **SUPERSEDED** | Directive 2: no mandatory external comparison |
| P1-05 | PLANNED: "baseline for a small local decoder" | **SUPERSEDED**, merged into P3-04/P3-05 | NAWA's own reference core *is* the internal reference, so a parallel task would duplicate P3-04/P3-05 |
| P1-06 | fix T1–T6 after "the starting point" | fix T1–T6 after measuring the internal reference; waits for P3-05 | D0 |
| G1 | "baseline numbers saved" | "internal-reference numbers saved; no external baseline required" | D0 |
| P5-05..P5-08 | Track B tasks | optional, not G5 conditions | D1 |
| R-02 | — | DONE (this ADR) | — |
| R-03 | — | PLANNED: multi-model development-review harness | Directive 1 |
| OD-10 | — | OPEN: authorized development-tool providers, and whether their outputs may become training data | D3 |

## Rejected alternatives

- **Finish the 1.5B run and record all four as baselines:** rejected by Directive 2.
- **Delete the partial reports:** rejected. AGENTS.md §2.2 forbids deleting results, and Directive 2 says keep them as SUPERSEDED.
- **Remove T3:** rejected. Removing a target is not needed to satisfy the directive. Making it optional and not a gate condition is enough, and its number is unchanged.
- **Keep P1-05 as a separate task:** rejected as duplicate work with P3-04/P3-05 (AGENTS.md §2.1).

## Consequences

- The next task that builds NAWA itself and is not blocked is **P3-04** (reference decoder from scratch), followed by P3-05 (XOR and tiny character LM). Both run on local CPU, which the budget guard allows, and need no external model or licensed data. P1-08 (first verified Atlas failures) is recorded next, using NAWA's own model failures once P3-05 exists.
- P3-04 and P3-05 may be *executed* before G0–G2 are closed (ROADMAP §0, "gate closure in order"). G3 cannot be *closed* before G0–G2.
