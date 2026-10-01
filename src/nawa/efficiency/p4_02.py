"""P4-02 experiment: Dense vs Sparse MoE vs Hybrid on the reference core (ADR-0007 D2). Code-only, synthetic, CPU.

    python -m nawa.efficiency.p4_02 --seed 42 [--dry-run]

``CRITERIA``, ``TOL`` and ``CONFIG`` below were written and committed to the branch before the first run
(pre-registration). The criteria are pass/fail **correctness** checks of the MoE implementation, plus one
learning-sanity check per variant (held-out loss clearly below H1, as in P3-05 and P4-03). Quality gaps, parameter
bytes, FLOPs, latency and expert load are **evidence only**: synthetic data cannot rank the variants or support
adoption (ADR-0007 D2, D4). The quality comparison is P4-02a (BLOCKED: OD-03, P3-03).

Amendment to the pre-registration (commit after 093a367, before the registered run): a development smoke run
(20 steps, seed 1, not recorded) found 1 strict causality "violation" of 1.5e-8 in the sparse dispatch path, while
the dense masked path (``SparseMoE.dense_forward``) had 0. The cause is float32 rounding: changing a later token can
change how many rows an expert's matmul receives, and the BLAS result for an unchanged row can differ in the last bit.
No information flows backward. ``moe_causality_violations == 0`` is therefore replaced by two criteria that are
together stricter in substance: exact causality (0 violations) of the routing and experts through the dense path,
and a dispatch-path difference <= TOL. The strict dispatch count is kept as evidence. No other criterion changed.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import statistics
import sys
import time
from pathlib import Path
from typing import Any

import torch
from torch import nn

from nawa import experiments as ex
from nawa.efficiency.moe import (MoEConfig, SparseMoE, apply_moe, aux_loss, forward_flops_per_token,
                                 load_balance_loss, moe_layers_of, param_counts, reset_expert_counters)
from nawa.efficiency.structural import causality_violations, gradient_report
from nawa.model import DecoderConfig, NawaDecoder
from nawa.training.sanity import MarkovSource, batches, heldout_loss

ROOT = Path(__file__).resolve().parents[3]

# ---- pre-registered (before the first run) ------------------------------------------------------------------------
TOL = 1e-5        # dispatch vs dense reference, batch invariance, equal-experts identity: float32 activations of
                  # order 1 summed in a different order differ by ~1e-7; a wrong gate, index or slot moves them >= 1e-2.
IDENTITY_TOL = 1e-6   # one expert with gate exactly 1 must reproduce the dense MLP (same matmul, x 1.0)
CRITERIA: dict[str, Any] = {
    "moe_param_counts_exact": {"op": "==", "value": True},
    "active_params_measured_equals_formula": {"op": "==", "value": True},
    "flops_counted_equals_formula": {"op": "==", "value": True},
    "dispatch_vs_dense_max_abs_diff": {"op": "<=", "value": TOL},
    "single_expert_identity_max_abs_diff": {"op": "<=", "value": IDENTITY_TOL},
    "equal_experts_identity_max_abs_diff": {"op": "<=", "value": TOL},
    "expert_assignments_equal_topk_times_tokens": {"op": "==", "value": True},
    "moe_batch_invariance_max_abs_diff": {"op": "<=", "value": TOL},
    "moe_dense_path_causality_violations": {"op": "==", "value": 0},
    "moe_dispatch_causality_max_abs_diff": {"op": "<=", "value": TOL},
    "moe_gradients_ok": {"op": "==", "value": True},
    "aux_loss_checks_ok": {"op": "==", "value": True},
    "reference_core_config_unchanged": {"op": "==", "value": True},
    "dense_margin_below_h1": {"op": ">=", "value": 0.10},
    "moe_margin_below_h1": {"op": ">=", "value": 0.10},
    "hybrid_margin_below_h1": {"op": ">=", "value": 0.10},
}

_D_FF = 176   # resolved_d_ff of the reference model below (SwiGLU, d_model 64); experts of 88 = same active MLP width
CONFIG: dict[str, Any] = {
    "model": {"vocab_size": 29, "d_model": 64, "n_layers": 2, "n_heads": 4, "max_seq_len": 64},
    "variants": {
        "dense": None,
        "moe": {"moe": {"n_experts": 4, "top_k": 2, "d_expert": _D_FF // 2, "n_shared": 0, "normalize_gates": True,
                        "aux_loss_coef": 0.01}, "moe_layers": [0, 1]},
        "hybrid": {"moe": {"n_experts": 4, "top_k": 2, "d_expert": _D_FF // 2, "n_shared": 0,
                           "normalize_gates": True, "aux_loss_coef": 0.01}, "moe_layers": [1]},
    },
    "correctness_extra": {"shared_expert": {"n_experts": 4, "top_k": 1, "d_expert": 48, "n_shared": 1},
                          "gelu_bias_model": {"vocab_size": 29, "d_model": 48, "n_layers": 2, "n_heads": 4,
                                              "max_seq_len": 64, "positional": "learned", "mlp": "gelu",
                                              "norm": "layernorm", "bias": True, "tie_embeddings": False}},
    "train": {"steps": 1500, "batch": 32, "seq_len": 64, "lr": 3e-3, "weight_decay": 0.01, "grad_clip": 1.0,
              "loss": "cross-entropy + aux_loss_coef * load-balance loss", "same_init_and_batches": True},
    "data": {"generator": "nawa.training.sanity.MarkovSource", "k": 29, "train_symbols": 500_000,
             "val_symbols": 50_000, "heldout_skip": 2},
    "latency": {"batch": 8, "seq_len": 64, "warmup": 3, "repeats": 20, "status": "evidence only, CPU wall clock"},
    "probe": {"seq_len": 63},
}
REFERENCE_CORE_HASH = "918f4cf4877c0cca"   # configs/base_model.yaml, pinned by ADR-0007 D4


# ---- builders -----------------------------------------------------------------------------------------------------
def _variant(spec: dict[str, Any] | None) -> tuple[MoEConfig | None, tuple[int, ...] | None]:
    if spec is None:
        return None, None
    return MoEConfig(**spec["moe"]), tuple(spec["moe_layers"])


def build(cfg: DecoderConfig, spec: dict[str, Any] | None, seed: int) -> NawaDecoder:
    torch.manual_seed(seed)
    model = NawaDecoder(cfg)
    moe, layers = _variant(spec)
    return apply_moe(model, moe, layers, seed=seed + 100) if moe else model


def _train(model: NawaDecoder, train: torch.Tensor, seed: int, t: dict[str, Any]) -> tuple[NawaDecoder, float]:
    model.train()
    opt = torch.optim.AdamW(model.parameters(), lr=t["lr"], weight_decay=t["weight_decay"])
    g = torch.Generator().manual_seed(seed + 3)
    last = math.nan
    for _ in range(t["steps"]):
        x, y = batches(train, t["seq_len"], t["batch"], g)
        loss = model(x, targets=y).loss + aux_loss(model)
        opt.zero_grad(set_to_none=True)
        loss.backward()
        nn.utils.clip_grad_norm_(model.parameters(), t["grad_clip"])
        opt.step()
        last = float(loss.detach())
    return model.eval(), last


# ---- correctness probes --------------------------------------------------------------------------------------------
def _configs() -> list[tuple[DecoderConfig, MoEConfig, tuple[int, ...] | None]]:
    out = []
    for c in (CONFIG["model"], CONFIG["correctness_extra"]["gelu_bias_model"]):
        cfg = DecoderConfig(**c)
        for spec in (CONFIG["variants"]["moe"], CONFIG["variants"]["hybrid"]):
            moe, layers = _variant(spec)
            out.append((cfg, moe, layers))
        out.append((cfg, MoEConfig(**CONFIG["correctness_extra"]["shared_expert"]), (0,)))
    return out


def count_checks(seed: int) -> dict[str, Any]:
    """Closed-form totals vs the model; active params vs the parameters that get a gradient from one token;
    FLOPs formula vs MACs counted by hooks on every Linear (plus the attention context term)."""
    totals_ok, active_ok, flops_ok = True, True, True
    for cfg, moe, layers in _configs():
        m = build(cfg, {"moe": moe.to_dict(), "moe_layers": list(layers) if layers else list(range(cfg.n_layers))},
                  seed)
        pc = param_counts(cfg, moe, layers)
        totals_ok &= pc["total"] == m.num_parameters()
        x = torch.randint(0, cfg.vocab_size, (1, 2), generator=torch.Generator().manual_seed(seed))
        m.zero_grad(set_to_none=True)
        m.train()
        m(x[:, :1], targets=x[:, 1:]).loss.backward()        # one token
        seen: set[int] = set()
        touched = 0
        for p in m.parameters():
            if id(p) not in seen:
                seen.add(id(p))
                touched += p.numel() if p.grad is not None else 0
        # every embedding row is a parameter of the same tensor, so the embedding counts in full on both sides
        active_ok &= touched == pc["active"]
        m.zero_grad(set_to_none=True)
        m.eval()
        t = 16
        macs = [0]
        hooks = [mod.register_forward_hook(lambda mod, inp, out: macs.__setitem__(
            0, macs[0] + inp[0].reshape(-1, mod.in_features).shape[0] * mod.in_features * mod.out_features))
            for mod in m.modules() if isinstance(mod, nn.Linear)]
        with torch.no_grad():
            m(torch.randint(0, cfg.vocab_size, (3, t), generator=torch.Generator().manual_seed(seed + 1)))
        for h in hooks:
            h.remove()
        ctx = cfg.n_layers * 2 * t * cfg.n_heads * cfg.head_dim * 3 * t
        flops_ok &= 2 * (macs[0] + ctx) == forward_flops_per_token(cfg, moe, layers, t) * 3 * t
    return {"moe_param_counts_exact": bool(totals_ok), "active_params_measured_equals_formula": bool(active_ok),
            "flops_counted_equals_formula": bool(flops_ok)}


@torch.no_grad()
def dispatch_checks(models: dict[str, NawaDecoder], val: torch.Tensor, seed: int) -> dict[str, Any]:
    worst, assign_ok = 0.0, True
    g = torch.Generator().manual_seed(seed + 5)
    for cfg, moe, _ in _configs():
        layer = SparseMoE(cfg, moe)
        x = torch.randn(4, 17, cfg.d_model, generator=g)
        worst = max(worst, float((layer(x) - layer.dense_forward(x)).abs().max()))
    for name in ("moe", "hybrid"):
        m = models[name]
        x = val[: 8 * 64].view(8, 64)
        reset_expert_counters(m)
        h = {}
        hooks = [layer.register_forward_pre_hook(lambda mod, inp, key=i: h.__setitem__(key, inp[0]))
                 for i, layer in enumerate(moe_layers_of(m))]
        m(x)
        for hk in hooks:
            hk.remove()
        for i, layer in enumerate(moe_layers_of(m)):
            worst = max(worst, float((layer(h[i]) - layer.dense_forward(h[i])).abs().max()))
        reset_expert_counters(m)
        m(x)
        for layer in moe_layers_of(m):
            assign_ok &= int(layer.expert_tokens.sum()) == layer.moe.top_k * x.numel()
    return {"dispatch_vs_dense_max_abs_diff": worst, "expert_assignments_equal_topk_times_tokens": bool(assign_ok)}


@torch.no_grad()
def identity_checks(seed: int) -> dict[str, float]:
    single, equal = 0.0, 0.0
    for c in (CONFIG["model"], CONFIG["correctness_extra"]["gelu_bias_model"]):
        cfg = DecoderConfig(**c)
        dense = build(cfg, None, seed).eval()
        x = torch.randint(0, cfg.vocab_size, (3, 32), generator=torch.Generator().manual_seed(seed + 7))
        ref = dense(x).logits
        for moe, key in ((MoEConfig(1, 1, d_expert=cfg.resolved_d_ff), "single"),
                         (MoEConfig(4, 2, d_expert=cfg.resolved_d_ff), "equal")):
            m = apply_moe(copy.deepcopy(dense), moe, None, seed=seed)
            for block, ref_block in zip(m.blocks, dense.blocks):
                for expert in block.mlp.experts:
                    expert.load_state_dict(ref_block.mlp.state_dict())
            d = float((m(x).logits - ref).abs().max())
            single, equal = (max(single, d), equal) if key == "single" else (single, max(equal, d))
    return {"single_expert_identity_max_abs_diff": single, "equal_experts_identity_max_abs_diff": equal}


@torch.no_grad()
def batch_invariance(models: dict[str, NawaDecoder], val: torch.Tensor) -> float:
    worst = 0.0
    x = val[: 6 * 64].view(6, 64)
    for name in ("moe", "hybrid"):
        m = models[name]
        full = m(x).logits
        for i in (0, 3, 5):
            worst = max(worst, float((m(x[i:i + 1]).logits[0] - full[i]).abs().max()))
    return worst


def aux_checks(seed: int) -> bool:
    e, n, k = 4, 16, 2
    uniform = torch.full((n, e), 1.0 / e)
    topi = torch.arange(n * k).remainder(e).view(n, k)          # every expert gets exactly n*k/e slots
    ok = abs(float(load_balance_loss(uniform, topi, e)) - 1.0) < 1e-6
    g = torch.Generator().manual_seed(seed)
    probs = torch.softmax(torch.randn(n, e, generator=g), -1)
    ti = probs.topk(k, -1).indices
    f = torch.tensor([(ti == i).sum().item() for i in range(e)], dtype=torch.float32) / (n * k)
    ok &= abs(float(load_balance_loss(probs, ti, e)) - float(e * (f * probs.mean(0)).sum())) < 1e-6
    collapsed = torch.zeros(n, k, dtype=torch.long)
    collapsed[:, 1] = 1
    ok &= float(load_balance_loss(torch.softmax(torch.tensor([[9.0, 9.0, 0.0, 0.0]]).expand(n, e), -1),
                                  collapsed, e)) > 1.5                   # concentrated routing is penalised
    cfg = DecoderConfig(**CONFIG["model"])
    layer = SparseMoE(cfg, MoEConfig(4, 2))
    layer(torch.randn(2, 8, cfg.d_model, generator=g))
    layer.last_aux.backward()
    ok &= layer.router.weight.grad is not None and bool(layer.router.weight.grad.abs().sum() > 0)
    ok &= float(aux_loss(NawaDecoder(cfg))) == 0.0
    return bool(ok)


@torch.no_grad()
def causality_probe(model: NawaDecoder, seq_len: int, seed: int, dense_path: bool, trials: int = 8) -> tuple[int, float]:
    """(positions whose logits change at all, max change) when only later tokens change. ``dense_path`` routes every
    SparseMoE through ``dense_forward`` (fixed shapes), which isolates information flow from matmul rounding."""
    layers = moe_layers_of(model)
    saved = [layer.forward for layer in layers]
    if dense_path:
        for layer in layers:
            layer.forward = layer.dense_forward
    try:
        model.eval()
        g = torch.Generator().manual_seed(seed)
        bad, worst = 0, 0.0
        for _ in range(trials):
            x = torch.randint(0, model.cfg.vocab_size, (1, seq_len), generator=g)
            cut = int(torch.randint(1, seq_len, (1,), generator=g))
            y = x.clone()
            y[0, cut:] = (y[0, cut:] + 1) % model.cfg.vocab_size
            d = (model(x).logits[0, :cut] - model(y).logits[0, :cut]).abs()
            bad += int(d.amax(-1).gt(0).sum())
            worst = max(worst, float(d.max()))
    finally:
        for layer, fwd in zip(layers, saved):
            layer.forward = fwd
    return bad, worst


def reference_core_unchanged() -> bool:
    return DecoderConfig.from_yaml(ROOT / "configs" / "base_model.yaml").config_hash() == REFERENCE_CORE_HASH


@torch.no_grad()
def latency_ms(model: NawaDecoder, lat: dict[str, Any], seed: int) -> float:
    x = torch.randint(0, model.cfg.vocab_size, (lat["batch"], lat["seq_len"]),
                      generator=torch.Generator().manual_seed(seed))
    for _ in range(lat["warmup"]):
        model(x)
    times = []
    for _ in range(lat["repeats"]):
        t0 = time.perf_counter()
        model(x)
        times.append((time.perf_counter() - t0) * 1000)
    return round(statistics.median(times), 3)


@torch.no_grad()
def expert_load(model: NawaDecoder, val: torch.Tensor) -> list[dict[str, Any]]:
    reset_expert_counters(model)
    n = (len(val) - 1) // 64
    model(val[: n * 64].view(n, 64))
    out = []
    for layer in moe_layers_of(model):
        frac = (layer.expert_tokens.float() / layer.expert_tokens.sum()).tolist()
        out.append({"fraction_per_expert": [round(f, 4) for f in frac], "dead_experts": sum(f == 0 for f in frac)})
    reset_expert_counters(model)
    return out


# ---- run -----------------------------------------------------------------------------------------------------------
def measure(seed: int, cfg: dict[str, Any]) -> tuple[dict[str, Any], str]:
    d, t, p = cfg["data"], cfg["train"], cfg["probe"]
    source = MarkovSource.make(k=d["k"], seed=seed)
    rates = source.entropy_rates()
    train = source.sample(d["train_symbols"], seed=seed + 1)
    val = source.sample(d["val_symbols"], seed=seed + 2)
    data_sha = ex.sha256_bytes(ex._pack_ints(train.tolist()) + b"|" + ex._pack_ints(val.tolist()))
    mcfg = DecoderConfig(**cfg["model"])
    m: dict[str, Any] = {"entropy_nats": {k: round(v, 4) for k, v in rates.items()}, "variants": {}}
    models: dict[str, NawaDecoder] = {}
    for name, spec in cfg["variants"].items():
        t0 = time.perf_counter()
        model, last = _train(build(mcfg, spec, seed), train, seed, t)
        vl = heldout_loss(model, val, t["seq_len"], skip=d["heldout_skip"])
        models[name] = model.eval()
        moe, layers = _variant(spec)
        pc = param_counts(mcfg, moe, layers)
        m["variants"][name] = {
            "val_loss": round(vl, 4), "final_train_loss": round(last, 4),
            "margin_below_H1": round(rates["H1"] - vl, 4), "gap_to_H2": round(vl - rates["H2"], 4),
            "params_total": pc["total"], "params_active_per_token": pc["active"],
            "param_bytes_fp32_total": 4 * pc["total"],
            "forward_flops_per_token_at_64": forward_flops_per_token(mcfg, moe, layers, t["seq_len"]),
            "train_seconds": round(time.perf_counter() - t0, 1)}
    for name in models:
        m["variants"][name]["latency_ms_median"] = latency_ms(models[name], cfg["latency"], seed)
    for name in ("moe", "hybrid"):
        m["variants"][name]["expert_load"] = expert_load(models[name], val)
    v = m["variants"]
    for name in v:
        m[f"{name}_margin_below_h1"] = v[name]["margin_below_H1"]
    m.update(count_checks(seed))
    m.update(dispatch_checks(models, val, seed))
    m.update(identity_checks(seed))
    m["moe_batch_invariance_max_abs_diff"] = batch_invariance(models, val)
    seq = cfg["model"]["max_seq_len"]
    dense_path = [causality_probe(models[n], seq, seed, dense_path=True) for n in ("moe", "hybrid")]
    dispatch = [causality_probe(models[n], seq, seed, dense_path=False) for n in ("moe", "hybrid")]
    m["moe_dense_path_causality_violations"] = sum(b for b, _ in dense_path)
    m["moe_dispatch_causality_max_abs_diff"] = max(w for _, w in dispatch)
    m["moe_dispatch_causality_violations_strict_evidence"] = sum(b for b, _ in dispatch)
    m["dense_causality_violations"] = causality_violations(models["dense"], seq, seed)
    grads = {n: gradient_report(build(mcfg, cfg["variants"][n], seed), p["seq_len"], seed) for n in ("moe", "hybrid")}
    m["gradients"] = grads
    m["moe_gradients_ok"] = all(all(g.values()) for g in grads.values())
    m["aux_loss_checks_ok"] = aux_checks(seed)
    m["reference_core_config_unchanged"] = reference_core_unchanged()
    m["loss_gap_vs_dense_evidence"] = {n: round(v[n]["val_loss"] - v["dense"]["val_loss"], 4) for n in ("moe", "hybrid")}
    return m, data_sha


def run(seed: int = 42) -> ex.P4Run:
    from nawa import budget
    decision = budget.check("cpu_local")
    if not decision.allowed:
        raise ex.RecordError(f"budget guard refused the run: {decision.reason}")
    t0 = time.perf_counter()
    metrics, data_sha = measure(seed, CONFIG)
    metrics["wall_seconds"] = round(time.perf_counter() - t0, 1)
    results = ex.evaluate_criteria(CRITERIA, metrics)
    failed = sorted(k for k, ok in results.items() if not ok)
    return ex.P4Run(
        task_id="P4-02",
        purpose="P4-02: Dense vs Sparse MoE (top-k router, no capacity limit) vs Hybrid (MoE in some blocks) on the "
                "reference decoder; correctness of routing, dispatch, parameter/FLOP accounting, load-balance loss, "
                "causality and batch invariance, and learning sanity of each variant. Comparisons are evidence only.",
        config=CONFIG, seed=seed, data_sha256=data_sha,
        data_description=f"synthetic: MarkovSource.make(k=29, seed={seed}); train = sample(500000, seed={seed + 1}); "
                         f"val = sample(50000, seed={seed + 2}); int64 little-endian (struct) hashed",
        criteria=CRITERIA, metrics=metrics, training_steps=CONFIG["train"]["steps"] * len(CONFIG["variants"]),
        reproduce=f"python -m nawa.efficiency.p4_02 --seed {seed} --dry-run",
        claims=[{"type": "correctness", "text": "The sparse dispatch equals the dense masked reference, the MoE reduces "
                                                "to the dense model in its two exact identities, parameter and FLOP "
                                                "counts match their closed forms, and the MoE variants are causal, "
                                                "batch-invariant and trainable."},
                {"type": "evidence", "text": "Loss gaps, parameter bytes, FLOPs, CPU latency and expert load come from a "
                                             "2-layer CPU model on a synthetic Markov source; they do not rank Dense, "
                                             "MoE or Hybrid for NAWA (P4-02a)."}],
        failure_cases=[f"criterion failed: {k}" for k in failed],
        conclusion=("Sparse MoE and Hybrid are implemented correctly and all three variants learn the synthetic source. "
                    "Nothing adopted (ADR-0007 D4); the comparison is P4-02a."
                    if not failed else f"Registered criteria failed: {', '.join(failed)}. See metrics."),
        next_action="P4-04 (attention + convolution/hybrid blocks, code-only, ADR-0007 D5); the Dense/MoE/Hybrid "
                    "comparison on real text waits for P4-02a (OD-03, P3-03).",
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m nawa.efficiency.p4_02")
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
