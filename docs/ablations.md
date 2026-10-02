# NAWA — P4 ablations register (ROADMAP P4-07, ADR-0007)

Every P4 experiment is listed here, including failures. A row points to its record in `experiments/log.jsonl`
(validated by `python -m nawa.experiments validate`).

Rules (ADR-0007):

- `data_kind = synthetic` rows are **evidence only**. They never support an improvement or adoption claim; the
  validator rejects such a claim.
- No technique is adopted from this table. Adoption is the ROADMAP §4 "technical decision" after an independent gate,
  on real text (P4-02a..P4-05a), after G3.
- No real data before OD-03 is resolved; no artifact upload while P4-08 is BLOCKED.

## Status at P4-07 closure (2026-10-02)

P4-07 is closed: its condition (P4-02..P4-05 done, ADR-0007) is met, and every P4 record is listed below. This register
stays open for appends: every later P4 experiment (P4-01, P4-02a..P4-05a, P4-08) must add its rows here, including
failures. A test (`tests/test_ablations_register.py`) checks that the index below equals the P4 records in
`experiments/log.jsonl`.

**Nothing is adopted.** Every result below comes from small models on synthetic sources (an order-2 Markov source and a
random-init model). It is preliminary evidence that the code is correct and runs, not evidence that a technique is
better for NAWA. In particular, attention, convolution and the attention/convolution hybrid (P4-04, EXP-0028) are
**not** adopted, and no attention:convolution ratio is chosen. The reference core default config is unchanged
(`configs/base_model.yaml`, `config_hash` `918f4cf4877c0cca`, enforced by a test).

**Not started, by rule:** no real-text comparison (P4-01, P4-02a..P4-05a) and no upload of data or weights to Hugging
Face (P4-08) before OD-03 (license of future weights and data) is resolved by the owner. No external model was used for
review (OD-10 open, `ModelRegistry` empty).

### Index of every P4 record

Generated from `experiments/log.jsonl` (schema `p4-record/v1`). Legacy records EXP-0001..EXP-0023 belong to other phases
(P1, P2, P3, R-*) and are not P4 ablations.

| Experiment | Task | Status | Passed | Criteria | data_kind | Seed | Steps | GPU h | Cost USD | config_hash | git_commit | Artifact | Reproduce |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| EXP-0024 | P4-06 | PASSED | true | 7 | synthetic | 42 | 150 | 0 | 0 | `30fb8b8dd3745e51` | `87ad308` | none | `python -m nawa.experiments record-p4-06 --seed 42 --dry-run` |
| EXP-0025 | P4-05 | PASSED | true | 13 | synthetic | 42 | 900 | 0 | 0 | `f76285c34a004a0b` | `3c442f8` | none | `python -m nawa.efficiency.p4_05 --seed 42 --dry-run` |
| EXP-0026 | P4-03 | PASSED | true | 15 | synthetic | 42 | 4500 | 0 | 0 | `70c4c6f78cce735f` | `b0420a0` | none | `python -m nawa.efficiency.p4_03 --seed 42 --dry-run` |
| EXP-0027 | P4-02 | PASSED | true | 16 | synthetic | 42 | 4500 | 0 | 0 | `27370e3f7d5f28f8` | `1d8e66e` | none | `python -m nawa.efficiency.p4_02 --seed 42 --dry-run` |
| EXP-0028 | P4-04 | PASSED | true | 15 | synthetic | 42 | 4500 | 0 | 0 | `88d01a41acfd15cc` | `49628b2` | none | `python -m nawa.efficiency.p4_04 --seed 42 --dry-run` |

### Technique status

