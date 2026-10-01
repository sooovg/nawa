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
