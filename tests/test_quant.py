"""P4-03: ternary and 4-bit QAT weights are correct (ADR-0007 D2). Nothing here is adopted (D4)."""

from __future__ import annotations

import copy
import json
import math
from pathlib import Path

import pytest

torch = pytest.importorskip("torch")

from torch import nn  # noqa: E402

from nawa.efficiency import quant as q  # noqa: E402
from nawa.efficiency.p4_03 import (CONFIG, CRITERIA, FALLBACK, LOGIT_TOL, fallback_cases,  # noqa: E402
                                   reference_core_unchanged, ste_grad_diff)
from nawa.efficiency.structural import causality_violations, gradient_report  # noqa: E402
from nawa.model import DecoderConfig, NawaDecoder  # noqa: E402
from nawa.model.decoder import expected_num_parameters  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CONFIGS = {
    "rope_swiglu_gqa": dict(vocab_size=23, d_model=32, n_layers=2, n_heads=4, n_kv_heads=2, max_seq_len=24),
    "learned_gelu_bias": dict(vocab_size=23, d_model=24, n_layers=2, n_heads=2, max_seq_len=24, positional="learned",
                              mlp="gelu", norm="layernorm", bias=True, tie_embeddings=False),
}


def model(name: str, mode: str | None = None, seed: int = 0) -> NawaDecoder:
    torch.manual_seed(seed)
    m = NawaDecoder(DecoderConfig(**CONFIGS[name])).eval()
    return q.apply_quant(m, mode) if mode else m


def tokens(shape: tuple[int, int], seed: int = 1, vocab: int = 23) -> torch.Tensor:
    return torch.randint(0, vocab, shape, generator=torch.Generator().manual_seed(seed))


# ---- pre-registration ---------------------------------------------------------------------------------------------
def test_criteria_are_registered_with_the_documented_values() -> None:
    assert LOGIT_TOL == 1e-4 and FALLBACK.max_loss_gap == 0.10
    assert CRITERIA["ste_grad_max_abs_diff"] == {"op": "<=", "value": 0.0}
    assert CRITERIA["packed_forward_max_abs_logit_diff"] == {"op": "<=", "value": 1e-4}
    assert CRITERIA["qat_ternary_margin_below_h1"] == {"op": ">=", "value": 0.10}
    assert CRITERIA["qat_int4_margin_below_h1"] == {"op": ">=", "value": 0.10}
    assert not any("gap_vs_fp" in k or "fallback_outcome" in k for k in CRITERIA)   # comparisons are evidence only


# ---- codes ---------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("granularity", q.GRANULARITIES)
def test_ternary_codes_and_absmean_scale(granularity: str) -> None:
    w = torch.randn(6, 11, generator=torch.Generator().manual_seed(2))
    c, s = q.quantize(w, "ternary", granularity)
    assert c.dtype == torch.int8 and set(c.unique().tolist()) == {-1, 0, 1}
    want = w.abs().mean(dim=1, keepdim=True) if granularity == "row" else w.abs().mean().expand(6, 1)
    assert torch.allclose(s, want) and s.shape == (6, 1)
    assert torch.equal(c, torch.round(w / s).clamp(-1, 1).to(torch.int8))


@pytest.mark.parametrize("granularity", q.GRANULARITIES)
def test_int4_codes_range_symmetric_and_idempotent(granularity: str) -> None:
    w = torch.randn(6, 11, generator=torch.Generator().manual_seed(3))
    c, s = q.quantize(w, "int4", granularity)
    assert int(c.min()) >= -7 and int(c.max()) <= 7
    if granularity == "row":
        assert torch.equal(c.abs().amax(dim=1), torch.full((6,), 7, dtype=torch.int8))   # row max maps to +-7
    assert torch.equal(q.quantize(q.dequantize(c, s), "int4", granularity)[0], c)
    assert float((q.dequantize(c, s) - w).abs().max()) <= float(s.max()) / 2 + 1e-6      # error <= half a step


def test_quantize_rejects_bad_arguments_and_zero_rows_are_safe() -> None:
    with pytest.raises(ValueError):
        q.quantize(torch.zeros(3, 3), "int3")
    with pytest.raises(ValueError):
        q.quantize(torch.zeros(3, 3), "ternary", "column")
    with pytest.raises(ValueError):
        q.quantize(torch.zeros(3), "ternary")
    c, s = q.quantize(torch.zeros(2, 4), "ternary")
    assert torch.equal(c, torch.zeros(2, 4, dtype=torch.int8)) and bool(torch.isfinite(s).all())


