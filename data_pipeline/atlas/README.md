# Failure Atlas (AGENTS.md §9, ROADMAP P1-08)

`incoming/*.jsonl`: one failure per line, validated by `python -m nawa.atlas validate data_pipeline/atlas/incoming/*.jsonl`
(also run by `tests/test_atlas.py`). Files are append-only: a new batch is a new file, and an existing file is never overwritten.

## Record fields

The AGENTS.md §9 fields (`category`, `prompt`, `bad_output`, `model`, `model_revision`, `verified_truth`, `verification_method`,
`source`, `license`, `reviewer`, `status`) plus provenance: `id` (`ATL-` + hash of model, item, and output), `secondary_categories`,
`run_id`, `split`, `suite`, `item_id`, `content_hash`, `git_commit`, `train_eligible`, `train_block_reason`, `created_utc`, `scorer_default_category` (the suite scorer's category before abstention attribution; traceability only, not a secondary category).

## Rules

- `category` must be an FT id from `docs/failure_taxonomy.md`. A failure with no id is refused, not guessed.
- `verified` means an independent deterministic check: the suite's reference answer is re-scored as correct and the bad output as wrong.
  `reviewer` says `automated:deterministic-scorer` because no human has reviewed these records yet.
- **Records derived from evaluation items are never training-eligible** (`train_eligible: false`). Training on them would leak the
  evaluation set. `content_hash` lets P2-05 exclude them during decontamination. They are useful as regression tests and as failure statistics.
- The frozen split is refused: its items are private (P1-03).

## Batches

| file | model | split | records | verified | categories | reproduce |
|---|---|---|---|---|---|---|
| `2026-09-30-dev-always-abstain.jsonl` | `always_abstain` (NAWA trivial reference, P1-07) | dev | see ROADMAP §2.3 P1-08 | all | FT-13 | `python eval/run_eval.py --model always_abstain --split dev` then `python -m nawa.atlas ingest --run eval/runs/<run_id> --out <file> --created-utc <ts>` |
