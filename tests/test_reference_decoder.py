"""Correctness tests for the NAWA reference decoder (ROADMAP P3-04).

These check mathematical properties, not quality: causality, equivalence with an independent attention
reference, relative-position behaviour of RoPE, closed-form parameter counts, gradients (including a
float64 gradcheck), determinism, and config validation. Learning checks (XOR, tiny LM) belong to P3-05.
"""

from __future__ import annotations

import itertools
import math
import os

import pytest

if os.environ.get("NAWA_REQUIRE_TORCH") == "1":
    import torch  # CI must fail loudly, not skip, if torch is missing
else:
    torch = pytest.importorskip("torch")

from torch.nn import functional as F  # noqa: E402

from nawa.model import (  # noqa: E402
    IGNORE_INDEX, DecoderConfig, ModelConfigError, NawaDecoder, expected_num_parameters,
)
from nawa.model.layers import LayerNorm, RMSNorm, RotaryEmbedding, causal_attention  # noqa: E402

TINY = dict(vocab_size=37, d_model=32, n_layers=2, n_heads=4, max_seq_len=16)
VARIANTS = list(itertools.product(("rmsnorm", "layernorm"), ("swiglu", "gelu"), ("rope", "learned", "none")))


def make(seed: int = 0, **over) -> NawaDecoder:
    torch.manual_seed(seed)
    return NawaDecoder(DecoderConfig(**{**TINY, **over})).eval()


def ids(b: int = 2, t: int = 10, vocab: int = TINY["vocab_size"], seed: int = 1) -> torch.Tensor:
    g = torch.Generator().manual_seed(seed)
    return torch.randint(0, vocab, (b, t), generator=g)


# ---- config -------------------------------------------------------------------------------------
@pytest.mark.parametrize("bad", [
    dict(d_model=30, n_heads=4),               # not divisible
    dict(n_kv_heads=3),                        # not a divisor of n_heads
    dict(norm="batchnorm"), dict(mlp="relu"), dict(positional="alibi"),
    dict(vocab_size=0), dict(dropout=1.0), dict(d_model=36, n_heads=4, positional="rope"),  # odd head_dim
])
def test_invalid_configs_are_rejected(bad: dict) -> None:
    with pytest.raises(ModelConfigError):
        DecoderConfig(**{**TINY, **bad})


def test_config_hash_is_stable_and_sensitive() -> None:
    a, b = DecoderConfig(**TINY), DecoderConfig(**TINY)
    assert a.config_hash() == b.config_hash() and len(a.config_hash()) == 16
    assert a.config_hash() != DecoderConfig(**{**TINY, "norm": "layernorm"}).config_hash()


def test_from_dict_rejects_unknown_keys() -> None:
    with pytest.raises(ModelConfigError):
        DecoderConfig.from_dict({**TINY, "n_expertz": 8})


def test_base_model_yaml_loads() -> None:
    cfg = DecoderConfig.from_yaml("configs/base_model.yaml")
    assert cfg.resolved_d_ff == 688 and cfg.positional == "rope"
    model = NawaDecoder(cfg)
    assert model.num_parameters() == expected_num_parameters(cfg)


# ---- shapes, parameter count, variants ---------------------------------------------------------
@pytest.mark.parametrize("norm,mlp,pos", VARIANTS)
def test_every_variant_runs_and_matches_closed_form_param_count(norm: str, mlp: str, pos: str) -> None:
    for extra in (dict(), dict(bias=True, tie_embeddings=False, n_kv_heads=2)):
        cfg = DecoderConfig(**{**TINY, "norm": norm, "mlp": mlp, "positional": pos, **extra})
        model = NawaDecoder(cfg)
        out = model(ids(), return_hidden=True)
        assert out.logits.shape == (2, 10, TINY["vocab_size"])
        assert out.hidden_states.shape == (2, 10, TINY["d_model"])
        assert torch.isfinite(out.logits).all()
        assert model.num_parameters() == expected_num_parameters(cfg), (norm, mlp, pos, extra)


