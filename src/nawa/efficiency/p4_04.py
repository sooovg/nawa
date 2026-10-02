"""P4-04 experiment: attention vs causal-convolution vs attention + convolution hybrid blocks (ADR-0007 D2).

Code-only, synthetic, CPU, Track S. Nothing adopted (D4); no attention:convolution ratio adopted.

    python -m nawa.efficiency.p4_04 --seed 42 [--dry-run]

``CRITERIA``, ``TOL``, ``IDENTITY_TOL`` and ``CONFIG`` below were written and committed to the branch before the
first run (pre-registration). The criteria are pass/fail **correctness** checks of the convolution mixer and the
layout surgery, plus one learning-sanity check per layout (held-out loss clearly below H1, as in P3-05, P4-03 and
P4-02). Loss gaps, parameter counts, FLOPs, decoding-state size and latency are **evidence only**: an order-2
Markov source needs only two symbols of context, which a 2-layer convolution of kernel 4 already covers, so this
source cannot show what attention adds over a short convolution, and cannot rank the layouts. The comparison on
real text is P4-04a (BLOCKED: OD-03, P3-03).

Amendment to the pre-registration (commit after 9af18f0, before the registered run). A development smoke of the
probes (seed 1, no training, not recorded) found two **probe** defects; no criterion, tolerance or config changed:

1. ``surgery_preserved`` required the replaced keys to be absent, but :class:`ConvMixer` also names its output
   projection ``o_proj``, so ``blocks.i.attn.o_proj.*`` exists in both models. The probe now skips every key under a
   replaced ``blocks.i.attn.`` prefix, checks that the module there is a :class:`ConvMixer`, and checks every other
   key for exact equality, which is what the criterion states.
2. ``reference_and_streaming_checks`` randomised every mixer parameter with std 0.5, which made outputs reach ~495;
   the measured difference (4.6e-5) was 6e-8 *relative*, i.e. float32 rounding, outside the order-1 activations TOL
   was justified for. Randomised parameters now use std 1/sqrt(fan_in) (fan_in = d_model for the projections, K for
   the taps, 1 for biases), which keeps activations of order 1. The max absolute output is recorded as evidence.
"""

from __future__ import annotations

import argparse
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
from nawa.efficiency.conv import (CausalDepthwiseConv, ConvConfig, ConvMixer, apply_conv, conv_mixers_of,
                                  forward_flops_per_token, mixer_state_floats, param_counts, receptive_field)
from nawa.efficiency.structural import causality_violations, gradient_report
from nawa.model import DecoderConfig, NawaDecoder
from nawa.model.layers import CausalSelfAttention
from nawa.training.sanity import MarkovSource, batches, heldout_loss

ROOT = Path(__file__).resolve().parents[3]

# ---- pre-registered (before the first run) ------------------------------------------------------------------------
TOL = 1e-5            # shifted-sum conv vs conv1d, streaming vs full, batch invariance: float32 activations of order 1
                      # summed in a different order differ by ~1e-7; a wrong lag, flip, pad or state shift moves
                      # them by >= 1e-2 (negative controls in tests/test_conv.py).
IDENTITY_TOL = 1e-6   # a delta kernel (lag 0 = 1) with no gate must reproduce o_proj(in_proj(x)) (same matmuls)
CRITERIA: dict[str, Any] = {
    "conv_param_counts_exact": {"op": "==", "value": True},
    "flops_counted_equals_formula": {"op": "==", "value": True},
    "conv_vs_conv1d_reference_max_abs_diff": {"op": "<=", "value": TOL},
    "delta_kernel_identity_max_abs_diff": {"op": "<=", "value": IDENTITY_TOL},
    "streaming_vs_full_max_abs_diff": {"op": "<=", "value": TOL},
    "causality_violations": {"op": "==", "value": 0},
    "receptive_field_violations": {"op": "==", "value": 0},
    "receptive_field_reached": {"op": "==", "value": True},
    "batch_invariance_max_abs_diff": {"op": "<=", "value": TOL},
    "surgery_preserves_other_weights": {"op": "==", "value": True},
    "conv_gradients_ok": {"op": "==", "value": True},
    "reference_core_config_unchanged": {"op": "==", "value": True},
    "attention_margin_below_h1": {"op": ">=", "value": 0.10},
    "conv_margin_below_h1": {"op": ">=", "value": 0.10},
    "hybrid_margin_below_h1": {"op": ">=", "value": 0.10},
}

