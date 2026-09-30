# ADR-0001: Bootstrap open issues and conflicts found during P0

- **Status:** PARTIALLY RESOLVED — see ADR-0002 for the resolution of each item
- **Date:** 2026-09-30
- **Task:** P0-05 / P0-06 (bootstrap)
- **Author:** bootstrap agent

This ADR records issues found while setting up the repository. They were **not fixed silently** (AGENTS.md §13 and ROADMAP.md §7.2). Each one needs an owner decision or a follow-up task.

## C1: GitHub repository visibility is public

- **Found:** `sooovg/nawa` already existed as a **public**, empty repository. The bootstrap instructions asked for a private repository.
- **Action taken:** none. Changing visibility is a permissions change and needs the owner (AGENTS.md §13). The bootstrap content contains no secrets, data, or weights.
- **Decision needed:** keep it public, or make it private.

## C2: Pre-existing Hugging Face repository outside the plan

- **Found:** `vuuuv/nawa` (model, public) already exists and contains only `.gitattributes`. It is not one of the eight repositories in ROADMAP §3.2.
- **Action taken:** left untouched, since deleting an artifact needs an ADR and owner approval.
- **Decision needed:** keep it (and assign a purpose), make it private, or delete it.

## C3: Default files in the `nawa-demo` Space

- **Found:** Creating the `vuuuv/nawa-demo` Space (SDK `static`, private) made Hugging Face add a template `README.md`, `index.html`, and `style.css`. The other seven repositories contain only `.gitattributes`.
- **Action taken:** none. The Space is private, and its content will be replaced under P10-07.

## C4: Task ID ranges in ROADMAP §2.2 do not match the phase task lists in §4

| Row in §2.2 | Tasks listed in §4 |
|---|---|
| `P3-01..P3-10` | P3-01..P3-08 |
| `P4-01..P4-09` | P4-01..P4-08 |
| `P5-01..P5-08` | P5-01..P5-10 |
| `P6-01..P6-08` | P6-01..P6-09 |

- **Action taken:** the ranges were left as written, and no task IDs were renumbered (§2.2 forbids changing used IDs).
- **Proposal:** align the §2.2 ranges to §4 in a ROADMAP PR.

## C5: Gate names in §2.1 do not match the gate definitions in §4

- §2.1 names G1 "the repository and CI", G2 "baseline and evaluation", G3 "data and Atlas", and so on. In §4, however, G0 includes "initial CI works", G1 is closed by P1 (baseline), G2 by P2 (data), and G3 by P3 (tokenizer/core). §4 also defines G10, which does not appear in §2.1.
- **Proposal:** a ROADMAP PR aligning §2.1 to §4 (gate *n* closes phase P*n*) and adding a G10 row.

## C6: Bootstrap scope vs. P0 task list

- P0-04 requires `RISK_REGISTER.md`. The owner's bootstrap instruction limited the initial files to an explicit list that does not include it, so it was **not created**, and P0-04 stays partially done.
- P0-07 (`configs/budget.yaml`) needs owner numbers (GPU hours, cost cap), so it was not created.
- `.github/workflows/ci.yml` and `.github/CODEOWNERS` were added beyond the explicit list for two reasons: branch protection with "require tests to pass" needs a CI check, and ROADMAP §11 step 3 plus P0-08 require them.

## C7: `.gitignore` exception for `experiments/log.jsonl`

- `*.jsonl` is ignored by `.gitignore`, as instructed. However, AGENTS.md §7 and §8 require `experiments/log.jsonl` to be tracked in Git, so an explicit un-ignore rule `!experiments/log.jsonl` was added.

## C8: Push path

- The local sandbox could not authenticate `git push` to github.com. The initial commit was therefore published through the GitHub Git Data API, which reproduces the same commit object, so the SHA is identical. This has no effect on the repository contents.