def test_tied_embeddings_share_storage() -> None:
    tied, untied = make(), make(tie_embeddings=False)
    assert tied.lm_head.weight.data_ptr() == tied.tok_emb.weight.data_ptr()
    assert untied.lm_head.weight.data_ptr() != untied.tok_emb.weight.data_ptr()
    assert untied.num_parameters() - tied.num_parameters() == TINY["vocab_size"] * TINY["d_model"]


def test_sequence_longer_than_max_is_rejected() -> None:
    with pytest.raises(ValueError):
        make()(ids(t=TINY["max_seq_len"] + 1))


# ---- causality ---------------------------------------------------------------------------------
@pytest.mark.parametrize("norm,mlp,pos", VARIANTS)
def test_future_tokens_do_not_affect_past_logits(norm: str, mlp: str, pos: str) -> None:
    model = make(norm=norm, mlp=mlp, positional=pos, n_kv_heads=2)
    x = ids(b=1, t=12)
    base = model(x).logits
    for cut in (0, 5, 11):
        y = x.clone()
        y[0, cut:] = (y[0, cut:] + 1) % TINY["vocab_size"]
        changed = model(y).logits
        torch.testing.assert_close(changed[:, :cut], base[:, :cut], rtol=0, atol=1e-6)
        assert not torch.allclose(changed[:, cut], base[:, cut])


# ---- attention and norms against independent references ----------------------------------------
def test_attention_matches_pytorch_reference_kernel() -> None:
    g = torch.Generator().manual_seed(3)
    q, k, v = (torch.randn(2, 4, 9, 8, generator=g) for _ in range(3))
    ref = F.scaled_dot_product_attention(q, k, v, is_causal=True)
    torch.testing.assert_close(causal_attention(q, k, v), ref, rtol=1e-5, atol=1e-6)


def test_grouped_query_attention_equals_mha_with_repeated_kv_weights() -> None:
    gqa = make(n_kv_heads=2)
    mha = make(n_kv_heads=None)
    mha.load_state_dict({k: v for k, v in gqa.state_dict().items() if ".attn.k_proj" not in k
                         and ".attn.v_proj" not in k}, strict=False)
    hd, rep = TINY["d_model"] // TINY["n_heads"], TINY["n_heads"] // 2
    for gb, mb in zip(gqa.blocks, mha.blocks):
        for name in ("k_proj", "v_proj"):
            w = getattr(gb.attn, name).weight.view(2, hd, TINY["d_model"])
            getattr(mb.attn, name).weight.data.copy_(w.repeat_interleave(rep, dim=0).reshape(-1, TINY["d_model"]))
    x = ids()
    torch.testing.assert_close(gqa(x).logits, mha(x).logits, rtol=1e-5, atol=1e-5)


def test_rmsnorm_and_layernorm_match_formulas() -> None:
    x = torch.randn(3, 5, 16, dtype=torch.float64)
    rms = RMSNorm(16).double()
    torch.testing.assert_close(rms(x), x / torch.sqrt((x ** 2).mean(-1, keepdim=True) + 1e-5))
    ln = LayerNorm(16, bias=True).double()
    torch.testing.assert_close(ln(x), F.layer_norm(x, (16,), eps=1e-5))


def test_rope_scores_depend_only_on_relative_offset() -> None:
    rope = RotaryEmbedding(head_dim=8, max_seq_len=64).double()
    g = torch.Generator().manual_seed(4)
    q, k = torch.randn(8, generator=g, dtype=torch.float64), torch.randn(8, generator=g, dtype=torch.float64)

    def score(pq: int, pk: int) -> float:
        qr = rope(q.view(1, 1, 1, 8), offset=pq)
        kr = rope(k.view(1, 1, 1, 8), offset=pk)
        return float((qr * kr).sum())

    # The cos/sin tables are stored in float32 (computed in float64, then cast), so equality holds to
    # float32 precision (measured relative gap about 2e-8), not to float64 precision.
    assert math.isclose(score(10, 7), score(40, 37), rel_tol=1e-6)
    assert math.isclose(score(3, 3), float(q @ k), rel_tol=1e-6)   # zero offset = no rotation
    assert not math.isclose(score(10, 7), score(10, 2), rel_tol=1e-6)


