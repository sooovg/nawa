"""P4-05: inference paths match the reference; structural variants are correct (ADR-0007 D2)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

torch = pytest.importorskip("torch")

from nawa.efficiency import kv_cache as kv  # noqa: E402
from nawa.efficiency.compiled import compiled_parity  # noqa: E402
from nawa.efficiency.p4_05 import CRITERIA, LOGIT_TOL, kv_logit_diff  # noqa: E402
from nawa.efficiency.speculative import speculative_generate  # noqa: E402
from nawa.efficiency.structural import (LowRankLinear, MaskedLinear, apply_low_rank, apply_sparsity,  # noqa: E402
                                        block_parameters, causality_violations, gradient_report, share_layers)
from nawa.model import DecoderConfig, NawaDecoder  # noqa: E402
from nawa.model.decoder import expected_num_parameters  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CONFIGS = {
    "rope_gqa": dict(vocab_size=23, d_model=32, n_layers=2, n_heads=4, n_kv_heads=2, max_seq_len=24, init_std=0.3),
    "rope_mha": dict(vocab_size=23, d_model=32, n_layers=2, n_heads=2, max_seq_len=24, init_std=0.3),
    "learned_gelu": dict(vocab_size=23, d_model=24, n_layers=2, n_heads=2, max_seq_len=24, positional="learned",
                         mlp="gelu", norm="layernorm", bias=True, tie_embeddings=False, init_std=0.3),
    "no_pos": dict(vocab_size=23, d_model=16, n_layers=1, n_heads=2, max_seq_len=24, positional="none", init_std=0.3),
}


def model(name: str, seed: int = 0) -> NawaDecoder:
    torch.manual_seed(seed)
    return NawaDecoder(DecoderConfig(**CONFIGS[name])).eval()


def prompt(n: int, seed: int = 1, vocab: int = 23) -> torch.Tensor:
    return torch.randint(0, vocab, (1, n), generator=torch.Generator().manual_seed(seed))


def test_criteria_are_registered_with_the_documented_tolerance() -> None:
    assert LOGIT_TOL == 1e-4
    assert CRITERIA["kv_max_abs_logit_diff"] == {"op": "<=", "value": 1e-4}
    assert CRITERIA["spec_token_match_rate"] == {"op": "==", "value": 1.0}


@pytest.mark.parametrize("name", sorted(CONFIGS))
def test_kv_cache_logits_match_full_forward(name: str) -> None:
    assert kv_logit_diff(model(name), prompt(5), 12) <= LOGIT_TOL


@pytest.mark.parametrize("name", sorted(CONFIGS))
def test_kv_cache_greedy_and_sampled_generation_identical(name: str) -> None:
    m = model(name)
    p = prompt(6)
    assert torch.equal(m.generate(p, 15), kv.generate_cached(m, p, 15))
    ga, gb = torch.Generator().manual_seed(3), torch.Generator().manual_seed(3)
    assert torch.equal(m.generate(p, 15, 1.0, ga), kv.generate_cached(m, p, 15, 1.0, gb))


def test_kv_cache_batched_and_beyond_max_seq_len_matches_reference() -> None:
    m = model("rope_gqa")
    p = torch.randint(0, 23, (3, 20), generator=torch.Generator().manual_seed(5))
    assert torch.equal(m.generate(p, 12), kv.generate_cached(m, p, 12))   # 20 + 12 > 24: crop fallback


def test_kv_cache_refuses_training_mode_and_overflow() -> None:
    m = model("rope_mha").train()
    with pytest.raises(ValueError):
        kv.forward_cached(m, prompt(3), kv.KVCache.empty(2))
    m.eval()
    with pytest.raises(ValueError):
        kv.forward_cached(m, prompt(25), kv.KVCache.empty(2))


def test_negative_control_wrong_rope_offset_is_detected(monkeypatch: pytest.MonkeyPatch) -> None:
    """The parity check is not vacuous: rotating new keys at position 0 must break it."""
    m = model("rope_mha")
    real = m.blocks[0].attn.rope.forward
    for block in m.blocks:
        monkeypatch.setattr(block.attn.rope, "forward", lambda x, offset=0: real(x, 0))
    assert kv_logit_diff(m, prompt(5), 10) > 1e-2


def test_negative_control_wrong_mask_is_detected(monkeypatch: pytest.MonkeyPatch) -> None:
    m = model("learned_gelu")
    orig = torch.Tensor.masked_fill
    monkeypatch.setattr(torch.Tensor, "masked_fill", lambda self, mask, v: orig(self, torch.zeros_like(mask), v))
    p = prompt(6)
    seq = m.generate(p, 6)
    monkeypatch.undo()
    with torch.no_grad():
        full = m(seq).logits
    monkeypatch.setattr(torch.Tensor, "masked_fill", lambda self, mask, v: orig(self, torch.zeros_like(mask), v))
    cached = kv.forward_cached(m, seq, kv.KVCache.empty(2))   # prefill without a causal mask sees the future
    monkeypatch.undo()
    assert float((cached - full).abs().max()) > 1e-2


@pytest.mark.parametrize("k", [1, 2, 3, 5])
def test_speculative_equals_target_greedy(k: int) -> None:
    target, draft = model("rope_gqa", 0), model("no_pos", 1)
    for s in range(4):
        p = prompt(4 + s, seed=s)
        out, st = speculative_generate(target, draft, p, 14, k)
        assert torch.equal(out, target.generate(p, 14))
        assert st.generated == 14 and st.accepted <= st.draft_tokens


def test_speculative_with_draft_equal_to_target_accepts_everything() -> None:
    target = model("rope_mha")
    out, st = speculative_generate(target, target, prompt(4), 12, 4)
    assert torch.equal(out, target.generate(prompt(4), 12))
    assert st.acceptance_rate == 1.0 and st.target_calls == 3


def test_negative_control_accept_all_draft_tokens_is_detected(monkeypatch: pytest.MonkeyPatch) -> None:
    import nawa.efficiency.speculative as spec
    target, draft = model("rope_gqa", 0), model("no_pos", 1)
    monkeypatch.setattr(spec.torch.Tensor, "cumprod", lambda self, dim: torch.ones_like(self))
    out, _ = spec.speculative_generate(target, draft, prompt(4), 14, 4)
    monkeypatch.undo()
    assert not torch.equal(out, target.generate(prompt(4), 14))


def test_speculative_refuses_out_of_scope_calls() -> None:
    t, d = model("rope_mha"), model("no_pos")
    with pytest.raises(ValueError):
        speculative_generate(t, d, torch.zeros(2, 3, dtype=torch.long), 4)
    with pytest.raises(ValueError):
        speculative_generate(t, d, prompt(20), 10)


def test_compiled_forward_matches_eager() -> None:
    res = compiled_parity(model("rope_gqa"), [prompt(9)])
    if not res["available"]:
        pytest.skip(f"torch.compile unavailable here: {res['error']}")
    assert res["max_abs_logit_diff"] <= LOGIT_TOL


# ---- structural variants: correctness only -----------------------------------------------------------------------------
BASE = dict(vocab_size=23, d_model=32, n_layers=4, n_heads=4, max_seq_len=16)


def fresh() -> NawaDecoder:
    torch.manual_seed(0)
    return NawaDecoder(DecoderConfig(**BASE)).eval()


@pytest.mark.parametrize("n_unique", [1, 2, 4])
def test_layer_sharing_parameter_count(n_unique: int) -> None:
    m = share_layers(fresh(), n_unique)
    cfg = m.cfg
    assert m.num_parameters() == expected_num_parameters(cfg) - (cfg.n_layers - n_unique) * block_parameters(m)
    assert m.blocks[0] is m.blocks[n_unique % cfg.n_layers] or n_unique == cfg.n_layers


def test_low_rank_counts_shapes_and_full_rank_identity() -> None:
    cfg = DecoderConfig(**BASE)
    lr = apply_low_rank(fresh(), 4)
    d, f = cfg.d_model, cfg.resolved_d_ff
    assert lr.num_parameters() == expected_num_parameters(cfg) - cfg.n_layers * 3 * d * f + cfg.n_layers * 3 * 4 * (d + f)
    x = prompt(16)
    assert lr(x).logits.shape == (1, 16, 23)
    full = apply_low_rank(fresh(), min(d, f))
    with torch.no_grad():
        assert float((full(x).logits - fresh()(x).logits).abs().max()) <= LOGIT_TOL
    with pytest.raises(ValueError):
        LowRankLinear(8, 4, 5)


def test_low_rank_is_best_rank_r_approximation() -> None:
    torch.manual_seed(0)
    lin = torch.nn.Linear(12, 10, bias=False)
    s = torch.linalg.svdvals(lin.weight.detach().double())
    approx = LowRankLinear.from_linear(lin, 3)
    w = (approx.b.weight @ approx.a.weight).detach().double()
    err = torch.linalg.matrix_norm(w - lin.weight.double())
    assert abs(float(err) - float(s[3:].pow(2).sum().sqrt())) < 1e-5   # Eckart–Young


@pytest.mark.parametrize("sparsity", [0.0, 0.25, 0.5, 0.9])
def test_sparsity_exact_and_masked_gradients_zero(sparsity: float) -> None:
    m = apply_sparsity(fresh(), sparsity)
    masked = [x for x in m.modules() if isinstance(x, MaskedLinear)]
    assert len(masked) == 3 * 4
    for x in masked:
        assert int((~x.mask).sum()) == int(round(sparsity * x.mask.numel()))
        kept, dropped = x.weight[x.mask].abs(), x.weight[~x.mask].abs()
        assert dropped.numel() == 0 or float(dropped.max()) <= float(kept.min())
    assert gradient_report(m, 15)["masked_grad_zero"]
    if sparsity == 0.0:
        assert torch.equal(m(prompt(16)).logits, fresh()(prompt(16)).logits)


@pytest.mark.parametrize("variant", ["shared", "low_rank", "sparse"])
def test_structural_variants_causal_and_trainable(variant: str) -> None:
    m = {"shared": lambda: share_layers(fresh(), 2), "low_rank": lambda: apply_low_rank(fresh(), 4),
         "sparse": lambda: apply_sparsity(fresh(), 0.5)}[variant]()
    assert causality_violations(m, 16) == 0
    assert all(gradient_report(m, 15).values())


def test_reference_core_untouched_by_efficiency_package() -> None:
    """ADR-0007 D4: the reference does not import the efficiency package and its default config is unchanged."""
    for path in (ROOT / "src/nawa/model").rglob("*.py"):
        assert "nawa.efficiency" not in path.read_text(encoding="utf-8"), path


def test_recorded_p4_05_experiment_is_valid_and_reproducible_in_part() -> None:
    from nawa import experiments as ex
    recs = [json.loads(line) for line in (ROOT / "experiments/log.jsonl").read_text(encoding="utf-8").splitlines()]
    rec = next(r for r in recs if r.get("task_id") == "P4-05")
    assert ex.validate_p4(rec, ex.Policy.from_roadmap()) == []
    assert rec["criteria"] == CRITERIA and rec["passed"] is True
    from nawa.efficiency.p4_05 import CONFIG
    assert rec["config"] == CONFIG and rec["config_hash"] == ex.config_hash(CONFIG)
    from nawa.training.sanity import MarkovSource
    s = rec["seed"]
    src = MarkovSource.make(k=29, seed=s)
    train, stream = src.sample(100_000, seed=s + 1), src.sample(20_000, seed=s + 2)
    assert rec["data_sha256"] == ex.sha256_bytes(ex._pack_ints(train.tolist()) + b"|" + ex._pack_ints(stream.tolist()))
