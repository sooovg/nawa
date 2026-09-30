# eval/reports — aggregate reports only (no item text)

## SUPERSEDED: P1-04 open-weight runs (2026-09-30)

The three reports below come from the cancelled optional P1-04 experiment. The owner cancelled P1-04 (ADR-0003):
NAWA's goal is to build an original system, not to compare models, and no external baseline is a condition for any gate.

The reports are kept **unmodified** (AGENTS.md §2.2: no result is deleted). They are **not** used in any target, gate, or
ROADMAP status, and they are not a reference for T1–T6. Their justifications are in `configs/model_registry.yaml`
(status `superseded`), and their log entries are EXP-0001..EXP-0003 (superseded by EXP-0005).

| report | model | status |
|---|---|---|
| `dev-smollm2-360m-instruct-20260930T114134Z.json` | HuggingFaceTB/SmolLM2-360M-Instruct | SUPERSEDED |
| `dev-qwen2-5-0-5b-instruct-20260930T115646Z.json` | Qwen/Qwen2.5-0.5B-Instruct | SUPERSEDED |
| `dev-qwen3-0-6b-20260930T121246Z.json` | Qwen/Qwen3-0.6B | SUPERSEDED |
| — (no report; run aborted, EXP-0004) | Qwen/Qwen2.5-1.5B-Instruct | SUPERSEDED |
