"""P4-03 experiment: ternary {-1, 0, +1} and 4-bit weights with QAT on the reference core (ADR-0007 D2).

    python -m nawa.efficiency.p4_03 --seed 42 [--dry-run]

``CRITERIA``, ``LOGIT_TOL``, ``FALLBACK`` and ``CONFIG`` below were written and committed to the branch before the
first run (pre-registration). Every criterion is a pass/fail **correctness** check, plus one learning-sanity check per
quantized variant (held-out loss clearly below the order-1 entropy H1, i.e. the QAT model learned to use the
two-symbol context, as in P3-05). Loss gaps against the full-precision reference, memory ratios and the fallback-rule
outcome are recorded as **evidence only**: synthetic data cannot support an improvement or adoption claim
(ADR-0007 D2, D4), and the reference core is not changed.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import sys
import time
from pathlib import Path
from typing import Any

import torch
from torch import nn

from nawa import experiments as ex
from nawa.efficiency.quant import (INT4_QMAX, MODES, FallbackRule, PackedLinear, QuantLinear, apply_quant,
                                   choose_precision, dequantize, fake_quant, memory_report, pack_codes, quant_layers,
                                   quantize, to_packed, unpack_codes)
from nawa.efficiency.structural import causality_violations, gradient_report
from nawa.model import DecoderConfig, NawaDecoder
from nawa.training.sanity import MarkovSource, batches, heldout_loss

ROOT = Path(__file__).resolve().parents[3]

# ---- pre-registered (before the first run) ------------------------------------------------------------------------
LOGIT_TOL = 1e-4   # same reasoning as P4-05: float32 logits of order 1-10; a reordered sum moves them ~1e-6, a wrong
                   # scale or code moves them by >= 1e-2 (tests/test_quant.py negative controls).
FALLBACK = FallbackRule(max_loss_gap=0.10)   # evidence only on synthetic data (ADR-0007 D2)
CRITERIA: dict[str, Any] = {
    # codes
    "ternary_codes_in_set": {"op": "==", "value": True},
    "ternary_uses_all_three_values": {"op": "==", "value": True},
    "int4_codes_in_range": {"op": "==", "value": True},
    "int4_requantize_idempotent": {"op": "==", "value": True},
    "forward_weight_equals_codes_times_scale": {"op": "==", "value": True},
    # straight-through estimator: latent-weight gradient == gradient w.r.t. the dequantized weight, exactly
    "ste_grad_max_abs_diff": {"op": "<=", "value": 0.0},
    # export
    "packed_roundtrip_exact": {"op": "==", "value": True},
    "packed_forward_max_abs_logit_diff": {"op": "<=", "value": LOGIT_TOL},
    "packed_bytes_formula_exact": {"op": "==", "value": True},
    # model-level correctness
    "quant_causality_violations": {"op": "==", "value": 0},
    "quant_gradients_ok": {"op": "==", "value": True},
    "fallback_rule_cases_ok": {"op": "==", "value": True},
    "reference_core_config_unchanged": {"op": "==", "value": True},
    # learning sanity under QAT (P3-05 convention: held-out loss <= H1 - 0.10)
    "qat_ternary_margin_below_h1": {"op": ">=", "value": 0.10},
    "qat_int4_margin_below_h1": {"op": ">=", "value": 0.10},
}

CONFIG: dict[str, Any] = {
    "model": {"vocab_size": 29, "d_model": 64, "n_layers": 2, "n_heads": 4, "max_seq_len": 64},
    "quant": {"modes": list(MODES), "granularity": "row", "int4_qmax": INT4_QMAX,
              "quantized": "block linears (attn q/k/v/o, mlp up/gate/down); embeddings, lm_head, norms fp32"},
    "train": {"steps": 1500, "batch": 32, "seq_len": 64, "lr": 3e-3, "weight_decay": 0.01, "grad_clip": 1.0,
              "same_init_and_batches_for_all_variants": True},
    "data": {"generator": "nawa.training.sanity.MarkovSource", "k": 29, "train_symbols": 500_000,
             "val_symbols": 50_000, "heldout_skip": 2},
    "fallback": {"max_loss_gap_nats": FALLBACK.max_loss_gap, "status": "evidence only (ADR-0007 D2)"},
    "probe": {"seq_len": 63, "packed_eval_windows": 32},
}
REFERENCE_CORE_HASH = "918f4cf4877c0cca"   # configs/base_model.yaml, pinned by ADR-0007 D4 (EXP-0006)


# ---- training ------------------------------------------------------------------------------------------------------
def _init(cfg: DecoderConfig, seed: int, mode: str | None) -> NawaDecoder:
    torch.manual_seed(seed)
    model = NawaDecoder(cfg)
    return apply_quant(model, mode, CONFIG["quant"]["granularity"]) if mode else model


def _train(model: NawaDecoder, train: torch.Tensor, seed: int, t: dict[str, Any]) -> tuple[NawaDecoder, float]:
    model.train()
    opt = torch.optim.AdamW(model.parameters(), lr=t["lr"], weight_decay=t["weight_decay"])
    g = torch.Generator().manual_seed(seed + 3)          # identical batch sequence for every variant
    last = math.nan
    for _ in range(t["steps"]):
        x, y = batches(train, t["seq_len"], t["batch"], g)
        loss = model(x, targets=y).loss
        opt.zero_grad(set_to_none=True)
        loss.backward()
        nn.utils.clip_grad_norm_(model.parameters(), t["grad_clip"])
        opt.step()
        last = float(loss)
    return model.eval(), last


# ---- correctness probes --------------------------------------------------------------------------------------------
@torch.no_grad()
def code_checks(models: dict[str, NawaDecoder]) -> dict[str, Any]:
    tern, i4 = quant_layers(models["ternary"]), quant_layers(models["int4"])
    in_set = all(set(layer.codes()[0].unique().tolist()) <= {-1, 0, 1} for layer in tern)
    all_three = all(set(layer.codes()[0].unique().tolist()) == {-1, 0, 1} for layer in tern)
    in_range = all(int(layer.codes()[0].abs().max()) <= INT4_QMAX for layer in i4)
    idem = True
    for layer in i4:
        c, s = layer.codes()
        idem &= torch.equal(quantize(dequantize(c, s), "int4")[0], c)
    fwd_exact = all(torch.equal(fake_quant(layer.weight, layer.mode, layer.granularity), dequantize(*layer.codes()))
                    for layer in tern + i4)
    zero_frac = [float((layer.codes()[0] == 0).float().mean()) for layer in tern]
    return {"ternary_codes_in_set": in_set, "ternary_uses_all_three_values": all_three, "int4_codes_in_range": in_range,
            "int4_requantize_idempotent": bool(idem), "forward_weight_equals_codes_times_scale": fwd_exact,
            "ternary_zero_fraction_evidence": {"min": round(min(zero_frac), 4), "max": round(max(zero_frac), 4),
                                               "mean": round(sum(zero_frac) / len(zero_frac), 4)},
            "quantized_layers": {"ternary": len(tern), "int4": len(i4)}}


def _dense_twin(model: NawaDecoder) -> NawaDecoder:
    """Copy of a QAT model where each QuantLinear is a plain Linear whose weight is the dequantized weight (a leaf)."""
    twin = copy.deepcopy(model)
    for block in twin.blocks:
        for parent in (block.attn, block.mlp):
            for name, layer in list(parent.named_children()):
                if isinstance(layer, QuantLinear):
                    dense = nn.Linear(layer.in_features, layer.out_features, bias=layer.bias is not None)
                    with torch.no_grad():
                        dense.weight.copy_(dequantize(*layer.codes()))
                        if layer.bias is not None:
                            dense.bias.copy_(layer.bias)
                    setattr(parent, name, dense)
    return twin


def ste_grad_diff(model: NawaDecoder, seq_len: int, seed: int) -> float:
    """max |dL/dw_latent - dL/dw_dequant| over every quantized layer, on one batch (must be exactly 0)."""
    x = torch.randint(0, model.cfg.vocab_size, (2, seq_len + 1), generator=torch.Generator().manual_seed(seed))
    twin = _dense_twin(model)
    for m in (model, twin):
        m.eval()
        m.zero_grad(set_to_none=True)
        m(x[:, :-1], targets=x[:, 1:]).loss.backward()
    worst = 0.0
    q = [mod for mod in model.modules() if isinstance(mod, QuantLinear)]
    d = [mod for name, mod in twin.named_modules()
         if isinstance(mod, nn.Linear) and any(name.endswith(f"{p}.{n}") for p, n in
                                               (("attn", "q_proj"), ("attn", "k_proj"), ("attn", "v_proj"),
                                                ("attn", "o_proj"), ("mlp", "up"), ("mlp", "gate"), ("mlp", "down")))]
    if len(q) != len(d):
        return math.inf
    for a, b in zip(q, d):
        worst = max(worst, float((a.weight.grad - b.weight.grad).abs().max()))
    model.zero_grad(set_to_none=True)
    return worst


@torch.no_grad()
def packed_checks(models: dict[str, NawaDecoder], val: torch.Tensor, seq_len: int, windows: int,
                  seed: int) -> dict[str, Any]:
    roundtrip, bytes_ok, diff, mem = True, True, 0.0, {}
    g = torch.Generator().manual_seed(seed + 11)
    for mode in MODES:                                   # random tensors, odd sizes (padding paths)
        hi = 1 if mode == "ternary" else INT4_QMAX
        for shape in ((1, 1), (3, 5), (7, 13), (64, 171)):
            c = torch.randint(-hi, hi + 1, shape, generator=g).to(torch.int8)
            roundtrip &= torch.equal(unpack_codes(pack_codes(c, mode), mode, shape), c)
    n = min(windows, (len(val) - 1) // seq_len)
    x = val[: n * seq_len].view(n, seq_len)
    for mode in MODES:
        qat = models[mode]
        for layer in quant_layers(qat):
            c = layer.codes()[0]
            roundtrip &= torch.equal(unpack_codes(pack_codes(c, mode), mode, tuple(c.shape)), c)
        packed = to_packed(copy.deepcopy(qat))
        diff = max(diff, float((packed(x).logits - qat(x).logits).abs().max()))
        report = memory_report(packed)
        real = sum(m.nbytes for m in packed.modules() if isinstance(m, PackedLinear))
        bytes_ok &= real == report["packed_bytes"] and report == memory_report(qat)
        mem[mode] = {**report, "fp32_over_packed_evidence": round(report["fp32_bytes"] / report["packed_bytes"], 3)}
    return {"packed_roundtrip_exact": bool(roundtrip), "packed_forward_max_abs_logit_diff": diff,
            "packed_bytes_formula_exact": bool(bytes_ok), "memory_evidence": mem}


def fallback_cases() -> bool:
    r = FallbackRule(0.1)
    cases = [((1.0, 1.05, 2.0), "ternary"), ((1.0, 1.5, 1.05), "int4"), ((1.0, 1.5, 1.5), "fp"),
             ((1.0, math.nan, 1.0), "int4"), ((1.0, math.inf, math.nan), "fp"), ((1.0, 1.1, 1.0), "ternary")]
    ok = all(choose_precision(*args, r) == want for args, want in cases)
    try:
        FallbackRule(-0.1)
        ok = False
    except ValueError:
        pass
    return ok


def reference_core_unchanged() -> bool:
    return DecoderConfig.from_yaml(ROOT / "configs" / "base_model.yaml").config_hash() == REFERENCE_CORE_HASH


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
    for variant in ("fp", *MODES):
        t0 = time.perf_counter()
        model, last = _train(_init(mcfg, seed, None if variant == "fp" else variant), train, seed, t)
        vl = heldout_loss(model, val, t["seq_len"], skip=d["heldout_skip"])
        model.eval()
        models[variant] = model
        m["variants"][variant] = {"val_loss": round(vl, 4), "final_train_loss": round(last, 4),
                                  "margin_below_H1": round(rates["H1"] - vl, 4), "gap_to_H2": round(vl - rates["H2"], 4),
                                  "seconds": round(time.perf_counter() - t0, 1)}
    v = m["variants"]
    m["qat_ternary_margin_below_h1"] = v["ternary"]["margin_below_H1"]
    m["qat_int4_margin_below_h1"] = v["int4"]["margin_below_H1"]
    m.update(code_checks(models))
    m["ste_grad_max_abs_diff"] = max(ste_grad_diff(models[mode], p["seq_len"], seed + 21) for mode in MODES)
    m.update(packed_checks(models, val, t["seq_len"], p["packed_eval_windows"], seed))
    m["quant_causality_violations"] = sum(causality_violations(models[mode], cfg["model"]["max_seq_len"], seed)
                                          for mode in MODES)
    grads = {mode: gradient_report(_init(mcfg, seed, mode), p["seq_len"], seed) for mode in MODES}
    m["gradients"] = grads
    m["quant_gradients_ok"] = all(all(g.values()) for g in grads.values())
    m["fallback_rule_cases_ok"] = fallback_cases()
    m["reference_core_config_unchanged"] = reference_core_unchanged()
    m["loss_gap_vs_fp_evidence"] = {mode: round(v[mode]["val_loss"] - v["fp"]["val_loss"], 4) for mode in MODES}
    m["fallback_outcome_evidence"] = choose_precision(v["fp"]["val_loss"], v["ternary"]["val_loss"],
                                                      v["int4"]["val_loss"], FALLBACK)
    m["parameters"] = models["fp"].num_parameters()
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
    passed = all(results.values())
    failed = sorted(k for k, ok in results.items() if not ok)
    return ex.P4Run(
        task_id="P4-03",
        purpose="P4-03: ternary {-1,0,+1} (absmean) and symmetric 4-bit (absmax) weights with straight-through QAT on "
                "the reference decoder; correctness of codes, STE gradient, packed export and fallback rule, and "
                "learning sanity under QAT. Comparison with full precision is evidence only.",
        config=CONFIG, seed=seed, data_sha256=data_sha,
        data_description=f"synthetic: MarkovSource.make(k=29, seed={seed}); train = sample(500000, seed={seed + 1}); "
                         f"val = sample(50000, seed={seed + 2}); int64 little-endian (struct) hashed",
        criteria=CRITERIA, metrics=metrics, training_steps=CONFIG["train"]["steps"] * 3,
        reproduce=f"python -m nawa.efficiency.p4_03 --seed {seed} --dry-run",
        claims=[{"type": "correctness", "text": "Ternary and 4-bit QAT layers produce codes in their value sets, the "
                                                "forward uses exactly codes*scale, the STE gradient is exact, and the "
                                                "packed export matches the QAT forward within the registered tolerance."},
                {"type": "evidence", "text": "Loss gaps to full precision, memory ratios and the fallback outcome come "
                                             "from a 2-layer CPU model on a synthetic Markov source; they do not show "
                                             "whether ternary or 4-bit weights are good enough for NAWA (P4-03a)."}],
        failure_cases=[f"criterion failed: {k}" for k in failed],
        conclusion=("Ternary and 4-bit QAT are implemented correctly and both variants learn the synthetic source "
                    "under QAT. Nothing adopted (ADR-0007 D4); the quality comparison is P4-03a."
                    if passed else f"Registered criteria failed: {', '.join(failed)}. See metrics."),
        next_action="P4-02 (Dense vs Sparse MoE vs Hybrid, code-only, ADR-0007 D5); ternary/4-bit quality on real text "
                    "waits for P4-03a (OD-03, P3-03).",
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m nawa.efficiency.p4_03")
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
