"""P4-02: Sparse MoE and Hybrid variants are correct (ADR-0007 D2). Nothing here is adopted (D4)."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

torch = pytest.importorskip("torch")

from torch import nn  # noqa: E402

from nawa.efficiency import moe as mo  # noqa: E402
from nawa.efficiency.p4_02 import (CONFIG, CRITERIA, IDENTITY_TOL, TOL, aux_checks, build,  # noqa: E402
                                   causality_probe, count_checks, identity_checks, reference_core_unchanged)
from nawa.efficiency.structural import gradient_report  # noqa: E402
from nawa.model import DecoderConfig, NawaDecoder  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CFGS = {
    "swiglu": DecoderConfig(vocab_size=23, d_model=32, n_layers=2, n_heads=4, n_kv_heads=2, max_seq_len=24),
    "gelu_bias": DecoderConfig(vocab_size=23, d_model=24, n_layers=2, n_heads=2, max_seq_len=24, positional="learned",
                               mlp="gelu", norm="layernorm", bias=True, tie_embeddings=False),
}
MOES = {"top2": (mo.MoEConfig(4, 2), None), "hybrid": (mo.MoEConfig(4, 2), (1,)),
        "shared": (mo.MoEConfig(3, 1, d_expert=16, n_shared=1), (0,))}


def model(cfg: str, moe: str | None = None, seed: int = 0) -> NawaDecoder:
    torch.manual_seed(seed)
    m = NawaDecoder(CFGS[cfg])
    if moe:
        mc, layers = MOES[moe]
        mo.apply_moe(m, mc, layers, seed=seed)
    return m.eval()


def toks(shape: tuple[int, int], seed: int = 1) -> torch.Tensor:
    return torch.randint(0, 23, shape, generator=torch.Generator().manual_seed(seed))


# ---- pre-registration -------------------------------------------------------------------------------------------
def test_criteria_registered_values_and_no_ranking_criteria() -> None:
    assert TOL == 1e-5 and IDENTITY_TOL == 1e-6
    assert CRITERIA["moe_dense_path_causality_violations"] == {"op": "==", "value": 0}
    assert CRITERIA["moe_dispatch_causality_max_abs_diff"] == {"op": "<=", "value": TOL}
    for name in ("dense", "moe", "hybrid"):
        assert CRITERIA[f"{name}_margin_below_h1"] == {"op": ">=", "value": 0.10}
    assert not any(k.startswith(("loss_gap", "latency", "param_bytes")) for k in CRITERIA)   # evidence only
    v = CONFIG["variants"]
    assert v["dense"] is None and v["moe"]["moe_layers"] == [0, 1] and v["hybrid"]["moe_layers"] == [1]


# ---- config validation ----------------------------------------------------------------------------------------------
@pytest.mark.parametrize("kw", [dict(n_experts=0), dict(top_k=0), dict(n_experts=2, top_k=3), dict(d_expert=0),
                                dict(n_shared=-1), dict(aux_loss_coef=-1.0)])
def test_moe_config_rejects_invalid(kw: dict) -> None:
    with pytest.raises(ValueError):
        mo.MoEConfig(**kw)


@pytest.mark.parametrize("layers", [(), (2,), (0, 0), (-1,)])
def test_apply_moe_rejects_bad_layers(layers: tuple[int, ...]) -> None:
    with pytest.raises(ValueError):
        mo.apply_moe(NawaDecoder(CFGS["swiglu"]), mo.MoEConfig(), layers)


def test_default_expert_width_keeps_active_mlp_width() -> None:
    cfg = CFGS["swiglu"]
    assert mo.MoEConfig(4, 2).expert_width(cfg) == cfg.resolved_d_ff // 2


# ---- routing and dispatch -----------------------------------------------------------------------------------------
@pytest.mark.parametrize("cfg", sorted(CFGS))
@pytest.mark.parametrize("moe", sorted(MOES))
def test_dispatch_equals_dense_masked_reference(cfg: str, moe: str) -> None:
    layer = mo.SparseMoE(CFGS[cfg], MOES[moe][0])
    x = torch.randn(3, 11, CFGS[cfg].d_model, generator=torch.Generator().manual_seed(2))
    with torch.no_grad():
        assert float((layer(x) - layer.dense_forward(x)).abs().max()) <= TOL


def test_gates_are_normalised_topk_of_softmax() -> None:
    layer = mo.SparseMoE(CFGS["swiglu"], mo.MoEConfig(5, 2))
    x = torch.randn(9, 32, generator=torch.Generator().manual_seed(3))
    probs, topi, gates = layer.route(x)
    assert torch.allclose(probs.sum(-1), torch.ones(9))
    assert torch.equal(topi, probs.topk(2, -1).indices)
    assert torch.allclose(gates.sum(-1), torch.ones(9))
    raw = mo.SparseMoE(CFGS["swiglu"], mo.MoEConfig(5, 2, normalize_gates=False))
    raw.load_state_dict(layer.state_dict())
    assert torch.allclose(raw.route(x)[2], probs.topk(2, -1).values)


def test_each_expert_runs_only_on_its_tokens_and_counts_match() -> None:
    layer = mo.SparseMoE(CFGS["swiglu"], mo.MoEConfig(4, 2))
    seen = [0] * 4
    for i, e in enumerate(layer.experts):
        e.up.register_forward_hook(lambda mod, inp, out, i=i: seen.__setitem__(i, seen[i] + inp[0].shape[0]))
    x = torch.randn(2, 13, 32, generator=torch.Generator().manual_seed(4))
    with torch.no_grad():
        layer(x)
        topi = layer.route(x.reshape(-1, 32))[1]
    want = torch.bincount(topi.flatten(), minlength=4).tolist()
    assert seen == want == layer.expert_tokens.tolist() and sum(seen) == 2 * 26


def test_negative_control_wrong_slot_gate_is_detected(monkeypatch: pytest.MonkeyPatch) -> None:
    """The dispatch check is not vacuous: using the first gate for every slot breaks the equality."""
    layer = mo.SparseMoE(CFGS["swiglu"], mo.MoEConfig(4, 2))
    x = torch.randn(2, 9, 32, generator=torch.Generator().manual_seed(5))
    real_route = layer.route

    def bad_route(flat: torch.Tensor):
        probs, topi, gates = real_route(flat)
        return probs, topi, gates[:, :1].expand_as(gates).contiguous()

    with torch.no_grad():
        ref = layer.dense_forward(x)
        monkeypatch.setattr(layer, "route", bad_route)
        assert float((layer(x) - ref).abs().max()) > 1e-3


# ---- exact identities -----------------------------------------------------------------------------------------------
def test_identities_single_expert_and_equal_experts() -> None:
    r = identity_checks(seed=0)
    assert r["single_expert_identity_max_abs_diff"] <= IDENTITY_TOL
    assert r["equal_experts_identity_max_abs_diff"] <= TOL


def test_negative_control_unnormalised_gates_break_equal_experts_identity() -> None:
    torch.manual_seed(0)
    dense = NawaDecoder(CFGS["swiglu"]).eval()
    m = mo.apply_moe(copy.deepcopy(dense), mo.MoEConfig(4, 2, d_expert=CFGS["swiglu"].resolved_d_ff,
                                                        normalize_gates=False))
    for block, ref in zip(m.blocks, dense.blocks):
        for e in block.mlp.experts:
            e.load_state_dict(ref.mlp.state_dict())
    x = toks((2, 16))
    with torch.no_grad():
        assert float((m(x).logits - dense(x).logits).abs().max()) > 1e-3


# ---- model integration -------------------------------------------------------------------------------------------
@pytest.mark.parametrize("cfg", sorted(CFGS))
@pytest.mark.parametrize("moe", sorted(MOES))
def test_parameter_counts_closed_form(cfg: str, moe: str) -> None:
    mc, layers = MOES[moe]
    m = model(cfg, moe)
    pc = mo.param_counts(CFGS[cfg], mc, layers)
    assert m.num_parameters() == pc["total"] and pc["active"] <= pc["total"]
    assert mo.param_counts(CFGS[cfg], None, None)["total"] == model(cfg).num_parameters()


def test_counts_active_params_and_flops_against_measurement() -> None:
    assert all(count_checks(seed=0).values())


def test_apply_moe_keeps_non_mlp_weights_identical_to_dense() -> None:
    dense, m = model("swiglu"), model("swiglu", "hybrid")
    assert isinstance(m.blocks[0].mlp, type(dense.blocks[0].mlp)) and isinstance(m.blocks[1].mlp, mo.SparseMoE)
    sd, sm = dense.state_dict(), m.state_dict()
    for k, v in sd.items():
        if not k.startswith("blocks.1.mlp."):
            assert torch.equal(v, sm[k]), k
    assert m.nawa_moe["moe_layers"] == [1]


@pytest.mark.parametrize("cfg", sorted(CFGS))
@pytest.mark.parametrize("moe", sorted(MOES))
def test_causal_exact_on_dense_path_and_within_tol_on_dispatch(cfg: str, moe: str) -> None:
    m = model(cfg, moe)
    assert causality_probe(m, 24, 0, dense_path=True)[0] == 0
    assert causality_probe(m, 24, 0, dense_path=False)[1] <= TOL


def test_negative_control_causality_probe_detects_a_leak() -> None:
    """Mixing the sequence mean into the MoE input (a future-token leak) must be caught on the dense path."""
    m = model("swiglu", "top2")
    layer = m.blocks[0].mlp
    orig = layer.dense_forward
    layer.dense_forward = lambda x: orig(x + x.mean(dim=1, keepdim=True))
    assert causality_probe(m, 24, 0, dense_path=True)[0] > 0


@pytest.mark.parametrize("moe", sorted(MOES))
def test_batch_invariance(moe: str) -> None:
    m = model("swiglu", moe)
    x = toks((5, 24))
    with torch.no_grad():
        full = m(x).logits
        for i in range(5):
            assert float((m(x[i:i + 1]).logits[0] - full[i]).abs().max()) <= TOL


@pytest.mark.parametrize("cfg", sorted(CFGS))
@pytest.mark.parametrize("moe", sorted(MOES))
def test_gradients_reach_router_and_experts(cfg: str, moe: str) -> None:
    assert all(gradient_report(model(cfg, moe), 23).values())


# ---- load-balance loss ----------------------------------------------------------------------------------------------
def test_aux_loss_checks() -> None:
    assert aux_checks(seed=0) is True


def test_aux_loss_is_collected_with_gradient() -> None:
    m = model("swiglu", "top2").train()
    x = toks((4, 24))
    m(x)
    a = mo.aux_loss(m)
    assert a.requires_grad and float(a.detach()) > 0
    assert float(mo.aux_loss(model("swiglu"))) == 0.0


def test_short_moe_training_reduces_loss() -> None:
    m = model("swiglu", "top2").train()
    opt = torch.optim.AdamW(m.parameters(), lr=3e-3)
    x = toks((8, 25), seed=9)
    first = None
    for _ in range(40):
        loss = m(x[:, :-1], targets=x[:, 1:]).loss + mo.aux_loss(m)
        first = float(loss.detach()) if first is None else first
        opt.zero_grad()
        loss.backward()
        opt.step()
    assert float(loss.detach()) < first - 0.5


def test_flops_formula_dense_matches_and_moe_iso_active() -> None:
    cfg = DecoderConfig(**CONFIG["model"])
    moe = mo.MoEConfig(**CONFIG["variants"]["moe"]["moe"])
    dense = mo.forward_flops_per_token(cfg, None, None, 64)
    sparse = mo.forward_flops_per_token(cfg, moe, None, 64)
    assert sparse - dense == 2 * cfg.n_layers * cfg.d_model * moe.n_experts      # only the router is extra


# ---- governance ----------------------------------------------------------------------------------------------------
def test_reference_core_has_no_moe_and_is_pinned() -> None:
    assert not mo.moe_layers_of(NawaDecoder(DecoderConfig.from_yaml(ROOT / "configs/base_model.yaml")))
    assert reference_core_unchanged()
    assert isinstance(build(DecoderConfig(**CONFIG["model"]), None, 0).blocks[0].mlp, nn.Module)


def test_recorded_p4_02_experiment_is_valid_and_reproducible_in_part() -> None:
    from nawa import experiments as ex
    recs = [json.loads(line) for line in (ROOT / "experiments/log.jsonl").read_text(encoding="utf-8").splitlines()]
    rec = next(r for r in recs if r.get("task_id") == "P4-02")
    assert ex.validate_p4(rec, ex.Policy.from_roadmap()) == []
    assert rec["criteria"] == CRITERIA and rec["config"] == CONFIG and rec["config_hash"] == ex.config_hash(CONFIG)
    assert rec["data_kind"] == "synthetic" and rec["artifact"] is None
    assert {c["type"] for c in rec["claims"]} <= {"correctness", "evidence"}
    from nawa.training.sanity import MarkovSource
    s = rec["seed"]
    src = MarkovSource.make(k=29, seed=s)
    train, val = src.sample(500_000, seed=s + 1), src.sample(50_000, seed=s + 2)
    assert rec["data_sha256"] == ex.sha256_bytes(ex._pack_ints(train.tolist()) + b"|" + ex._pack_ints(val.tolist()))
