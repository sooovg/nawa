# ADR-0008: P6 reasoning and verification system before G5 closes (code-only scope, no quality claim)

- **Status:** ACCEPTED under the ROADMAP §0 roadmap-repair rule and the owner instruction of 2026-10-02 (10:07 +03):
  "if no independent unblocked code task exists, create an ADR that scopes the P6 code work only, such as fact
  verification, abstention when evidence is insufficient, and tool use; do not use external models before OD-10;
  keep G1 and the owner decisions open and recorded". Proposed by agent R-08. The owner may reverse it at any time.
  It applies §0 the same way ADR-0005 (P2) and ADR-0007 (P4) do. No goal or target changes; no existing task ID
  changes; no gate condition is weakened (G6 gains one); no task or result is deleted. No independent model review
  (OD-10 is open and `ModelRegistry` is empty).
- **Date:** 2026-10-02
- **Task:** R-08

## Context

1. After P4-07 (PR #30) no independent code task is unblocked in P0–P4:
   - P3-03, P4-01, P4-02a..P4-05a and P4-08 wait for OD-03;
   - P2-05a waits for the Eval role;
   - P1-06a waits for a trained text core (P5).

   The §2.2 row `P6-01..P6-09 | PLANNED` gives no scope, so the next agent has no executable task. This is the same
   internal conflict that ADR-0005 and ADR-0007 resolved, between the §0 rule ("tasks of a phase that do not depend on
   a pending decision may run") and an undivided status row.
2. P6 is "the practical core of the distinction" (§4 P6). It targets what NAWA exists for: hallucination, false
   confidence, verification, knowledge limits and abstention (ADR-0003). Its rule is: "the verifier is not only a copy
   of the generator; use deterministic rules for arithmetic, code execution, source checks, and independent review
   where needed".
3. Much of P6 does not need a trained model, real data or an external service. These parts can be built now and
   tested deterministically:
   - the five verification states (P6-08);
   - an exact calculator, a sandbox with an allowlist and an audit log, and a read-only file inspector;
   - claim-versus-evidence checks on structured contexts;
   - rule-based contradiction detection;
   - an abstention decision function and risk–coverage computation;
   - a lexical index;
   - routing rules;
   - the pipeline with a full trace.

   The existing evaluation suites already provide test material made by code:
   - `abstention`: twin items with and without evidence;
   - `faithfulness`: numbered contexts and citations;
   - `tool_use`: tool labels;
   - `factual`: a public answer bank.

   `nawa.evaluation.sandbox` already exists, and its docstring says "P6-02 must replace it".
4. Other parts of P6 cannot be done honestly now:
   - **Quality on NAWA:** risk–coverage of NAWA's own answers, thresholds, and the P6-09 ablation (model only, +RAG,
     +tool, +verifier, +abstention, full system). These need a trained text core (P5, G5).
   - **Dense embeddings and a learned reranker or verifier:** these need a trained model, or open weights under
     Track B with the six questions (ADR-0003).
   - **A real retrieval corpus:** this needs OD-03.
   - **"Approved search/API":** this needs an owner decision on providers, network access and cost. No such decision
     exists yet.
   - **An external model as verifier or judge:** this needs OD-10.

## Decision

- **D1. Split the status row** `P6-01..P6-09` into nine rows, and add five subtasks P6-01a, P6-02a, P6-03a, P6-04a and
  P6-05a for the parts that need a model, real data or an owner decision (D3). No existing ID changes.
- **D2. Code-only now (PLANNED, unblocked):** P6-01..P6-08, under these limits:
  - **Track S:** code inside `src/nawa/` (packages `retrieval`, `tools`, `reasoning`, `verification`, `abstention`,
    `routing`, `pipeline`), written from scratch, with no external model, tokenizer or hub library. The import rule of
    ADR-0007 D4 is extended to these packages by a test.
  - **No external model** of any kind, as generator, verifier, judge or reviewer (OD-10). Independent checking means
    deterministic rules and executable checks.
  - **No network:** tools have no network access. Search and external APIs are P6-02a (BLOCKED).
  - **No real data:** inputs are made by code (synthetic fixtures, the existing suite generators), or are the public
    `dev` and `calib` items already in Git. The `frozen` split is never read (Eval role, SECURITY.md §3). No upload to
    HF.
  - **CPU only,** inside the existing budget guard (`cpu_local`).
  - **Pass/fail correctness criteria, registered before any run,** with tolerances written down, as in ADR-0007 D2.
    Examples:
    - the calculator is exact on rationals and refuses unsafe input;
    - the sandbox blocks network and file writes outside its directory and records every call in the audit log;
    - the verifier returns exactly one of the five P6-08 states, and returns `SUPPORTED` only when every claim has
      cited evidence that entails it under the rule;
    - contradiction detection finds planted conflicts and does not flag consistent evidence;
    - risk–coverage matches a brute-force computation;
    - the pipeline trace replays deterministically.
  - **Negative controls** for every check, so a check cannot pass vacuously. Examples: an unsupported claim must not be
    `SUPPORTED`, and a planted contradiction must be `CONTRADICTED`.
  - **Generators are stubs:** wherever P6 needs a generator (candidates, self-consistency), it is a declared interface
    tested with deterministic stub generators, including an oracle and a stub that is wrong on purpose. Results with
    stubs show that the machinery is correct. They never show that NAWA answers better.
  - **Records:** every run uses the experiment record with `data_kind: synthetic` (the first P6 task that records a
    run extends the `nawa.experiments` validator from P4 code tasks to P6 code tasks under the same rules). Every claim
    is of type `correctness` or `evidence`, and none is an improvement claim.
  - **Fixed numbers stay fixed:** no target, abstention threshold or gate number in `eval/targets.yaml` or
    `SUCCESS_CRITERIA.md` changes. Any threshold that P6 code selects on synthetic scores is evidence only and is not
    adopted.
  - **Reuse:** `nawa.evaluation.sandbox`, `normalize.is_abstention`, the suites and `nawa.evaluation.taxonomy` are
    reused, not copied. P6-02 hardens the sandbox in place or wraps it, and the evaluation runner keeps working.
- **D3. BLOCKED** (new subtasks, so that nothing is lost when a code task closes on synthetic evidence):
  - **P6-01a:** dense embeddings, a learned reranker, and retrieval over a real licensed corpus. Blocked on OD-03 and
    on a trained core (P5) or a documented Track B need (ADR-0003).
  - **P6-02a:** approved search and external APIs. Blocked on a new owner decision **OD-11**: which providers, network
    scope, rate and cost limits, and data sent. OD-05 also applies if it costs money. If the owner rejects external
    search, P6-02a becomes REJECTED by that decision and stops being a G6 condition.
  - **P6-03a:** candidate generation and self-consistency with a NAWA model. Blocked on G5.
  - **P6-04a:** verification of free-text answers (open claim extraction, learned entailment) on NAWA outputs. Blocked
    on G5; any external model for this is also blocked on OD-10.
  - **P6-05a:** calibration and abstention thresholds for NAWA, fitted on `calib` and checked once on `frozen` by the
    Eval role. Blocked on G5.
  - **P6-09** (the ablation: model only, +RAG, +tool, +verifier, +abstention, full) stays a single task and is
    BLOCKED on G5 and P6-01a..P6-05a. A harness smoke run with stubs may run inside P6-07, labelled as such, and is
    never P6-09 output.
- **D4. No quality claim.** No P6 result under this ADR supports a statement that NAWA hallucinates less, abstains
  better, or verifies better. G6 keeps all four conditions, which are measured on NAWA, and gains one: P6-01a..P6-05a
  and P6-09 are done, unless the owner rejected P6-02a. G6 cannot close on stub evidence, and cannot close before G0–G5
  (§0).
- **D5. Execution order** (dependencies, IDs unchanged):
  1. **P6-08:** the five states and their rules, which are the vocabulary every other part uses.
  2. **P6-02:** the calculator, sandbox, file inspector, permissions and audit log, which the verifier calls.
  3. **P6-04:** claims, citation, deterministic fact checks, contradiction, uncertainty and consensus.
  4. **P6-05:** the abstention decision function and risk–coverage.
  5. **P6-01:** the chunker, lexical index, freshness and source-quality metadata.
  6. **P6-06:** routing rules, escalation, fallback and trace.
  7. **P6-03:** the planner, decomposer, state and budget, with the generator interface.
  8. **P6-07:** the pipeline.

## Consequences

- The next agent has an executable task (P6-08) without waiting for an owner decision.
- G6 keeps all its conditions and gains one, so no gate is weakened. A test checks the split, the BLOCKED rows, the G6
  conditions and the import rule.
- **OD-11** is added to ROADMAP §2.4 as OPEN. It blocks only P6-02a.
- When G5 closes, every P6 component is measured on NAWA (P6-01a..P6-05a, P6-09) before any claim about
  hallucination or abstention is made.

## Alternatives rejected

- **Keep P6 fully PLANNED until G5.** Rejected: it stops all independent work, against §0 and the owner instruction,
  although the deterministic parts need no model.
- **Use an external LLM as verifier or judge now.** Rejected: OD-10 is open, and the P6 rule asks for deterministic
  checks where possible.
- **Use open-weight embeddings for retrieval now.** Rejected: no documented need yet. A lexical index answers the
  code-only scope, and Track B needs the six questions (ADR-0003).
- **Tune abstention thresholds on synthetic scores and write them into the targets.** Rejected: thresholds belong to
  the model being calibrated, and targets may not change silently.
