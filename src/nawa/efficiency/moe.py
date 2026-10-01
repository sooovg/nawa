"""Sparse mixture-of-experts feed-forward and the Dense / MoE / Hybrid variants of the reference core (P4-02).

Written from scratch (Track S, ADR-0007 D2). Nothing here is adopted into the reference core (D4).

Definitions used by P4-02 (a stated scope, not a claim about which layout is right):

* **Dense**: the P3-04 reference decoder, unchanged.
* **Sparse MoE**: every block's MLP is replaced by :class:`SparseMoE`: a linear router, softmax over ``n_experts``,
  the ``top_k`` experts per token, gates renormalised over the selected experts, and an optional set of always-on
  shared experts. Each expert has the reference MLP form (SwiGLU or GELU) with hidden width ``d_expert``.
* **Hybrid**: only the blocks listed in ``moe_layers`` use :class:`SparseMoE`; the others keep the dense MLP.

Routing is per token with no capacity limit, so no token is dropped and a token's output never depends on the other
tokens in the batch. That keeps the model causal and batch-invariant (a capacity limit would break both; see the
P4-02 report). The dispatch computes each expert only on the tokens routed to it, and :meth:`SparseMoE.dense_forward`
is the slow reference (every expert on every token, masked by the gates) that the dispatch must match.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import torch
from torch import nn
from torch.nn import functional as F

from nawa.model.config import DecoderConfig
from nawa.model.decoder import NawaDecoder, expected_num_parameters
from nawa.model.layers import MLP


@dataclass(frozen=True)
class MoEConfig:
    n_experts: int = 4
    top_k: int = 2
    d_expert: int | None = None        # None = reference d_ff // top_k (same active MLP width as the dense model)
    n_shared: int = 0                  # always-on experts, added to the routed output
    normalize_gates: bool = True       # renormalise the top-k gate values to sum to 1
    aux_loss_coef: float = 0.01        # weight of the load-balancing loss (Switch form, generalised to top-k)

    def __post_init__(self) -> None:
        if not isinstance(self.n_experts, int) or self.n_experts < 1:
            raise ValueError("n_experts must be a positive int")
        if not isinstance(self.top_k, int) or not 1 <= self.top_k <= self.n_experts:
            raise ValueError(f"top_k must be in [1, n_experts={self.n_experts}]")
        if self.d_expert is not None and (not isinstance(self.d_expert, int) or self.d_expert < 1):
            raise ValueError("d_expert must be a positive int or None")
        if not isinstance(self.n_shared, int) or self.n_shared < 0:
            raise ValueError("n_shared must be a non-negative int")
        if not self.aux_loss_coef >= 0:
            raise ValueError("aux_loss_coef must be >= 0")

    def expert_width(self, cfg: DecoderConfig) -> int:
        return self.d_expert if self.d_expert is not None else max(1, cfg.resolved_d_ff // self.top_k)

    def to_dict(self) -> dict:
        return asdict(self)


def _expert(cfg: DecoderConfig, width: int) -> MLP:
    """An expert is the reference MLP with hidden width ``width`` (same activation, bias and dropout)."""
    return MLP(DecoderConfig(**{**cfg.to_dict(), "d_ff": width}))


def load_balance_loss(probs: torch.Tensor, topi: torch.Tensor, n_experts: int) -> torch.Tensor:
    """E * sum_i f_i * P_i, with f_i the fraction of the N*k routing slots sent to expert i (no gradient) and P_i the
    mean router probability of expert i. Equals 1 for perfectly uniform routing; its minimum over P is reached there."""
    counts = torch.bincount(topi.flatten(), minlength=n_experts).to(probs.dtype)
    f = counts / topi.numel()
    return n_experts * (f * probs.mean(dim=0)).sum()


class SparseMoE(nn.Module):
    def __init__(self, cfg: DecoderConfig, moe: MoEConfig) -> None:
        super().__init__()
        self.moe = moe
        width = moe.expert_width(cfg)
        self.router = nn.Linear(cfg.d_model, moe.n_experts, bias=False)
        self.experts = nn.ModuleList(_expert(cfg, width) for _ in range(moe.n_experts))
        self.shared = nn.ModuleList(_expert(cfg, width) for _ in range(moe.n_shared))
        self.last_aux: torch.Tensor | None = None
        self.register_buffer("expert_tokens", torch.zeros(moe.n_experts, dtype=torch.long), persistent=False)

    # ---- routing ---------------------------------------------------------------------------------------------------
    def route(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """x: (N, d). Returns router probabilities (N, E) in float32, top-k indices (N, k) and gates (N, k)."""
        probs = torch.softmax(self.router(x).float(), dim=-1)
        topv, topi = probs.topk(self.moe.top_k, dim=-1)        # ties broken by torch.topk (deterministic on CPU)
        gates = topv / topv.sum(dim=-1, keepdim=True) if self.moe.normalize_gates else topv
        return probs, topi, gates.to(x.dtype)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        shape = x.shape
        flat = x.reshape(-1, shape[-1])
        probs, topi, gates = self.route(flat)
        self.last_aux = load_balance_loss(probs, topi, self.moe.n_experts)
        out = torch.zeros_like(flat)
        for e, expert in enumerate(self.experts):
            tok, slot = (topi == e).nonzero(as_tuple=True)
            if tok.numel() == 0:
                continue
            with torch.no_grad():
                self.expert_tokens[e] += tok.numel()
            out = out.index_add(0, tok, expert(flat[tok]) * gates[tok, slot].unsqueeze(-1))
        for expert in self.shared:
            out = out + expert(flat)
        return out.view(shape)

    def dense_forward(self, x: torch.Tensor) -> torch.Tensor:
        """Reference: every expert on every token, weighted by a dense (N, E) gate matrix that is zero off the top-k."""
        shape = x.shape
        flat = x.reshape(-1, shape[-1])
        _, topi, gates = self.route(flat)
        weights = torch.zeros(flat.shape[0], self.moe.n_experts, dtype=flat.dtype).scatter(1, topi, gates)
        out = sum(weights[:, e:e + 1] * expert(flat) for e, expert in enumerate(self.experts))
        for expert in self.shared:
            out = out + expert(flat)
        return out.view(shape)


# ---- model surgery ------------------------------------------------------------------------------------------------
def apply_moe(model: NawaDecoder, moe: MoEConfig, moe_layers: tuple[int, ...] | None = None,
              seed: int = 0) -> NawaDecoder:
    """Replace the MLP of the listed blocks (all blocks if None) with a freshly initialised SparseMoE. In place.

    New weights use the reference init (N(0, init_std), residual outputs scaled by 1/sqrt(2 n_layers)) from a
    dedicated generator, so attention, norms and embeddings stay identical to the dense model built with the same seed.
    """
    n = len(model.blocks)
    layers = tuple(range(n)) if moe_layers is None else tuple(moe_layers)
    if not layers or len(set(layers)) != len(layers) or not all(isinstance(i, int) and 0 <= i < n for i in layers):
        raise ValueError(f"moe_layers must be distinct block indices in [0, {n})")
    state = torch.random.get_rng_state()
    torch.manual_seed(seed)
    try:
        for i in sorted(layers):
            layer = SparseMoE(model.cfg, moe)
            layer.apply(model._init_weights)
            model.blocks[i].mlp = layer
    finally:
        torch.random.set_rng_state(state)
    model.nawa_moe = {"moe": moe.to_dict(), "moe_layers": sorted(layers)}
    return model


def moe_layers_of(model: nn.Module) -> list[SparseMoE]:
    return [m for m in model.modules() if isinstance(m, SparseMoE)]


def aux_loss(model: nn.Module) -> torch.Tensor:
    """Sum of the load-balancing losses of the last forward pass, times each layer's coefficient (0 if no MoE)."""
    terms = [m.moe.aux_loss_coef * m.last_aux for m in moe_layers_of(model) if m.last_aux is not None]
    return torch.stack(terms).sum() if terms else torch.zeros(())


