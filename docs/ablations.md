# NAWA — P4 ablations register (ROADMAP P4-07, ADR-0007)

Every P4 experiment is listed here, including failures. A row points to its record in `experiments/log.jsonl`
(validated by `python -m nawa.experiments validate`).

Rules (ADR-0007):

- `data_kind = synthetic` rows are **evidence only**. They never support an improvement or adoption claim; the
  validator rejects such a claim.
- No technique is adopted from this table. Adoption is the ROADMAP §4 "technical decision" after an independent gate,
  on real text (P4-02a..P4-05a), after G3.
- No real data before OD-03 is resolved; no artifact upload while P4-08 is BLOCKED.

| Experiment | Task | Technique | data_kind | Registered criteria | Result | What it shows | What it does not show |
|---|---|---|---|---|---|---|---|
| EXP-0024 | P4-06 | none (record pipeline) | synthetic | rerun identical, finite loss, loss decreased; validator: legacy log valid, valid records accepted, 22 violation types detected, append refuses invalid | PASSED (all = 1.0 / true) | The P4 record is enforced by re-derivation and the pipeline is deterministic | Anything about model quality or any technique |
| EXP-0025 | P4-05 | KV cache; greedy speculative decoding (draft 1 layer, k = 1, 2, 4); `torch.compile` | synthetic | logits within 1e-4 of the reference; greedy, sampled, cropped and speculative tokens identical (rate 1.0); compile available | PASSED: max diff 4.8e-6 (KV) and 1.9e-6 (compile); all token rates 1.0; seed 7 also passes (not recorded as a row) | The three paths compute the reference function on the tested configs (RoPE+GQA, learned+GELU+LayerNorm+bias) | Speed at NAWA scale: 1.4–1.5x for KV cache and 20–24% fewer target calls for speculative decoding are tiny-CPU evidence only. Draft acceptance is low (9–27%) |
| EXP-0025 | P4-05 | weight sharing (4→2 unique blocks), low-rank MLP (r = 4), magnitude sparsity 50% | synthetic (random init) | exact parameter counts; full-rank factorisation within 1e-4; exact sparsity; zero sparsity identical; 0 causality violations; gradients ok | PASSED: parameters 51,392 → 26,176 (shared) / 23,360 (low-rank); 16,896 non-zero MLP weights at 50% | The variants are implemented correctly | Their effect on quality: P4-05a (BLOCKED, OD-03) |
| EXP-0026 | P4-03 | ternary `{-1, 0, +1}` (per-row absmean) and symmetric 4-bit (per-row absmax, codes −7..7) block linears, straight-through QAT from the same init and batches; packed export (2 and 4 bits per weight + fp32 row scales) | synthetic | codes in their value sets, all three ternary values used, int4 re-quantization idempotent, forward = codes·scale exactly, STE gradient diff = 0, pack round-trip exact, packed logits within 1e-4, byte formula exact, 0 causality violations, gradients ok, fallback-rule cases, reference config unchanged; held-out loss ≤ H1 − 0.10 for both QAT variants | PASSED (15/15): STE diff 0.0; packed max diff 9.7e-6; margins below H1 0.614 (ternary) and 0.744 (int4); seed 7 also passes (not recorded as a row) | Both quantizers, the STE and the packed export are implemented correctly, and both QAT variants learn the order-2 source (they use the two-symbol context) | Whether ternary or 4-bit is good enough for NAWA: P4-03a (BLOCKED, OD-03, P3-03) |
| EXP-0026 | P4-03 | same run: comparison with the full-precision reference trained identically (102,528 parameters, 1,500 steps) | synthetic | none (evidence only, ADR-0007 D2) | held-out loss fp 2.542, int4 2.570 (+0.028), ternary 2.700 (+0.158); block-linear bytes fp32 401,408 → int4 55,552 (7.2×) / ternary 30,464 (13.2×); the pre-registered fallback rule (gap ≤ 0.10 nats) returns `int4` | On this tiny synthetic task ternary loses more than the registered margin and the rule falls back to 4-bit; memory ratios follow the closed form | Any ranking or adoption. The gap is from one 2-layer model, one source, one seed, no tuning for ternary; embeddings and lm_head stay fp32 |
