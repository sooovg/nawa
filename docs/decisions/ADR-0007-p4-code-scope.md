# ADR-0007: P4 efficiency studies before G3 closes (code-only scope, adoption blocked)

- **Status:** ACCEPTED under the ROADMAP §0 roadmap-repair rule and the owner instruction of 2026-10-01 (18:54 +03:
  "fix internal roadmap conflicts when that is the highest open task; continue safe independent work automatically").
  Proposed by agent R-06. The owner may reverse it at any time. It applies §0 the same way ADR-0005 (P2) and ADR-0006
  (P3) do. No goal or target changes; no existing task ID changes; no gate condition is weakened (G4 gains one);
  no task or result is deleted. Revised after an independent review (Claude Opus 5.5, reviewer role, R-03): see
  "Review" below.
- **Date:** 2026-10-01
- **Task:** R-06

## Context

1. After P3-01/P3-02 (PR #23) the report says no code task is clearly unblocked: P3-03 waits for OD-03, P2-05a needs the
   Eval role, P1-06a needs a trained text core. It names P4-03 and P4-05 as code-only candidates, but says an ADR must
   scope them first. That ADR does not exist, so the next agent has no executable task. This is an internal conflict
   between the §0 rule ("tasks of a phase that do not depend on a pending decision may run") and the §2.2 row
   `P4-01..P4-08 | PLANNED`, which gives no scope.
2. P4 is a set of **hypotheses** (§4 P4: "every technique is an experimental hypothesis ... accepted only if it beats the
   baseline on a defined benchmark"). An adoption decision ("قرار تقني") needs real text, the chosen tokenizer (P3-03),
   and an independent gate. None exists before G3, and real text needs OD-03.
3. The **implementations and their correctness tests** do not need any of that. A KV cache is either exactly equivalent
   to recomputation or it is wrong; a ternary quantizer either maps weights to `{-1, 0, +1}·scale` with a working
   straight-through gradient or it does not. These are code and tests, like the P2 tools (ADR-0005) and the tokenizer
   harness (ADR-0006). They read no external data, use no external weights (Track S), and decide nothing.

## Decision

- **D1.** Split the status row `P4-01..P4-08` into eight rows, and add four subtasks P4-02a, P4-03a, P4-04a, P4-05a
  for the real-text comparisons (see D3). No existing ID changes.
- **D2. Code-only now (PLANNED, unblocked):** P4-02, P4-03, P4-04, P4-05, P4-06, P4-07, under these limits:
  - implementation inside `src/nawa/` on the P3-04 reference core, written from scratch (Track S): no external weights,
    no external model library, no external dataset, no frozen data, no upload, CPU only (budget guard `cpu_local`);
  - **pass/fail correctness criteria** registered before the run, including any numerical tolerance (e.g. KV-cache
    and compiled forward equal to full recomputation within a tolerance written down before the run; greedy
    speculative decoding emitting exactly the target model's greedy tokens; ternary value set; gradient flow;
    parameter-count formula; causality);
  - in P4-05, only KV cache, greedy speculative decoding and compilation are equivalence-checked. Weight sharing,
    low-rank and sparsity change the model, so P4-05 gives them correctness tests only; their quality effect is P4-05a;
  - the P4-06 record must carry `data_kind: synthetic | real`, and its validator must reject any adoption or
    "improvement" claim from a record whose `data_kind` is `synthetic`;
  - runs stay inside the existing budget guard (`cpu_local`) at the scale of the P3-05 sanity runs; anything larger
    is a budget question for OD-05;
  - **comparative numbers** on the synthetic sources that already exist (P3-05 XOR and Markov source, P3-02 generated
    text) are recorded as evidence only, never as a ranking or adoption;
  - every experiment uses the P4-06 record and is listed in `docs/ablations.md` (P4-07), including failures.
- **D3. BLOCKED:**
  - **P4-01** (scaling curves): curves of loss/quality against parameters, tokens and compute describe the data they
    are measured on. On synthetic text they would mislead every later size decision. Blocked until a licensed real
    corpus (OD-03, P2-06..P2-08) and the tokenizer choice (P3-03) exist. A curve on synthetic data may be run as a
    harness smoke test inside another task, labelled as such, never as P4-01 output.
  - **P4-02a, P4-03a, P4-04a, P4-05a** (new): the same comparisons as P4-02..P4-05 on licensed real text after
    P3-03. A code-only P4 task can be DONE on synthetic evidence; its comparison cannot. These subtasks carry the
    comparison, so it cannot be lost, and G4 gains the condition that they are done (a stricter gate, not a weaker one).
  - **P4-08** (experimental checkpoints to HF `nawa-core/dev`): synthetic-task checkpoints are re-created by one
    command and carry no capability worth storing. Blocked until a P4 run on real text produces a reproducible
    checkpoint with a manifest. Nothing is uploaded to HF under this ADR.
- **D4. No adoption.** No technique becomes part of NAWA ("ternary", "hybrid", "MoE", or any other label) under this
  ADR. The §4 "قرار تقني" stays as written and needs an independent gate after G3. The reference core default
  configuration does not change under this ADR. This is enforced by tests, not by text: the `configs/base_model.yaml`
  `config_hash` is pinned to `918f4cf4877c0cca` (EXP-0006), and the Track S packages `nawa.model`, `nawa.training`
  and `nawa.tokenizer` may not import external model, tokenizer or hub libraries.
- **D5. Execution order** (dependencies, IDs unchanged): P4-06 (the record every P4 experiment needs) → P4-05 (KV
  cache, greedy speculative decoding and compilation first; the lossy items last) → P4-03 → P4-02 → P4-04, with P4-07
  updated by each of them.

## Consequences

- G4 keeps all its conditions ("scaling curves exist" needs P4-01) and gains one (P4-02a..P4-05a done), so G4 cannot
  close before P4-01 and P4-02a..P4-05a are done, and not before G0–G3 close (§0). A test checks that G4 is not
  closed while P4-01 is not DONE.
- The next agent has an executable task (P4-06) without waiting for an owner decision.
- When OD-03 and P3-03 are resolved, P4-01 starts, and every code-only P4 implementation is re-measured on real text
  before any adoption decision.

## Alternatives rejected

- **Keep P4 fully PLANNED and wait for OD-03.** Rejected: it stops all independent work, against the §0 rule and the
  owner instruction to continue safe work automatically.
- **Run P4-01 scaling curves on the synthetic Markov source now.** Rejected: the curve shape is a property of the data;
  a synthetic curve would bias the size decision (§0: size is decided by measurement, not assumption).
- **Allow adoption on synthetic evidence when the gain is large.** Rejected: it would bypass the §4 technical-decision
  rule and the independent-judgement rule (AGENTS.md §6).

## Review

An independent reviewer model (Claude Opus 5.5, reviewer/error_hunter role, payload passed `nawa.review.check_payload`)
returned APPROVE_WITH_CHANGES with three blocking points. Each was checked against the code before it was accepted
(ADR-0003 D4: a model opinion is a hypothesis):

1. P4-02/P4-04 had no DONE definition separating code from comparison → accepted; P4-02a..P4-05a added (D1, D3).
2. The P4-05 row claimed exact equivalence for lossy items → accepted; P4-05 split by item, tolerances registered
   before the run (D2).
3. D4 was enforced only by text → confirmed (no test pinned the config hash; no import rule for Track S packages);
   two tests added (D4).

Non-blocking points accepted: G4-not-closed check, wording fixes. Not accepted: requiring R-06's own report to carry a
merge hash before the merge exists (the PR number is the reference; the hash is recorded after merge, as in earlier
tasks).