_CONV = {"kernel_size": 4, "gate": "silu"}
CONFIG: dict[str, Any] = {
    "model": {"vocab_size": 29, "d_model": 64, "n_layers": 2, "n_heads": 4, "max_seq_len": 64},
    "variants": {
        "attention": None,                                      # the P3-04 reference layout
        "conv": {"conv": _CONV, "conv_layers": [0, 1]},         # every block convolutional (ratio 0:2)
        "hybrid": {"conv": _CONV, "conv_layers": [0]},          # convolution then attention (ratio 1:1)
    },
    "correctness_extra": {
        "gelu_bias_model": {"vocab_size": 29, "d_model": 48, "n_layers": 2, "n_heads": 4, "max_seq_len": 64,
                            "positional": "learned", "mlp": "gelu", "norm": "layernorm", "bias": True,
                            "tie_embeddings": False},
        "four_layer_model": {"vocab_size": 29, "d_model": 32, "n_layers": 4, "n_heads": 4, "n_kv_heads": 2,
                             "max_seq_len": 64},
        "convs": [{"kernel_size": 1, "gate": "none"}, {"kernel_size": 3, "gate": "sigmoid"}, _CONV],
        "layouts_4": [[0], [1, 3], [0, 1, 2], [0, 1, 2, 3]],
    },
    "train": {"steps": 1500, "batch": 32, "seq_len": 64, "lr": 3e-3, "weight_decay": 0.01, "grad_clip": 1.0,
              "loss": "cross-entropy", "same_init_and_batches": True},
    "data": {"generator": "nawa.training.sanity.MarkovSource", "k": 29, "train_symbols": 500_000,
             "val_symbols": 50_000, "heldout_skip": 2},
    "latency": {"batch": 8, "seq_len": 64, "warmup": 3, "repeats": 20, "status": "evidence only, CPU wall clock"},
    "probe": {"seq_len": 63, "streaming_len": 40, "trials": 8},
}
REFERENCE_CORE_HASH = "918f4cf4877c0cca"   # configs/base_model.yaml, pinned by ADR-0007 D4


# ---- builders -----------------------------------------------------------------------------------------------------
def _variant(spec: dict[str, Any] | None) -> tuple[ConvConfig | None, tuple[int, ...] | None]:
    if spec is None:
        return None, None
    return ConvConfig(**spec["conv"]), tuple(spec["conv_layers"])


def build(cfg: DecoderConfig, spec: dict[str, Any] | None, seed: int) -> NawaDecoder:
    torch.manual_seed(seed)
    model = NawaDecoder(cfg)
    conv, layers = _variant(spec)
    return apply_conv(model, conv, layers, seed=seed + 100) if conv else model


def _train(model: NawaDecoder, train: torch.Tensor, seed: int, t: dict[str, Any]) -> tuple[NawaDecoder, float]:
    model.train()
    opt = torch.optim.AdamW(model.parameters(), lr=t["lr"], weight_decay=t["weight_decay"])
    g = torch.Generator().manual_seed(seed + 3)
    last = math.nan
    for _ in range(t["steps"]):
        x, y = batches(train, t["seq_len"], t["batch"], g)
        loss = model(x, targets=y).loss
        opt.zero_grad(set_to_none=True)
        loss.backward()
        nn.utils.clip_grad_norm_(model.parameters(), t["grad_clip"])
        opt.step()
        last = float(loss.detach())
    return model.eval(), last


# ---- correctness probes --------------------------------------------------------------------------------------------
def _model_cfgs() -> list[DecoderConfig]:
    extra = CONFIG["correctness_extra"]
    return [DecoderConfig(**CONFIG["model"]), DecoderConfig(**extra["gelu_bias_model"]),
            DecoderConfig(**extra["four_layer_model"])]


