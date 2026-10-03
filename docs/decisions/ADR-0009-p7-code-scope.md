# ADR-0009: P7 memory, expert specification and routing machinery before G5 closes (code-only scope, no quality claim)

- **Status:** ACCEPTED under the ROADMAP §0 roadmap-repair rule and the owner directive of 2026-10-03: "independent
  and safe work continues automatically in roadmap order, without waiting for a separate order". Proposed by agent
  R-10. The owner may reverse it at any time. It applies §0 the same way ADR-0005 (P2), ADR-0007 (P4) and ADR-0008
  (P6) do. No goal or target changes; no existing task ID changes; no gate condition is weakened (G7 gains one); no
  task or result is deleted. No independent model review (OD-10 is open and `ModelRegistry` is empty).
- **Date:** 2026-10-03
- **Task:** R-10

## Context

1. After R-09 (PR #41, `bb827fe`) no task in §2.2 is both unfinished and unblocked:
   - P6-01..P6-08 are DONE; P6-01a..P6-05a and P6-09 are BLOCKED (G5, OD-03, OD-10, OD-11);
   - P0–P4 leftovers wait for owner decisions (OD-01, OD-03, OD-09, the Eval role) or for a trained core (P1-06a);
   - P5 trains the core and depends on G2–G4 and on data (OD-03).

   R-09 wrote "no unblocked task; the next agent waits for the owner decisions". That sentence followed an owner
   instruction limited to that session (2026-10-02 15:34: "then do not start a new code task"). It conflicts with the
   §0 rules "owner decisions do not stop the whole project" and "sequential execution", and with the owner directive
   of 2026-10-03. The §2.2 row `P7-01..P7-08 | PLANNED` gives no scope, which is the same internal conflict ADR-0005,
   ADR-0007 and ADR-0008 resolved.
2. P7 targets one of the weaknesses NAWA exists for (ADR-0003, AGENTS.md §1): weak memory and weak learning from
   mistakes. G7 asks that "memory does not leak data and does not change facts without provenance". P7-06 states that
   changing knowledge stays in updatable and deletable retrieval or memory, not in weights.
3. Parts of P7 need no trained model, no real data and no external service, and can be built now and tested
   deterministically:
   - a memory store with the five kinds named in P7-05 (working, episodic, semantic, procedural, personal/project),
     provenance on every item, deterministic consolidation rules, forgetting and deletion with an audit trail, and
     isolation between synthetic users and projects;
   - the memory test suite of P7-08;
   - the P7-06 rule as an enforced check: a fact marked as changing is accepted only by memory or retrieval and is
     refused by any training-data manifest;
   - an expert specification schema and registry (P7-02: objective, data, tests, limits, invocation rule);
   - router machinery over registered experts with a documented core-only fallback (P7-03), and an isolation-test
     harness that re-runs earlier experts' checks after an expert is added (P7-04), both with deterministic stub
     experts.
4. Other parts of P7 cannot be done honestly now:
   - **Adapters or trained experts (P7-01)** need a trained core (G5) and real licensed data (OD-03).
   - **"Each adapter improves its domain" and "no general degradation beyond T5"** are measured on trained adapters.
   - **Upload to `nawa-adapters` (P7-07)** needs trained adapters, a weights license (OD-03) and the release rules.
   - **Memory built from real conversations or real personal data** needs a privacy policy that no decision covers
     yet: what is stored, where, for how long, with what consent, how it is deleted, and who can read it. Changing the
     privacy or permission policy is an owner decision (owner directive of 2026-10-03; AGENTS.md §13 on data rights
     and permissions). Model-driven extraction or consolidation also
     needs a NAWA model (G5) or an authorized external model (OD-10).

## Decision

- **D1. Split the status row** `P7-01..P7-08` into eight rows, and add three subtasks P7-03a, P7-04a and P7-05a for the
  parts that need a trained model, real data or an owner decision (D3). No existing ID changes.
- **D2. Code-only now (PLANNED, unblocked):** P7-02, P7-03, P7-04, P7-05, P7-06 and P7-08, under these limits:
  - **Track S:** code inside `src/nawa/` (a new package `memory`, and `experts` for P7-02..P7-04), written from scratch,
    with no external model, tokenizer or hub library. The first task that creates a package extends the import rule of
    ADR-0007 D4 and the no-model/no-network rule of ADR-0008 to it, with a negative control.
  - **No external model** of any kind, as generator, extractor, summarizer, judge or reviewer (OD-10).
  - **No network.** Memory is local files or in-process state under a directory the test chooses.
  - **No real data:** synthetic users, projects and facts with invented names, made by code. No real user data, no
    secrets, no `frozen` split. No upload to HF.
  - **Privacy by construction:** every read and write names a user and a project; a read can never return another
    user's item; deletion removes the item from every index and leaves only a tombstone with id, time and reason, not
    the content; every item has provenance (source, time, author, evidence reference). Each rule has a negative test.
  - **CPU only,** inside the existing budget guard (`cpu_local`).
  - **Pass/fail correctness criteria registered before any run,** with negative controls, as in ADR-0007 D2 and
    ADR-0008 D2. Examples: correct recall of stored items; no recall after deletion; zero cross-user results over an
    exhaustive set of synthetic pairs; a fact changed without provenance is refused; consolidation is deterministic
    and keeps the provenance of each merged item; the router falls back to core-only when no expert qualifies; adding
    a stub expert that breaks an earlier one is detected by the isolation harness.
  - **Experts are stubs:** wherever P7 needs an expert or adapter, it is a declared interface tested with deterministic
    stub experts, including one that is wrong on purpose. Results with stubs show that the machinery is correct. They
    never show that an adapter improves its domain.
  - **Records:** every run uses the experiment record with `data_kind: synthetic` (the first P7 task that records a run
    extends the `nawa.experiments` validator to P7 code tasks under the same rules). Every claim is of type
    `correctness` or `evidence`, and none is an improvement claim.
  - **Fixed numbers stay fixed:** no target or gate number in `eval/targets.yaml` or `SUCCESS_CRITERIA.md` changes.
  - **Reuse:** `nawa.routing` (P6-06), `nawa.retrieval` (P6-01, including freshness metadata), `nawa.verification`
    states (P6-08) and `nawa.atlas` are reused, not copied. P7-03 builds on the P6-06 router; it does not write a
    second query router.
- **D3. BLOCKED** (kept as rows so nothing is lost when a code task closes on synthetic evidence):
  - **P7-01:** adapters or trained experts. Blocked on G5 and OD-03.
  - **P7-03a:** routing quality between the core and trained experts. Blocked on P7-01.
  - **P7-04a:** isolation measured on trained adapters (adding an adapter does not break the earlier ones, and no
    general degradation beyond T5). Blocked on P7-01.
  - **P7-05a:** memory built from real conversations or real personal or project data, and model-driven extraction or
    consolidation. Blocked on a new owner decision **OD-12** (personal memory privacy policy) and on G5, or on OD-10
    for an external model.
  - **P7-07:** upload of adapters to `nawa-adapters`. Blocked on P7-01 and OD-03.
- **D4. No quality claim.** No P7 result under this ADR supports a statement that NAWA remembers better, learns from
  mistakes, or that any expert improves its domain. G7 keeps all four conditions and gains one: P7-01, P7-03a, P7-04a,
  P7-05a and P7-07 are done, and OD-12 is decided before any personal memory holds real user data. G7 cannot close on
  stub evidence, and cannot close before G0–G6 (§0).
- **D5. Execution order** (dependencies, IDs unchanged):
  1. **P7-05:** the memory store, kinds, provenance, consolidation, forgetting and deletion.
  2. **P7-08:** the memory test suite (recall, forgetting and deletion, no cross-user leakage, provenance).
  3. **P7-06:** the changing-knowledge rule as an enforced check.
  4. **P7-02:** the expert specification schema and registry.
  5. **P7-03:** router machinery over experts, on top of P6-06, with a core-only fallback and rollback.
  6. **P7-04:** the isolation-test harness.

## Consequences

- The next agent has an executable task (P7-05) without waiting for an owner decision.
- G7 keeps all its conditions and gains one, so no gate is weakened. A test checks the split, the BLOCKED rows, the G7
  conditions and OD-12.
- **OD-12** is added to ROADMAP §2.4 as OPEN. It blocks only P7-05a.

## Alternatives rejected

- **Keep P7 fully PLANNED until G5, as R-09 wrote.** Rejected: it stops all independent work, against §0 and the owner
  directive of 2026-10-03, although memory and routing machinery need no model.
- **Open P8, P9 or P10 code work instead.** Rejected for now: P7 comes first in roadmap order, and its memory part
  serves G7 directly. Those phases are scoped by later ADRs when their turn comes.
- **Store real conversations as memory now.** Rejected: no privacy decision covers it (OD-12), and the owner directive of
  2026-10-03 makes privacy policy an owner decision.
- **Use an external LLM to extract or consolidate memories now.** Rejected: OD-10 is open.
