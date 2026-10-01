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

## Independent verification (P2-02)

`python data_pipeline/atlas/verify.py check <candidates.jsonl> --out <results.jsonl>` (implementation:
`src/nawa/data_verify.py`, settings: `configs/verification.yaml`). Four methods: `calculation` (exact safe
arithmetic), `execution` (sandboxed code with tests by someone other than the producer), `licensed_source`
(answer inside a verbatim quote from a sha256-pinned source whose license is approved; **no license is approved
until OD-03**), and `expert_review` (a named `human:` reviewer who is not the producer; a model is never the expert).
Results are `verified`, `rejected`, or `unverified`. `train_eligibility()` keeps everything out of training while G2 is
not DONE, and always for dev/calib/frozen items and frozen content hashes (ADR-0005 D2).

## Cleaning pipeline (P2-05)

`python -m nawa.data.pipeline run <in.jsonl> --out-dir <new dir>` (code: `src/nawa/data/`, settings:
`configs/data_pipeline.yaml`). Steps: clean (NFC, presentation forms, bidi/zero-width/control removal, tatweel;
diacritics and ZWNJ kept) → PII redaction to typed placeholders (email, phone, IBAN mod-97, card Luhn, Saudi ID
checksum, IPv4, tokens; spans never carry the value) → language tag and rule-based quality score → license
(single approved list in `configs/verification.yaml`, empty until OD-03) → decontamination (8-gram overlap with
dev/calib rebuilt from code, frozen item hashes, optional hashed n-gram index from the Eval role — P2-05a) →
exact + MinHash/LSH near dedup confirmed by exact Jaccard → provenance stamp with the G2 fields. Every input ends
in `kept.jsonl` or `dropped.jsonl` (id + reason, no text). Output is never train-eligible; P2-02 decides that.
Person names and addresses are not detected by these rules.

## Abstention twins (P2-03)

`python -m nawa.data.twins build --n <pairs> --seed <s> --out <new file>` (code: `src/nawa/data/twins.py`).
Each pair shares one question: the answerable twin keeps the evidence sentence and its target answers and cites
it; the unanswerable twin removes only that sentence and its target says `غير موجود في السياق` plus what is missing.
A distractor entity with the asked attribute stays in both. `check_pair` enforces all of this and the CLI refuses to
write a malformed pair. Twins use fictional ships, their own templates and system prompt, and names built only from
consonants absent from the evaluation generator, so they share no name and no 8-gram with dev/calib. Records are
never `train_eligible`; P2-02's methods do not yet cover synthetic-by-construction data.