def _cases() -> list[tuple[DecoderConfig, ConvConfig, tuple[int, ...]]]:
    out = []
    extra = CONFIG["correctness_extra"]
    for cfg in _model_cfgs():
        layouts = extra["layouts_4"] if cfg.n_layers == 4 else [[0], [1], [0, 1]]
        for c in extra["convs"]:
            for layout in layouts:
                out.append((cfg, ConvConfig(**c), tuple(layout)))
    return out


def count_checks(seed: int) -> dict[str, bool]:
    """Closed-form totals vs the model; FLOPs formula vs MACs counted by hooks on every Linear and every
    convolution (plus the attention context term of the remaining attention blocks)."""
    totals_ok, flops_ok = True, True
    for cfg, conv, layers in _cases():
        m = build(cfg, {"conv": conv.to_dict(), "conv_layers": list(layers)}, seed).eval()
        totals_ok &= param_counts(cfg, conv, layers) == m.num_parameters()
        t, b = 16, 3
        macs = [0]

        def lin(mod: nn.Linear, inp: tuple, out: torch.Tensor) -> None:
            macs[0] += inp[0].reshape(-1, mod.in_features).shape[0] * mod.in_features * mod.out_features

        def cnv(mod: CausalDepthwiseConv, inp: tuple, out: torch.Tensor) -> None:
            macs[0] += inp[0].shape[0] * inp[0].shape[1] * mod.weight.numel()

        hooks = [mod.register_forward_hook(lin) for mod in m.modules() if isinstance(mod, nn.Linear)]
        hooks += [mod.register_forward_hook(cnv) for mod in m.modules() if isinstance(mod, CausalDepthwiseConv)]
        with torch.no_grad():
            m(torch.randint(0, cfg.vocab_size, (b, t), generator=torch.Generator().manual_seed(seed + 1)))
        for h in hooks:
            h.remove()
        n_attn = sum(isinstance(blk.attn, CausalSelfAttention) for blk in m.blocks)
        ctx = n_attn * 2 * t * cfg.n_heads * cfg.head_dim * b * t
        flops_ok &= 2 * (macs[0] + ctx) == forward_flops_per_token(cfg, conv, layers, t) * b * t
    return {"conv_param_counts_exact": bool(totals_ok), "flops_counted_equals_formula": bool(flops_ok)}


@torch.no_grad()
def reference_and_streaming_checks(seed: int) -> dict[str, float]:
    """Shifted-sum convolution vs conv1d, and ConvMixer.step vs ConvMixer.forward, over every case's mixer, on
    random inputs and on randomised (non-init) taps and biases."""
    g = torch.Generator().manual_seed(seed + 5)
    worst_ref, worst_stream, out_max = 0.0, 0.0, 0.0
    n = CONFIG["probe"]["streaming_len"]
    for cfg, conv, _ in _cases():
        mixer = ConvMixer(cfg, conv)
        for name, p in mixer.named_parameters():
            fan_in = 1 if name.endswith("bias") else p.shape[-1]
            p.copy_(torch.randn(p.shape, generator=g) / math.sqrt(fan_in))
        x = torch.randn(3, n, cfg.d_model, generator=g)
        full = mixer(x)
        out_max = max(out_max, float(full.abs().max()))
        worst_ref = max(worst_ref, float((full - mixer.reference_forward(x)).abs().max()))
        worst_ref = max(worst_ref, float((mixer.conv(x) - mixer.conv.reference(x)).abs().max()))
        state = mixer.init_state(3)
        steps = []
        for i in range(n):
            y, state = mixer.step(x[:, i], state)
            steps.append(y)
        worst_stream = max(worst_stream, float((torch.stack(steps, 1) - full).abs().max()))
    return {"conv_vs_conv1d_reference_max_abs_diff": worst_ref, "streaming_vs_full_max_abs_diff": worst_stream,
            "probe_max_abs_output_evidence": round(out_max, 3)}


