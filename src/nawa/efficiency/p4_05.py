"""P4-05 experiment: equivalence of KV cache, greedy speculative decoding and compilation with the reference, and
correctness of weight sharing, low-rank and sparsity (ADR-0007 D2). Synthetic data, CPU, no claim of improvement.

    python -m nawa.efficiency.p4_05 --seed 42 [--dry-run]

``CRITERIA`` below was written and committed to the branch before the first run (tolerances are part of the
pre-registration). Timings and acceptance rates are recorded as evidence only.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from typing import Any

import torch

from nawa import experiments as ex
from nawa.efficiency.compiled import compiled_parity
from nawa.efficiency.kv_cache import KVCache, forward_cached, generate_cached
from nawa.efficiency.speculative import speculative_generate
from nawa.efficiency.structural import (LowRankLinear, MaskedLinear, apply_low_rank, apply_sparsity,
                                        block_parameters, causality_violations, gradient_report, share_layers)
from nawa.model import DecoderConfig, NawaDecoder
from nawa.model.decoder import expected_num_parameters
from nawa.training.sanity import MarkovSource, batches

# ---- pre-registered (before the first run) ------------------------------------------------------------------------
LOGIT_TOL = 1e-4   # float32 logits of order 1-10; reordered sums differ by ~1e-6, so 1e-4 leaves margin and still
                   # catches any real bug (a wrong mask or position offset moves logits by >= 1e-2).
CRITERIA: dict[str, Any] = {
    "kv_max_abs_logit_diff": {"op": "<=", "value": LOGIT_TOL},
    "kv_greedy_token_match_rate": {"op": "==", "value": 1.0},
    "kv_sampled_token_match_rate": {"op": "==", "value": 1.0},
    "kv_crop_token_match_rate": {"op": "==", "value": 1.0},
    "spec_token_match_rate": {"op": "==", "value": 1.0},
    "compile_available": {"op": "==", "value": True},
    "compile_max_abs_logit_diff": {"op": "<=", "value": LOGIT_TOL},
    "structural_param_counts_exact": {"op": "==", "value": True},
    "low_rank_full_rank_max_abs_diff": {"op": "<=", "value": LOGIT_TOL},
    "sparsity_exact": {"op": "==", "value": True},
    "zero_sparsity_identity": {"op": "==", "value": True},
    "structural_causality_violations": {"op": "==", "value": 0},
    "structural_gradients_ok": {"op": "==", "value": True},
}

CONFIG: dict[str, Any] = {
    "targets": {
        "rope_swiglu_gqa": {"vocab_size": 29, "d_model": 64, "n_layers": 2, "n_heads": 4, "n_kv_heads": 2,
                            "max_seq_len": 64},
        "learned_gelu_layernorm_bias": {"vocab_size": 29, "d_model": 48, "n_layers": 2, "n_heads": 4,
                                        "max_seq_len": 64, "positional": "learned", "mlp": "gelu",
                                        "norm": "layernorm", "bias": True, "tie_embeddings": False},
    },
    "draft": {"vocab_size": 29, "d_model": 32, "n_layers": 1, "n_heads": 2, "max_seq_len": 64},
    "train": {"steps": 300, "batch": 32, "seq_len": 64, "lr": 3e-3, "weight_decay": 0.01, "grad_clip": 1.0},
    "data": {"generator": "nawa.training.sanity.MarkovSource", "k": 29, "train_symbols": 100_000,
             "prompt_symbols": 20_000},
    "eval": {"prompts": 16, "prompt_len": [4, 24], "max_new_tokens": 32, "temperature_sampled": 1.0,
             "crop_prompt_len": 50, "crop_new_tokens": 30, "spec_k": [1, 2, 4], "spec_new_tokens": 32,
             "compile_shapes": [[1, 17], [4, 64]]},
    "structural": {"config": {"vocab_size": 29, "d_model": 32, "n_layers": 4, "n_heads": 4, "max_seq_len": 32},
                   "share_n_unique": 2, "low_rank": 4, "sparsity": 0.5},
}


def _train(cfg: DecoderConfig, train: torch.Tensor, seed: int, t: dict[str, Any]) -> NawaDecoder:
    torch.manual_seed(seed)
    model = NawaDecoder(cfg).train()
    opt = torch.optim.AdamW(model.parameters(), lr=t["lr"], weight_decay=t["weight_decay"])
    g = torch.Generator().manual_seed(seed + 3)
    for _ in range(t["steps"]):
        x, y = batches(train, t["seq_len"], t["batch"], g)
        loss = model(x, targets=y).loss
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), t["grad_clip"])
        opt.step()
    return model.eval()


def _prompts(stream: torch.Tensor, n: int, lo: int, hi: int, seed: int) -> list[torch.Tensor]:
    g = torch.Generator().manual_seed(seed)
    out = []
    for _ in range(n):
        length = int(torch.randint(lo, hi + 1, (1,), generator=g))
        start = int(torch.randint(0, len(stream) - length, (1,), generator=g))
        out.append(stream[start:start + length][None])
    return out


@torch.no_grad()
def kv_logit_diff(model: NawaDecoder, prompt: torch.Tensor, new_tokens: int) -> float:
    """Prefill + one-token steps through the cache vs the full forward on the same sequence, every position."""
    seq = model.generate(prompt, new_tokens)
    full = model(seq).logits
    cache = KVCache.empty(model.cfg.n_layers)
    parts = [forward_cached(model, seq[:, :prompt.shape[1]], cache)]
    for i in range(prompt.shape[1], seq.shape[1]):
        parts.append(forward_cached(model, seq[:, i:i + 1], cache))
    return float((torch.cat(parts, dim=1) - full).abs().max())


def _timed(fn, repeats: int = 3) -> float:
    best = math.inf
    for _ in range(repeats):
        t0 = time.perf_counter()
        fn()
        best = min(best, time.perf_counter() - t0)
    return best


def equivalence(seed: int, cfg: dict[str, Any]) -> tuple[dict[str, Any], str]:
    d, t, e = cfg["data"], cfg["train"], cfg["eval"]
    source = MarkovSource.make(k=d["k"], seed=seed)
    train = source.sample(d["train_symbols"], seed=seed + 1)
    stream = source.sample(d["prompt_symbols"], seed=seed + 2)
    data_sha = ex.sha256_bytes(ex._pack_ints(train.tolist()) + b"|" + ex._pack_ints(stream.tolist()))
    prompts = _prompts(stream, e["prompts"], *e["prompt_len"], seed=seed + 4)
    m: dict[str, Any] = {"per_target": {}}
    kv_diff, greedy_ok, sampled_ok, crop_ok, n_greedy, n_sampled, n_crop = 0.0, 0, 0, 0, 0, 0, 0
    targets = {}
    for name, tc in cfg["targets"].items():
        model = _train(DecoderConfig(**tc), train, seed, t)
        targets[name] = model
        diffs = [kv_logit_diff(model, p, e["max_new_tokens"]) for p in prompts]
        g_ok = sum(torch.equal(model.generate(p, e["max_new_tokens"]), generate_cached(model, p, e["max_new_tokens"]))
                   for p in prompts)
        s_ok = 0
        for i, p in enumerate(prompts):
            ga, gb = (torch.Generator().manual_seed(seed + 100 + i) for _ in range(2))
            s_ok += torch.equal(model.generate(p, e["max_new_tokens"], e["temperature_sampled"], ga),
                                generate_cached(model, p, e["max_new_tokens"], e["temperature_sampled"], gb))
        crop_prompts = _prompts(stream, 4, e["crop_prompt_len"], e["crop_prompt_len"], seed=seed + 5)
        c_ok = sum(torch.equal(model.generate(p, e["crop_new_tokens"]), generate_cached(model, p, e["crop_new_tokens"]))
                   for p in crop_prompts)
        p0 = prompts[0]
        no_cache = _timed(lambda: model.generate(p0, e["max_new_tokens"]))
        cached = _timed(lambda: generate_cached(model, p0, e["max_new_tokens"]))
        m["per_target"][name] = {"config_hash": model.cfg.config_hash(), "parameters": model.num_parameters(),
                                 "kv_max_abs_logit_diff": max(diffs), "greedy_match": g_ok, "sampled_match": s_ok,
                                 "crop_match": c_ok, "seconds_no_cache": round(no_cache, 4),
                                 "seconds_cached": round(cached, 4),
                                 "speed_ratio_evidence": round(no_cache / cached, 2)}
        kv_diff = max(kv_diff, max(diffs))
        greedy_ok, sampled_ok, crop_ok = greedy_ok + g_ok, sampled_ok + s_ok, crop_ok + c_ok
        n_greedy, n_sampled, n_crop = n_greedy + len(prompts), n_sampled + len(prompts), n_crop + len(crop_prompts)
    m.update(kv_max_abs_logit_diff=kv_diff, kv_greedy_token_match_rate=greedy_ok / n_greedy,
             kv_sampled_token_match_rate=sampled_ok / n_sampled, kv_crop_token_match_rate=crop_ok / n_crop)
    # speculative decoding: draft trained on the same stream, target = first config
    target = targets["rope_swiglu_gqa"]
    draft = _train(DecoderConfig(**cfg["draft"]), train, seed + 7, t)
    spec_ok, spec_n, per_k = 0, 0, {}
    for k in e["spec_k"]:
        acc, calls, ok = [], 0, 0
        for p in prompts:
            ref = target.generate(p, e["spec_new_tokens"])
            out, st = speculative_generate(target, draft, p, e["spec_new_tokens"], k)
            ok += torch.equal(ref, out)
            acc.append(st.acceptance_rate)
            calls += st.target_calls
        per_k[str(k)] = {"token_match": ok, "mean_acceptance_rate": round(sum(acc) / len(acc), 4),
                         "target_calls_per_token": round(calls / (len(prompts) * e["spec_new_tokens"]), 4)}
        spec_ok, spec_n = spec_ok + ok, spec_n + len(prompts)
    m.update(spec_token_match_rate=spec_ok / spec_n, spec_per_k_evidence=per_k,
             draft_parameters=draft.num_parameters())
    # compilation
    shapes = [torch.randint(0, 29, tuple(s), generator=torch.Generator().manual_seed(seed + 9))
              for s in e["compile_shapes"]]
    comp = compiled_parity(target, shapes)
    m.update(compile_available=comp["available"], compile_max_abs_logit_diff=comp["max_abs_logit_diff"],
             compile_detail=comp)
    return m, data_sha


def structural(seed: int, cfg: dict[str, Any]) -> dict[str, Any]:
    s = cfg["structural"]
    base_cfg = DecoderConfig(**s["config"])
    def fresh() -> NawaDecoder:
        torch.manual_seed(seed)
        return NawaDecoder(base_cfg).eval()
    out: dict[str, Any] = {}
    counts_ok = True
    # sharing
    shared = share_layers(fresh(), s["share_n_unique"])
    exp_shared = expected_num_parameters(base_cfg) - (base_cfg.n_layers - s["share_n_unique"]) * block_parameters(shared)
    counts_ok &= shared.num_parameters() == exp_shared
    # low rank
    lr = apply_low_rank(fresh(), s["low_rank"])
    d, f, r = base_cfg.d_model, base_cfg.resolved_d_ff, s["low_rank"]
    exp_lr = expected_num_parameters(base_cfg) - base_cfg.n_layers * 3 * d * f + base_cfg.n_layers * 3 * r * (d + f)
    counts_ok &= lr.num_parameters() == exp_lr
    ref = fresh()
    full = apply_low_rank(fresh(), min(d, f))
    x = torch.randint(0, base_cfg.vocab_size, (2, base_cfg.max_seq_len), generator=torch.Generator().manual_seed(seed))
    with torch.no_grad():
        out["low_rank_full_rank_max_abs_diff"] = float((full(x).logits - ref(x).logits).abs().max())
        sp = apply_sparsity(fresh(), s["sparsity"])
        masked = [mod for mod in sp.modules() if isinstance(mod, MaskedLinear)]
        sp_exact = all(int((~mod.mask).sum()) == int(round(s["sparsity"] * mod.mask.numel())) for mod in masked)
        zero = apply_sparsity(fresh(), 0.0)
        zero_identity = torch.equal(zero(x).logits, ref(x).logits)
    counts_ok &= sp.num_parameters() == expected_num_parameters(base_cfg)   # masking keeps the dense tensors
    out.update(structural_param_counts_exact=counts_ok, sparsity_exact=sp_exact, zero_sparsity_identity=zero_identity,
               params={"reference": expected_num_parameters(base_cfg), "shared": shared.num_parameters(),
                       "low_rank": lr.num_parameters(), "sparse_nonzero_mlp": sum(int(mod.mask.sum()) for mod in masked)},
               low_rank_modules=sum(isinstance(mod, LowRankLinear) for mod in lr.modules()))
    variants = {"shared": shared, "low_rank": lr, "sparse": sp}
    out["structural_causality_violations"] = sum(causality_violations(v, base_cfg.max_seq_len, seed)
                                                 for v in variants.values())
    grads = {k: gradient_report(v, base_cfg.max_seq_len - 1, seed) for k, v in variants.items()}
    out["gradients"] = grads
    out["structural_gradients_ok"] = all(all(g.values()) for g in grads.values())
    return out


def run(seed: int = 42) -> ex.P4Run:
    from nawa import budget
    decision = budget.check("cpu_local")
    if not decision.allowed:
        raise ex.RecordError(f"budget guard refused the run: {decision.reason}")
    t0 = time.perf_counter()
    metrics, data_sha = equivalence(seed, CONFIG)
    metrics.update(structural(seed, CONFIG))
    metrics["wall_seconds"] = round(time.perf_counter() - t0, 1)
    passed = all(ex.evaluate_criteria(CRITERIA, metrics).values())
    return ex.P4Run(
        task_id="P4-05",
        purpose="P4-05: KV cache, greedy speculative decoding and torch.compile checked for equivalence with the "
                "reference decoder within pre-registered tolerances; weight sharing, low-rank and sparsity checked "
                "for correctness only (they change the model).",
        config=CONFIG, seed=seed, data_sha256=data_sha,
        data_description=f"synthetic: MarkovSource.make(k=29, seed={seed}); train = sample(100000, seed={seed + 1}); "
                         f"prompt stream = sample(20000, seed={seed + 2}); int64 little-endian (struct) hashed",
        criteria=CRITERIA, metrics=metrics, training_steps=CONFIG["train"]["steps"] * 3,
        reproduce=f"python -m nawa.efficiency.p4_05 --seed {seed} --dry-run",
        claims=[{"type": "correctness", "text": "KV cache, greedy speculative decoding and compiled forward match "
                                                "the reference within the registered tolerances on these configs."},
                {"type": "evidence", "text": "Timings and acceptance rates are from tiny CPU models on a synthetic "
                                             "source; they say nothing about speed or quality at NAWA scale."}],
        failure_cases=[],
        conclusion=("Inference paths are equivalent to the reference on the tested configs; structural variants are "
                    "correct (counts, causality, gradients). Nothing adopted (ADR-0007 D4)."
                    if passed else "At least one registered criterion failed; see metrics."),
        next_action="P4-03 (ternary weights with QAT, code-only on synthetic tasks); quality of sharing/low-rank/"
                    "sparsity waits for P4-05a (OD-03).",
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m nawa.efficiency.p4_05")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--dry-run", action="store_true", help="print the record, do not append")
    args = ap.parse_args(argv)
    rec = run(args.seed).build(ex.next_id())
    if not args.dry_run:
        ex.append(rec)
    print(json.dumps(rec, ensure_ascii=False, indent=1))
    return 0 if rec["passed"] else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
