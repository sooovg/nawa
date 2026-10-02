"""P4-04: the causal convolution mixer and attention/convolution layouts are correct (ADR-0007 D2).

Nothing here is adopted (D4), and no attention:convolution ratio is adopted.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

torch = pytest.importorskip("torch")

from torch.nn import functional as F  # noqa: E402

from nawa.efficiency import conv as cv  # noqa: E402
from nawa.efficiency.p4_04 import (CONFIG, CRITERIA, IDENTITY_TOL, TOL, build, count_checks,  # noqa: E402
                                   delta_identity, receptive_field_probe, reference_and_streaming_checks,
                                   reference_core_unchanged, surgery_preserved)
from nawa.efficiency.structural import causality_violations, gradient_report  # noqa: E402
from nawa.model import DecoderConfig, NawaDecoder  # noqa: E402
from nawa.model.layers import CausalSelfAttention  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CFGS = {
    "swiglu": DecoderConfig(vocab_size=23, d_model=32, n_layers=2, n_heads=4, n_kv_heads=2, max_seq_len=32),
    "gelu_bias": DecoderConfig(vocab_size=23, d_model=24, n_layers=2, n_heads=2, max_seq_len=32, positional="learned",
                               mlp="gelu", norm="layernorm", bias=True, tie_embeddings=False),
}
CONVS = {"k4_silu": cv.ConvConfig(4, "silu"), "k3_sigmoid": cv.ConvConfig(3, "sigmoid"),
         "k1_none": cv.ConvConfig(1, "none")}
LAYOUTS = {"all": None, "first": (0,), "second": (1,)}


def model(cfg: str, conv: str | None = None, layout: str = "all", seed: int = 0) -> NawaDecoder:
    torch.manual_seed(seed)
    m = NawaDecoder(CFGS[cfg])
    if conv:
        cv.apply_conv(m, CONVS[conv], LAYOUTS[layout], seed=seed)
    return m.eval()


def toks(shape: tuple[int, int], seed: int = 1) -> torch.Tensor:
    return torch.randint(0, 23, shape, generator=torch.Generator().manual_seed(seed))


def randn(*shape: int, seed: int = 2) -> torch.Tensor:
    return torch.randn(*shape, generator=torch.Generator().manual_seed(seed))


# ---- pre-registration -------------------------------------------------------------------------------------------
def test_criteria_registered_values_and_no_ranking_criteria() -> None:
    assert TOL == 1e-5 and IDENTITY_TOL == 1e-6
    assert CRITERIA["causality_violations"] == {"op": "==", "value": 0}
    assert CRITERIA["receptive_field_violations"] == {"op": "==", "value": 0}
    for name in ("attention", "conv", "hybrid"):
        assert CRITERIA[f"{name}_margin_below_h1"] == {"op": ">=", "value": 0.10}
    assert not any(k.startswith(("loss_gap", "latency", "flops_per", "decode_state")) for k in CRITERIA)
    v = CONFIG["variants"]
    assert v["attention"] is None and v["conv"]["conv_layers"] == [0, 1] and v["hybrid"]["conv_layers"] == [0]


# ---- config validation ----------------------------------------------------------------------------------------------
@pytest.mark.parametrize("kw", [dict(kernel_size=0), dict(kernel_size=2.0), dict(kernel_size=True),
                                dict(gate="relu")])
def test_conv_config_rejects_invalid(kw: dict) -> None:
    with pytest.raises(ValueError):
        cv.ConvConfig(**kw)


@pytest.mark.parametrize("layers", [(), (2,), (0, 0), (-1,), (True,)])
def test_apply_conv_rejects_bad_layers(layers: tuple) -> None:
    with pytest.raises(ValueError):
        cv.apply_conv(NawaDecoder(CFGS["swiglu"]), cv.ConvConfig(), layers)


# ---- the convolution itself ---------------------------------------------------------------------------------------
@pytest.mark.parametrize("k", [1, 2, 4, 7])
@pytest.mark.parametrize("bias", [False, True])
def test_shifted_sum_equals_conv1d_reference(k: int, bias: bool) -> None:
    c = cv.CausalDepthwiseConv(8, k, bias=bias)
    with torch.no_grad():
        if bias:
            c.bias.copy_(randn(8, seed=3))
        x = randn(3, 13, 8)
        assert float((c(x) - c.reference(x)).abs().max()) <= TOL


def test_convolution_matches_explicit_formula() -> None:
    """y[t, c] = b[c] + sum_j w[c, j] * x[t - j, c], with zeros before position 0 (written as loops)."""
    c = cv.CausalDepthwiseConv(5, 3, bias=True)
    with torch.no_grad():
        c.bias.copy_(randn(5, seed=4))
        x = randn(2, 7, 5)
        y = c(x)
        for b in range(2):
            for t in range(7):
                for ch in range(5):
                    want = float(c.bias[ch]) + sum(float(c.weight[ch, j] * x[b, t - j, ch])
                                                   for j in range(3) if t - j >= 0)
                    assert abs(float(y[b, t, ch]) - want) <= 1e-5


def test_kernel_longer_than_sequence() -> None:
    c = cv.CausalDepthwiseConv(4, 9)
    x = randn(2, 3, 4)
    with torch.no_grad():
        assert float((c(x) - c.reference(x)).abs().max()) <= TOL


def test_negative_control_unflipped_conv1d_kernel_is_detected() -> None:
    """The reference check is not vacuous: conv1d without the flip is a different (anti-causal-lag) function."""
    c = cv.CausalDepthwiseConv(6, 4)
    x = randn(2, 11, 6)
    with torch.no_grad():
        wrong = F.conv1d(F.pad(x.transpose(1, 2), (3, 0)), c.weight.unsqueeze(1), None, groups=6).transpose(1, 2)
        assert float((c(x) - wrong).abs().max()) > 1e-2


@pytest.mark.parametrize("conv", sorted(CONVS))
@pytest.mark.parametrize("cfg", sorted(CFGS))
def test_streaming_step_equals_full_forward(conv: str, cfg: str) -> None:
    mixer = cv.ConvMixer(CFGS[cfg], CONVS[conv])
    x = randn(3, 17, CFGS[cfg].d_model)
    with torch.no_grad():
        full = mixer(x)
        state = mixer.init_state(3)
        assert state.shape == (3, CONVS[conv].kernel_size - 1, CFGS[cfg].d_model)
        ys = []
        for t in range(17):
            y, state = mixer.step(x[:, t], state)
            ys.append(y)
        assert float((torch.stack(ys, 1) - full).abs().max()) <= TOL


def test_negative_control_streaming_state_not_shifted_is_detected() -> None:
    mixer = cv.ConvMixer(CFGS["swiglu"], CONVS["k4_silu"])
    x = randn(2, 12, 32)
    with torch.no_grad():
        full = mixer(x)
        state = mixer.init_state(2)
        ys = []
        for t in range(12):
            y, _ = mixer.step(x[:, t], state)      # bug: the state never advances
            ys.append(y)
        assert float((torch.stack(ys, 1) - full).abs().max()) > 1e-2


def test_delta_kernel_identity_and_probe_checks() -> None:
    assert delta_identity(seed=0) <= IDENTITY_TOL
    r = reference_and_streaming_checks(seed=0)
    assert r["conv_vs_conv1d_reference_max_abs_diff"] <= TOL and r["streaming_vs_full_max_abs_diff"] <= TOL


def test_gate_none_has_no_gate_half() -> None:
    cfg = CFGS["swiglu"]
    assert cv.ConvMixer(cfg, CONVS["k1_none"]).in_proj.out_features == cfg.d_model
    assert cv.ConvMixer(cfg, CONVS["k4_silu"]).in_proj.out_features == 2 * cfg.d_model


# ---- model integration -------------------------------------------------------------------------------------------
@pytest.mark.parametrize("layout", sorted(LAYOUTS))
@pytest.mark.parametrize("conv", sorted(CONVS))
@pytest.mark.parametrize("cfg", sorted(CFGS))
def test_parameter_counts_closed_form(cfg: str, conv: str, layout: str) -> None:
    m = model(cfg, conv, layout)
    assert m.num_parameters() == cv.param_counts(CFGS[cfg], CONVS[conv], LAYOUTS[layout])
    assert cv.param_counts(CFGS[cfg], None, None) == model(cfg).num_parameters()


def test_counts_and_flops_against_measurement() -> None:
    assert all(count_checks(seed=0).values())


def test_surgery_keeps_every_other_weight_identical() -> None:
    assert surgery_preserved(seed=0) is True
    ref, m = model("swiglu"), model("swiglu", "k4_silu", "second")
    assert isinstance(m.blocks[0].attn, CausalSelfAttention) and isinstance(m.blocks[1].attn, cv.ConvMixer)
    sr, sm = ref.state_dict(), m.state_dict()
    for k, v in sr.items():
        if not k.startswith("blocks.1.attn."):
            assert torch.equal(v, sm[k]), k
    assert m.nawa_conv["conv_layers"] == [1]


def test_apply_conv_does_not_touch_global_rng() -> None:
    torch.manual_seed(5)
    m = NawaDecoder(CFGS["swiglu"])
    before = torch.random.get_rng_state()
    cv.apply_conv(m, cv.ConvConfig(), None, seed=3)
    assert torch.equal(before, torch.random.get_rng_state())


@pytest.mark.parametrize("layout", sorted(LAYOUTS))
@pytest.mark.parametrize("conv", sorted(CONVS))
@pytest.mark.parametrize("cfg", sorted(CFGS))
def test_causality_exact(cfg: str, conv: str, layout: str) -> None:
    assert causality_violations(model(cfg, conv, layout), 32, seed=0, trials=4) == 0


def test_negative_control_causality_detects_a_lookahead() -> None:
    m = model("swiglu", "k4_silu")
    c = m.blocks[0].attn.conv
    orig = c.forward
    c.forward = lambda x: orig(torch.roll(x, -1, dims=1))     # reads position t + 1
    assert causality_violations(m, 32, seed=0, trials=4) > 0


@pytest.mark.parametrize("conv", ["k4_silu", "k3_sigmoid"])
@pytest.mark.parametrize("cfg", sorted(CFGS))
def test_receptive_field_is_exactly_layers_times_k_minus_1(cfg: str, conv: str) -> None:
    m = model(cfg, conv)
    assert cv.receptive_field(CFGS[cfg], CONVS[conv], None) == 2 * (CONVS[conv].kernel_size - 1)
    bad, reached = receptive_field_probe(m, CONVS[conv], 32, seed=0, trials=6)
    assert bad == 0 and reached


def test_receptive_field_none_with_any_attention_block() -> None:
    assert cv.receptive_field(CFGS["swiglu"], CONVS["k4_silu"], (0,)) is None


def test_negative_control_receptive_field_probe_detects_a_longer_kernel() -> None:
    m = model("swiglu", "k4_silu")
    bad, _ = receptive_field_probe(m, cv.ConvConfig(3, "silu"), 32, seed=0, trials=6)   # claims a shorter field
    assert bad > 0


@pytest.mark.parametrize("layout", sorted(LAYOUTS))
def test_batch_invariance(layout: str) -> None:
    m = model("swiglu", "k4_silu", layout)
    x = toks((5, 32))
    with torch.no_grad():
        full = m(x).logits
        for i in range(5):
            assert float((m(x[i:i + 1]).logits[0] - full[i]).abs().max()) <= TOL


@pytest.mark.parametrize("layout", sorted(LAYOUTS))
@pytest.mark.parametrize("cfg", sorted(CFGS))
def test_gradients_reach_every_parameter(cfg: str, layout: str) -> None:
    assert all(gradient_report(model(cfg, "k4_silu", layout), 31).values())


def test_short_conv_training_reduces_loss() -> None:
    m = model("swiglu", "k4_silu").train()
    opt = torch.optim.AdamW(m.parameters(), lr=3e-3)
    x = toks((8, 25), seed=9)
    first = None
    for _ in range(40):
        loss = m(x[:, :-1], targets=x[:, 1:]).loss
        first = float(loss.detach()) if first is None else first
        opt.zero_grad()
        loss.backward()
        opt.step()
    assert float(loss.detach()) < first - 0.5


def test_flops_and_state_formulas() -> None:
    cfg = DecoderConfig(**CONFIG["model"])
    c = cv.ConvConfig(**CONFIG["variants"]["conv"]["conv"])
    # convolution layers do not grow with context; attention layers do
    assert cv.forward_flops_per_token(cfg, c, None, 64) == cv.forward_flops_per_token(cfg, c, None, 1024)
    assert cv.forward_flops_per_token(cfg, None, None, 1024) > cv.forward_flops_per_token(cfg, None, None, 64)
    assert cv.mixer_state_floats(cfg, c, None, 1024) == cfg.n_layers * (c.kernel_size - 1) * cfg.d_model
    assert cv.mixer_state_floats(cfg, None, None, 64) == cfg.n_layers * 2 * 64 * cfg.kv_heads * cfg.head_dim


# ---- governance ----------------------------------------------------------------------------------------------------
def test_reference_core_has_no_conv_and_is_pinned() -> None:
    assert not cv.conv_mixers_of(NawaDecoder(DecoderConfig.from_yaml(ROOT / "configs/base_model.yaml")))
    assert reference_core_unchanged()
    assert all(isinstance(b.attn, CausalSelfAttention) for b in build(DecoderConfig(**CONFIG["model"]), None, 0).blocks)


def test_recorded_p4_04_experiment_is_valid_and_reproducible_in_part() -> None:
    from nawa import experiments as ex
    recs = [json.loads(line) for line in (ROOT / "experiments/log.jsonl").read_text(encoding="utf-8").splitlines()]
    rec = next((r for r in recs if r.get("task_id") == "P4-04"), None)
    if rec is None:
        pytest.skip("P4-04 record not yet appended")
    assert ex.validate_p4(rec, ex.Policy.from_roadmap()) == []
    assert rec["criteria"] == CRITERIA and rec["config"] == CONFIG and rec["config_hash"] == ex.config_hash(CONFIG)
    assert rec["data_kind"] == "synthetic" and rec["artifact"] is None
    assert {c["type"] for c in rec["claims"]} <= {"correctness", "evidence"}
    from nawa.training.sanity import MarkovSource
    s = rec["seed"]
    src = MarkovSource.make(k=29, seed=s)
    train, val = src.sample(500_000, seed=s + 1), src.sample(50_000, seed=s + 2)
    assert rec["data_sha256"] == ex.sha256_bytes(ex._pack_ints(train.tolist()) + b"|" + ex._pack_ints(val.tolist()))