@torch.no_grad()
def delta_identity(seed: int) -> float:
    """ConvMixer with gate 'none' and taps (1, 0, ..., 0) and zero conv bias is o_proj(in_proj(x)) exactly."""
    g = torch.Generator().manual_seed(seed + 9)
    worst = 0.0
    for cfg in _model_cfgs():
        for k in (1, 3, 4):
            mixer = ConvMixer(cfg, ConvConfig(kernel_size=k, gate="none"))
            mixer.conv.weight.zero_()
            mixer.conv.weight[:, 0] = 1.0
            if mixer.conv.bias is not None:
                mixer.conv.bias.zero_()
            x = torch.randn(2, 19, cfg.d_model, generator=g)
            worst = max(worst, float((mixer(x) - mixer.o_proj(mixer.in_proj(x))).abs().max()))
    return worst


@torch.no_grad()
def receptive_field_probe(model: NawaDecoder, conv: ConvConfig, seq_len: int, seed: int,
                          trials: int) -> tuple[int, bool]:
    """All-convolution model only. Change the token at position s (and everything before it). Positions
    > s + RF must not change at all (violations); position s + RF must change in every trial (reached)."""
    rf = receptive_field(model.cfg, conv, None)
    assert rf is not None
    g = torch.Generator().manual_seed(seed)
    bad, reached = 0, True
    for _ in range(trials):
        x = torch.randint(0, model.cfg.vocab_size, (1, seq_len), generator=g)
        s = int(torch.randint(0, seq_len - rf - 1, (1,), generator=g))
        y = x.clone()
        y[0, : s + 1] = (y[0, : s + 1] + 1) % model.cfg.vocab_size
        d = (model(x).logits[0] - model(y).logits[0]).abs().amax(-1)
        bad += int(d[s + rf + 1:].gt(0).sum())
        reached &= bool(d[s + rf] > 0)
    return bad, reached


@torch.no_grad()
def batch_invariance(models: dict[str, NawaDecoder], val: torch.Tensor) -> float:
    worst = 0.0
    x = val[: 6 * 64].view(6, 64)
    for name in ("conv", "hybrid"):
        m = models[name]
        full = m(x).logits
        for i in (0, 3, 5):
            worst = max(worst, float((m(x[i:i + 1]).logits[0] - full[i]).abs().max()))
    return worst