| Technique | Code task | Correctness (synthetic) | Preliminary synthetic evidence | Adoption | Governing comparison |
|---|---|---|---|---|---|
| Experiment record + validator | P4-06 | PASSED, EXP-0024 | pipeline deterministic; 22 violation types detected | infrastructure, in use for every P4 run (not a model technique) | none needed |
| KV cache | P4-05 | PASSED, EXP-0025 (logits within 1e-4 of recomputation) | exact equivalence, so no quality effect is expected | NOT ADOPTED (inference path for P8-04) | P8-04 |
| Greedy speculative decoding | P4-05 | PASSED, EXP-0025 (tokens identical to the target model) | low draft acceptance with a 300-step draft | NOT ADOPTED | P8-04 |
| `torch.compile` | P4-05 | PASSED, EXP-0025 (within 1e-4) | none | NOT ADOPTED | P8-04 |
| Weight sharing, low-rank MLP, magnitude sparsity | P4-05 | PASSED, EXP-0025 (exact counts, factorisation, sparsity) | random-init model only, no quality measured | NOT ADOPTED | P4-05a (BLOCKED: OD-03, P3-03) |
| Ternary and symmetric 4-bit QAT + packed export | P4-03 | PASSED, EXP-0026 | loss gap vs fp: int4 +0.028, ternary +0.158 | NOT ADOPTED | P4-03a (BLOCKED: OD-03, P3-03) |
| Sparse MoE and MoE hybrid | P4-02 | PASSED, EXP-0027 | loss vs Dense: MoE −0.034, hybrid −0.027 | NOT ADOPTED | P4-02a (BLOCKED: OD-03, P3-03) |
| Convolution mixer and attention/convolution hybrid | P4-04 | PASSED, EXP-0028 | loss vs attention: convolution −0.035, hybrid −0.047; the source needs only 2 symbols of context, so it cannot show what attention adds | NOT ADOPTED, no ratio chosen | P4-04a (BLOCKED: OD-03, P3-03) |
| Scaling curves | P4-01 | not run (BLOCKED) | none | — | P4-01 (BLOCKED: OD-03, P2-06..P2-08, P3-03) |

### What failed or was amended

No registered P4 run failed its criteria. These defects were found during development, fixed and documented before
the registered run (records are append-only; nothing was deleted):

