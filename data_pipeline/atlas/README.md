# Failure Atlas (AGENTS.md §9, ROADMAP P1-08)

`incoming/*.jsonl`: one failure per line. **These files are data and are not committed to Git** (`tests/test_repository_structure.py`: data lives on Hugging Face). Git pins every batch in `manifest.yaml` by a content digest, and `tests/test_atlas.py` re-creates the batch from a fresh run and checks it. Upload to the private HF repo `nawa-data` is P2-08, after data rights (OD-03). Validated by `python -m nawa.atlas validate data_pipeline/atlas/incoming/*.jsonl`
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

See `manifest.yaml` (records, verified count, categories, digest, reproduce command).