def surgery_preserved(seed: int) -> bool:
    """Every parameter outside the replaced attention sub-layers equals the reference built with the same seed."""
    ok = True
    for cfg in _model_cfgs():
        ref = {k: v for k, v in build(cfg, None, seed).state_dict().items()}
        layouts = CONFIG["correctness_extra"]["layouts_4"] if cfg.n_layers == 4 else [[0], [1], [0, 1]]
        for layout in layouts:
            m = build(cfg, {"conv": _CONV, "conv_layers": layout}, seed)
            replaced = tuple(f"blocks.{i}.attn." for i in layout)
            sd = m.state_dict()
            for k, v in ref.items():
                if k.startswith(replaced):
                    continue
                ok &= k in sd and torch.equal(sd[k], v)
            ok &= all(isinstance(m.blocks[i].attn, ConvMixer) for i in layout)
            ok &= all(isinstance(blk.attn, CausalSelfAttention) for i, blk in enumerate(m.blocks) if i not in layout)
            ok &= len(conv_mixers_of(m)) == len(layout)
    return bool(ok)


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
        conv, layers = _variant(spec)
        m["variants"][name] = {
            "val_loss": round(vl, 4), "final_train_loss": round(last, 4),
            "margin_below_H1": round(rates["H1"] - vl, 4), "gap_to_H2": round(vl - rates["H2"], 4),
            "params": param_counts(mcfg, conv, layers),
            "forward_flops_per_token_at_64": forward_flops_per_token(mcfg, conv, layers, t["seq_len"]),
            "forward_flops_per_token_at_1024_formula": forward_flops_per_token(mcfg, conv, layers, 1024),
            "decode_state_floats_at_64": mixer_state_floats(mcfg, conv, layers, t["seq_len"]),
            "decode_state_floats_at_1024_formula": mixer_state_floats(mcfg, conv, layers, 1024),
            "receptive_field": receptive_field(mcfg, conv, layers) if conv else None,
            "train_seconds": round(time.perf_counter() - t0, 1)}
    for name in models:
        m["variants"][name]["latency_ms_median"] = latency_ms(models[name], cfg["latency"], seed)
    v = m["variants"]
    for name in v:
        m[f"{name}_margin_below_h1"] = v[name]["margin_below_H1"]
    m.update(count_checks(seed))
    m.update(reference_and_streaming_checks(seed))
    m["delta_kernel_identity_max_abs_diff"] = delta_identity(seed)
    seq = cfg["model"]["max_seq_len"]
    m["causality_violations"] = sum(causality_violations(models[n], seq, seed, trials=p["trials"])
                                    for n in ("conv", "hybrid"))
    m["attention_causality_violations"] = causality_violations(models["attention"], seq, seed, trials=p["trials"])
    rf_bad, rf_reached = receptive_field_probe(models["conv"], ConvConfig(**_CONV), seq, seed, p["trials"])
    m["receptive_field_violations"], m["receptive_field_reached"] = rf_bad, rf_reached
    m["batch_invariance_max_abs_diff"] = batch_invariance(models, val)
    m["surgery_preserves_other_weights"] = surgery_preserved(seed)
    grads = {n: gradient_report(build(mcfg, cfg["variants"][n], seed), p["seq_len"], seed) for n in ("conv", "hybrid")}
    m["gradients"] = grads
    m["conv_gradients_ok"] = all(all(g.values()) for g in grads.values())
    m["reference_core_config_unchanged"] = reference_core_unchanged()
    m["loss_gap_vs_attention_evidence"] = {n: round(v[n]["val_loss"] - v["attention"]["val_loss"], 4)
                                           for n in ("conv", "hybrid")}
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
        task_id="P4-04",
        purpose="P4-04: attention vs gated causal depthwise convolution (kernel 4) vs a 1:1 convolution+attention "
                "hybrid on the reference decoder; correctness of the convolution (independent conv1d path, "
                "streaming state, delta-kernel identity), exact causality and receptive field, parameter/FLOP "
                "accounting, layout surgery, batch invariance, gradients, and learning sanity of each layout. "
                "Comparisons are evidence only; no ratio is adopted.",
        config=CONFIG, seed=seed, data_sha256=data_sha,
        data_description=f"synthetic: MarkovSource.make(k=29, seed={seed}); train = sample(500000, seed={seed + 1}); "
                         f"val = sample(50000, seed={seed + 2}); int64 little-endian (struct) hashed",
        criteria=CRITERIA, metrics=metrics, training_steps=CONFIG["train"]["steps"] * len(CONFIG["variants"]),
        reproduce=f"python -m nawa.efficiency.p4_04 --seed {seed} --dry-run",
        claims=[{"type": "correctness", "text": "The shifted-sum causal convolution equals an independent conv1d path "
                                                "and its streaming form, reduces to the projections under a delta "
                                                "kernel, has an exact causal receptive field of L*(K-1), parameter "
                                                "and FLOP counts match their closed forms, the surgery leaves every "
                                                "other weight untouched, and every layout is trainable."},
                {"type": "evidence", "text": "Loss gaps, FLOPs, decoding-state size and CPU latency come from a "
                                             "2-layer CPU model on an order-2 synthetic Markov source that a short "
                                             "convolution already covers; they do not rank attention, convolution "
                                             "or any ratio for NAWA (P4-04a)."}],
        failure_cases=[f"criterion failed: {k}" for k in failed],
        conclusion=("The convolution mixer and the attention/convolution layouts are implemented correctly and all "
                    "three layouts learn the synthetic source. Nothing adopted, no ratio adopted (ADR-0007 D4); the "
                    "comparison is P4-04a." if not failed else
                    f"Registered criteria failed: {', '.join(failed)}. See metrics."),
        next_action="P4-07 stays IN_PROGRESS until P4-02..P4-05 are listed; all P4 code tasks are then done. The "
                    "attention/convolution comparison on real text waits for P4-04a (OD-03, P3-03).",
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m nawa.efficiency.p4_04")
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