# ---- straight-through estimator -------------------------------------------------------------------------------------
@pytest.mark.parametrize("mode", q.MODES)
def test_fake_quant_forward_is_exact_and_gradient_is_identity(mode: str) -> None:
    w = torch.randn(5, 7, generator=torch.Generator().manual_seed(4), requires_grad=True)
    y = q.fake_quant(w, mode)
    assert torch.equal(y, q.dequantize(*q.quantize(w, mode)))
    up = torch.randn(5, 7, generator=torch.Generator().manual_seed(5))
    y.backward(up)
    assert torch.equal(w.grad, up)


@pytest.mark.parametrize("name", sorted(CONFIGS))
@pytest.mark.parametrize("mode", q.MODES)
def test_ste_latent_gradient_equals_dequantized_weight_gradient(name: str, mode: str) -> None:
    assert ste_grad_diff(model(name, mode), 20, seed=3) == 0.0


def test_negative_control_detached_quantizer_loses_the_gradient(monkeypatch: pytest.MonkeyPatch) -> None:
    """The gradient check is not vacuous: a quantizer without STE gives the latent weights no gradient."""
    monkeypatch.setattr(q, "fake_quant", lambda w, mode, g="row": q.dequantize(*q.quantize(w, mode, g)))
    rep = gradient_report(model("rope_swiglu_gqa", "ternary"), 20)
    assert rep["all_have_grad"] is False


# ---- model integration -------------------------------------------------------------------------------------------
@pytest.mark.parametrize("name", sorted(CONFIGS))
@pytest.mark.parametrize("mode", q.MODES)
def test_apply_quant_scope_and_parameter_count(name: str, mode: str) -> None:
    m = model(name, mode)
    per_block = 7 if CONFIGS[name].get("mlp", "swiglu") == "swiglu" else 6
    assert len(q.quant_layers(m)) == per_block * m.cfg.n_layers
    assert isinstance(m.tok_emb, nn.Embedding) and isinstance(m.lm_head, nn.Linear)     # stated scope: not quantized
    assert m.num_parameters() == expected_num_parameters(m.cfg)                          # latent weights only
    ref = model(name)
    for a, b in zip(q.quant_layers(m), [mod for mod in ref.modules() if isinstance(mod, nn.Linear)
                                        and mod is not ref.lm_head]):
        assert torch.equal(a.weight, b.weight)                                           # same initialisation


@pytest.mark.parametrize("name", sorted(CONFIGS))
@pytest.mark.parametrize("mode", q.MODES)
def test_quantized_models_are_causal_and_trainable(name: str, mode: str) -> None:
    m = model(name, mode)
    assert causality_violations(m, 24) == 0
    assert all(gradient_report(m, 23).values())


def test_short_qat_reduces_training_loss() -> None:
    m = model("rope_swiglu_gqa", "ternary").train()
    opt = torch.optim.AdamW(m.parameters(), lr=3e-3)
    x = tokens((8, 25), seed=9)
    first = None
    for _ in range(40):
        loss = m(x[:, :-1], targets=x[:, 1:]).loss
        first = float(loss.detach()) if first is None else first
        opt.zero_grad()
        loss.backward()
        opt.step()
    assert float(loss.detach()) < first - 0.5
    assert all(set(layer.codes()[0].unique().tolist()) <= {-1, 0, 1} for layer in q.quant_layers(m))


# ---- packing and export ------------------------------------------------------------------------------------------
@pytest.mark.parametrize("mode", q.MODES)
@pytest.mark.parametrize("shape", [(1, 1), (1, 3), (3, 5), (8, 8), (17, 31)])
def test_pack_unpack_round_trip(mode: str, shape: tuple[int, int]) -> None:
    hi = 1 if mode == "ternary" else 7
    c = torch.randint(-hi, hi + 1, shape, generator=torch.Generator().manual_seed(6)).to(torch.int8)
    p = q.pack_codes(c, mode)
    assert p.dtype == torch.uint8 and p.numel() == math.ceil(c.numel() / (4 if mode == "ternary" else 2))
    assert torch.equal(q.unpack_codes(p, mode, shape), c)