| Task | What failed | Fix | Criteria changed? | Reference |
|---|---|---|---|---|
| P4-06 | first record attempt (not committed) said `git_dirty: false` with `experiments.py` untracked | `git_state` counts untracked files; record re-created | no | EXP-0024 `failure_cases` |
| P4-06 | weight-hash reproducibility test would fail across Python/torch versions in CI | match data/config hashes and parameter count exactly, loss within 1e-3, weight hash only in the recorded environment | no | ROADMAP §2.3 P4-06 |
| P4-06 | validator benchmark written by the same agent as the validator | recorded limitation, no independent review (OD-10 open) | no | EXP-0024 `failure_cases` |
| P4-05 | three UserWarnings in `test_efficiency.py` | fixed in the tests (`no_grad`/`detach`), no `src` change | no | ROADMAP §2.3 P4-05 |
| P4-02 | dispatch-path causality "violation" of 1.5e-8 (float32 rounding when a later token changes an expert's row count) | `moe_causality_violations == 0` replaced by exact causality on the dense path plus dispatch diff ≤ TOL; strict count kept as evidence | yes, documented before the run (`1d8e66e`) | ROADMAP §2.3 P4-02 |
| P4-04 | surgery probe required replaced keys to be absent, but `ConvMixer` reuses the name `o_proj` | probe skips the replaced prefix, checks module types and every other key | no (probe only, `49628b2`) | ROADMAP §2.3 P4-04 |
| P4-04 | reference/streaming probe used std 0.5 parameters (outputs ~495, diff 4.6e-5 absolute, 6e-8 relative) | parameters at std 1/sqrt(fan_in); max output recorded | no (probe only, `49628b2`) | ROADMAP §2.3 P4-04 |

### Experiment details

| Experiment | Task | Technique | data_kind | Registered criteria | Result | What it shows | What it does not show |
|---|---|---|---|---|---|---|---|
| EXP-0024 | P4-06 | none (record pipeline) | synthetic | rerun identical, finite loss, loss decreased; validator: legacy log valid, valid records accepted, 22 violation types detected, append refuses invalid | PASSED (all = 1.0 / true) | The P4 record is enforced by re-derivation and the pipeline is deterministic | Anything about model quality or any technique |
| EXP-0025 | P4-05 | KV cache; greedy speculative decoding (draft 1 layer, k = 1, 2, 4); `torch.compile` | synthetic | logits within 1e-4 of the reference; greedy, sampled, cropped and speculative tokens identical (rate 1.0); compile available | PASSED: max diff 4.8e-6 (KV) and 1.9e-6 (compile); all token rates 1.0; seed 7 also passes (not recorded as a row) | The three paths compute the reference function on the tested configs (RoPE+GQA, learned+GELU+LayerNorm+bias) | Speed at NAWA scale: 1.4–1.5x for KV cache and 20–24% fewer target calls for speculative decoding are tiny-CPU evidence only. Draft acceptance is low (9–27%) |
| EXP-0025 | P4-05 | weight sharing (4→2 unique blocks), low-rank MLP (r = 4), magnitude sparsity 50% | synthetic (random init) | exact parameter counts; full-rank factorisation within 1e-4; exact sparsity; zero sparsity identical; 0 causality violations; gradients ok | PASSED: parameters 51,392 → 26,176 (shared) / 23,360 (low-rank); 16,896 non-zero MLP weights at 50% | The variants are implemented correctly | Their effect on quality: P4-05a (BLOCKED, OD-03) |
| EXP-0026 | P4-03 | ternary `{-1, 0, +1}` (per-row absmean) and symmetric 4-bit (per-row absmax, codes −7..7) block linears, straight-through QAT from the same init and batches; packed export (2 and 4 bits per weight + fp32 row scales) | synthetic | codes in their value sets, all three ternary values used, int4 re-quantization idempotent, forward = codes·scale exactly, STE gradient diff = 0, pack round-trip exact, packed logits within 1e-4, byte formula exact, 0 causality violations, gradients ok, fallback-rule cases, reference config unchanged; held-out loss ≤ H1 − 0.10 for both QAT variants | PASSED (15/15): STE diff 0.0; packed max diff 9.7e-6; margins below H1 0.614 (ternary) and 0.744 (int4); seed 7 also passes (not recorded as a row) | Both quantizers, the STE and the packed export are implemented correctly, and both QAT variants learn the order-2 source (they use the two-symbol context) | Whether ternary or 4-bit is good enough for NAWA: P4-03a (BLOCKED, OD-03, P3-03) |
| EXP-0026 | P4-03 | same run: comparison with the full-precision reference trained identically (102,528 parameters, 1,500 steps) | synthetic | none (evidence only, ADR-0007 D2) | held-out loss fp 2.542, int4 2.570 (+0.028), ternary 2.700 (+0.158); block-linear bytes fp32 401,408 → int4 55,552 (7.2×) / ternary 30,464 (13.2×); the pre-registered fallback rule (gap ≤ 0.10 nats) returns `int4` | On this tiny synthetic task ternary loses more than the registered margin and the rule falls back to 4-bit; memory ratios follow the closed form | Any ranking or adoption. The gap is from one 2-layer model, one source, one seed, no tuning for ternary; embeddings and lm_head stay fp32 |
| EXP-0027 | P4-02 | Sparse MoE (`SparseMoE`: linear router, softmax, top-2 of 4 experts, renormalised gates, Switch-style load-balance loss ×0.01, no capacity limit) in every block, and Hybrid (MoE in block 1 only), against the Dense reference; experts of width 88 = the dense MLP width 176 / top-k | synthetic | totals, per-token active parameters and FLOPs match closed forms (active parameters measured by one-token gradients, FLOPs by hooks); dispatch = dense masked reference within 1e-5; one expert and four equal experts reproduce the dense model; top-k × tokens assignments; batch invariance; exact causality on the dense path, dispatch within 1e-5; gradients; load-balance loss; reference config unchanged; held-out loss ≤ H1 − 0.10 for all three | PASSED (16/16): dispatch diff 4.8e-7; identities 0.0 and 1.2e-7; batch invariance 1.2e-7; dense-path causality 0, dispatch 4.8e-7 (2 strict float32 differences, evidence); margins below H1 0.772 / 0.806 / 0.799; seed 7 also passes (not recorded as a row) | Routing, dispatch and accounting are correct, and the three variants learn the order-2 source | Which layout NAWA should use: P4-02a (BLOCKED, OD-03, P3-03) |
| EXP-0027 | P4-02 | same run: Dense 102,528 params; MoE 170,624 total / 103,040 active; Hybrid 136,576 / 102,784; 1,500 steps each, same init and batches | synthetic | none (evidence only, ADR-0007 D2) | held-out loss Dense 2.542, MoE 2.508 (−0.034), Hybrid 2.515 (−0.027); seed 7: 2.563 / 2.522 / 2.524; FLOPs/token at context 64: 237,184 / 238,208 / 237,696; fp32 parameter bytes 410,112 / 682,496 / 546,304; no dead expert, expert share 0.21–0.33. CPU latency in the EXP-0027 record is invalid (measured while other test processes ran); a clean seed-7 dry run gave 4.9 / 4.8 / 3.9 ms median per batch of 8×64, i.e. noise at this size | MoE and Hybrid have 1.33–1.66× the total parameters of Dense at about equal active parameters and FLOPs; the small loss gap does not separate capacity from routing | Any ranking or adoption, any latency or memory claim. Parameter bytes are weights only, not runtime memory (activations, KV cache, optimizer state); one 2-layer model, one source, two seeds |
| EXP-0028 | P4-04 | gated causal depthwise convolution mixer (`ConvMixer`: `o_proj(conv(v) * silu(g))`, kernel 4, shifted-sum form) replacing attention in every block (ratio 0:2), and a hybrid (convolution in block 0, attention in block 1, ratio 1:1), against the attention reference; MLPs unchanged | synthetic | parameter counts and FLOPs match closed forms (FLOPs by hooks on every Linear and convolution); shifted-sum = independent `conv1d` path within 1e-5; streaming state = full forward within 1e-5; delta kernel reproduces the projections within 1e-6; 0 causality violations; exact receptive field L·(K−1) (0 violations beyond it, reached at its edge); batch invariance; surgery leaves every other weight identical; gradients; reference config unchanged; held-out loss ≤ H1 − 0.10 for all three | PASSED (15/15): conv vs conv1d 1.4e-6; streaming 9.5e-7; delta identity 0.0; causality 0; receptive field 0 violations and reached; batch invariance 0.0; margins below H1 0.772 / 0.807 / 0.819; seed 7 also passes (not recorded as a row) | The convolution, its streaming form and the layout surgery are correct, and the three layouts learn the order-2 source | Which layout or ratio NAWA should use: P4-04a (BLOCKED, OD-03, P3-03) |
| EXP-0028 | P4-04 | same run: attention 102,528 params; convolution 94,848; hybrid 98,688; 1,500 steps each, same init and batches | synthetic | none (evidence only, ADR-0007 D2) | held-out loss attention 2.542 (identical to the EXP-0027 Dense run, same seed, init and batches), convolution 2.507 (−0.035), hybrid 2.495 (−0.047); seed 7: 2.563 / 2.517 / 2.508; FLOPs/token at context 64: 237,184 / 189,056 / 213,120, and at 1,024 by formula 728,704 / 189,056 / 458,880; decoding state per sequence at context 1,024 by formula 262,144 / 384 / 131,264 floats; CPU latency 2.9 / 2.7 / 2.3 ms median per batch of 8×64 (noise at this size) | Convolution layers cost the same at every context length and keep a fixed K−1 state, while attention cost and KV cache grow with context; on this source both layouts with convolution learn at least as well as attention | Any ranking, ratio or adoption. An order-2 Markov source needs only two symbols of context, which a 2-layer kernel-4 convolution (receptive field 6) already covers, so the source cannot show what attention adds; one 2-layer model, one source, two seeds; state floats are not runtime memory |