def test_rope_preserves_vector_norm() -> None:
    rope = RotaryEmbedding(head_dim=8, max_seq_len=32)
    x = torch.randn(2, 3, 20, 8)
    torch.testing.assert_close(rope(x).norm(dim=-1), x.norm(dim=-1), rtol=1e-5, atol=1e-5)


# ---- loss and gradients ------------------------------------------------------------------------
def test_initial_loss_is_close_to_uniform_entropy() -> None:
    cfg = DecoderConfig(**{**TINY, "vocab_size": 256, "max_seq_len": 64})
    torch.manual_seed(0)
    x = torch.randint(0, 256, (8, 64))
    loss = NawaDecoder(cfg)(x[:, :-1], targets=x[:, 1:]).loss.item()
    assert abs(loss - math.log(256)) < 0.1, loss


def test_ignore_index_targets_are_excluded_from_loss() -> None:
    model, x = make(), ids()
    targets = x.clone()
    targets[:, 5:] = IGNORE_INDEX
    logits = model(x).logits
    manual = F.cross_entropy(logits[:, :5].reshape(-1, logits.size(-1)), x[:, :5].reshape(-1))
    torch.testing.assert_close(model(x, targets=targets).loss, manual)


def test_every_parameter_receives_a_gradient() -> None:
    model = make(tie_embeddings=False, bias=True, positional="learned").train()
    x = ids(t=12)
    model(x[:, :-1], targets=x[:, 1:]).loss.backward()
    missing = [n for n, p in model.named_parameters() if p.grad is None or not p.grad.abs().sum() > 0]
    assert not missing, missing


def test_float64_gradcheck() -> None:
    cfg = DecoderConfig(vocab_size=7, d_model=8, n_layers=1, n_heads=2, max_seq_len=6)
    torch.manual_seed(0)
    model = NawaDecoder(cfg).double()
    x = torch.randint(0, 7, (1, 5))

    def f(emb: torch.Tensor) -> torch.Tensor:
        h = emb[x]
        for blk in model.blocks:
            h = blk(h)
        return model.lm_head(model.final_norm(h)).sum()

    emb = model.tok_emb.weight.detach().clone().requires_grad_(True)
    assert torch.autograd.gradcheck(f, (emb,), eps=1e-6, atol=1e-5)


# ---- determinism and generation ---------------------------------------------------------------
def test_same_seed_gives_identical_weights_and_outputs() -> None:
    a, b, c = make(seed=7), make(seed=7), make(seed=8)
    x = ids()
    assert torch.equal(a(x).logits, b(x).logits)
    assert not torch.equal(a(x).logits, c(x).logits)


def test_generate_greedy_is_deterministic_and_consistent_with_forward() -> None:
    model, prompt = make(), ids(b=2, t=4)
    out = model.generate(prompt, max_new_tokens=6)
    assert out.shape == (2, 10) and torch.equal(out[:, :4], prompt)
    assert torch.equal(out, model.generate(prompt, max_new_tokens=6))
    first = model(prompt).logits[:, -1].argmax(-1)
    assert torch.equal(out[:, 4], first)


def test_generate_sampling_is_reproducible_with_a_generator_and_crops_context() -> None:
    model, prompt = make(), ids(b=1, t=3)
    run = lambda s: model.generate(prompt, 20, temperature=1.0, generator=torch.Generator().manual_seed(s))  # noqa: E731
    assert torch.equal(run(5), run(5))
    assert run(5).shape == (1, 23)   # longer than max_seq_len=16: context is cropped, no error
    with pytest.raises(ValueError):
        model.generate(prompt, 1, temperature=-1.0)