def test_pack_refuses_out_of_range_codes() -> None:
    with pytest.raises(ValueError):
        q.pack_codes(torch.tensor([[2]], dtype=torch.int8), "ternary")
    with pytest.raises(ValueError):
        q.pack_codes(torch.tensor([[-8]], dtype=torch.int8), "int4")


@pytest.mark.parametrize("name", sorted(CONFIGS))
@pytest.mark.parametrize("mode", q.MODES)
def test_packed_export_matches_qat_forward_and_byte_formula(name: str, mode: str) -> None:
    m = model(name, mode)
    x = tokens((3, 24))
    with torch.no_grad():
        ref = m(x).logits
        packed = q.to_packed(copy.deepcopy(m))
        assert float((packed(x).logits - ref).abs().max()) <= LOGIT_TOL
    layers = [mod for mod in packed.modules() if isinstance(mod, q.PackedLinear)]
    assert len(layers) == len(q.quant_layers(m)) and not q.quant_layers(packed)
    rep = q.memory_report(packed)
    assert sum(mod.nbytes for mod in layers) == rep["packed_bytes"] and rep == q.memory_report(m)
    for mod in layers:
        rows, cols = mod.shape
        assert mod.nbytes == q.packed_bytes(rows * cols, rows, mode, rows if mod.bias is not None else 0)


def test_negative_control_wrong_scale_in_export_is_detected() -> None:
    m = model("rope_swiglu_gqa", "int4")
    x = tokens((2, 24))
    with torch.no_grad():
        ref = m(x).logits
        packed = q.to_packed(copy.deepcopy(m))
        for mod in packed.modules():
            if isinstance(mod, q.PackedLinear):
                mod.scale.mul_(1.1)
        assert float((packed(x).logits - ref).abs().max()) > 1e-2


def test_negative_control_unclamped_codes_are_caught(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without the clamp, ternary rounding leaves {-1, 0, 1}; the export refuses such codes."""
    w = torch.randn(4, 9, generator=torch.Generator().manual_seed(7)) * 3
    s = w.abs().mean(dim=1, keepdim=True)
    raw = torch.round(w / s).to(torch.int8)
    assert int(raw.abs().max()) > 1
    with pytest.raises(ValueError):
        q.pack_codes(raw, "ternary")


# ---- fallback rule ---------------------------------------------------------------------------------------------------
def test_fallback_rule() -> None:
    r = q.FallbackRule(0.1)
    assert q.choose_precision(1.0, 1.05, 9.0, r) == "ternary"
    assert q.choose_precision(1.0, 1.50, 1.05, r) == "int4"
    assert q.choose_precision(1.0, 1.50, 1.50, r) == "fp"
    assert q.choose_precision(1.0, math.nan, 1.0, r) == "int4"
    with pytest.raises(ValueError):
        q.FallbackRule(math.inf)
    assert fallback_cases() is True


# ---- governance ----------------------------------------------------------------------------------------------------
def test_reference_core_is_not_quantized_by_default() -> None:
    """ADR-0007 D4: nothing is adopted. The default reference has no quantized layer and its config hash is pinned."""
    assert not q.quant_layers(NawaDecoder(DecoderConfig.from_yaml(ROOT / "configs/base_model.yaml")))
    assert reference_core_unchanged()


def test_recorded_p4_03_experiment_is_valid_and_reproducible_in_part() -> None:
    from nawa import experiments as ex
    recs = [json.loads(line) for line in (ROOT / "experiments/log.jsonl").read_text(encoding="utf-8").splitlines()]
    rec = next(r for r in recs if r.get("task_id") == "P4-03")
    assert ex.validate_p4(rec, ex.Policy.from_roadmap()) == []
    assert rec["criteria"] == CRITERIA and rec["config"] == CONFIG and rec["config_hash"] == ex.config_hash(CONFIG)
    assert rec["data_kind"] == "synthetic" and rec["artifact"] is None
    assert {c["type"] for c in rec["claims"]} <= {"correctness", "evidence"}
    from nawa.training.sanity import MarkovSource
    s = rec["seed"]
    src = MarkovSource.make(k=29, seed=s)
    train, val = src.sample(500_000, seed=s + 1), src.sample(50_000, seed=s + 2)
    assert rec["data_sha256"] == ex.sha256_bytes(ex._pack_ints(train.tolist()) + b"|" + ex._pack_ints(val.tolist()))