def reset_expert_counters(model: nn.Module) -> None:
    for m in moe_layers_of(model):
        m.expert_tokens.zero_()


# ---- closed forms ---------------------------------------------------------------------------------------------------
def _mlp_params(cfg: DecoderConfig, width: int) -> int:
    b = 1 if cfg.bias else 0
    n_in = 2 if cfg.mlp == "swiglu" else 1
    return n_in * (cfg.d_model * width + b * width) + (width * cfg.d_model + b * cfg.d_model)


def param_counts(cfg: DecoderConfig, moe: MoEConfig | None, moe_layers: tuple[int, ...] | None) -> dict[str, int]:
    """Closed-form total and per-token active parameters (embeddings included, tied lm_head counted once)."""
    dense = expected_num_parameters(cfg)
    if moe is None:
        return {"total": dense, "active": dense}
    layers = cfg.n_layers if moe_layers is None else len(moe_layers)
    width = moe.expert_width(cfg)
    exp = _mlp_params(cfg, width)
    router = cfg.d_model * moe.n_experts
    removed = layers * _mlp_params(cfg, cfg.resolved_d_ff)
    total = dense - removed + layers * (router + (moe.n_experts + moe.n_shared) * exp)
    active = dense - removed + layers * (router + (moe.top_k + moe.n_shared) * exp)
    return {"total": total, "active": active}


def forward_flops_per_token(cfg: DecoderConfig, moe: MoEConfig | None, moe_layers: tuple[int, ...] | None,
                            seq_len: int) -> int:
    """Multiply-accumulate FLOPs (2 per MAC) of one token's forward pass at context ``seq_len``: every matmul with a
    weight it touches, plus the attention scores and weighted sum (2 * 2 * seq_len * n_heads * head_dim per layer).
    Element-wise ops, softmax and norms are not counted (stated convention)."""
    d, hd = cfg.d_model, cfg.head_dim
    attn_w = d * cfg.n_heads * hd + 2 * d * cfg.kv_heads * hd + cfg.n_heads * hd * d
    attn_ctx = 2 * seq_len * cfg.n_heads * hd
    n_in = 2 if cfg.mlp == "swiglu" else 1
    mlp_dense = (n_in + 1) * d * cfg.resolved_d_ff
    moe_set = set(range(cfg.n_layers) if moe_layers is None else moe_layers) if moe else set()
    macs = 0
    for i in range(cfg.n_layers):
        macs += attn_w + attn_ctx
        if i in moe_set:
            w = moe.expert_width(cfg)
            macs += d * moe.n_experts + (moe.top_k + moe.n_shared) * (n_in + 1) * d * w
        else:
            macs += mlp_dense
    macs += d * cfg.vocab_size   # lm_head
    return 2 * macs
