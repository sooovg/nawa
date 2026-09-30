"""Building blocks of the NAWA reference decoder (ROADMAP P3-04), written from scratch.

Attention is written out explicitly (scores → causal mask → softmax → weighted sum) and not
delegated to a fused kernel, so the reference is readable and testable. A fused kernel is a P4-05 / P8-04
optimisation that must match this reference (``tests/test_reference_decoder.py``).
"""

from __future__ import annotations

import math

import torch
from torch import nn
from torch.nn import functional as F

from nawa.model.config import DecoderConfig


# ---- normalisation ---------------------------------------------------------------------------
class RMSNorm(nn.Module):
    """y = x / sqrt(mean(x^2) + eps) * weight. Computed in float32 for stability."""

    def __init__(self, dim: int, eps: float = 1e-5) -> None:
        super().__init__()
        self.eps = eps
        self.weight = nn.Parameter(torch.ones(dim))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        xf = x.float() if x.dtype in (torch.float16, torch.bfloat16) else x
        y = xf * torch.rsqrt(xf.pow(2).mean(dim=-1, keepdim=True) + self.eps)
        return y.to(x.dtype) * self.weight


class LayerNorm(nn.Module):
    """y = (x - mean) / sqrt(var + eps) * weight (+ bias). Written out, not nn.LayerNorm, for readability."""

    def __init__(self, dim: int, eps: float = 1e-5, bias: bool = False) -> None:
        super().__init__()
        self.eps = eps
        self.weight = nn.Parameter(torch.ones(dim))
        self.bias = nn.Parameter(torch.zeros(dim)) if bias else None

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        mean = x.mean(dim=-1, keepdim=True)
        var = (x - mean).pow(2).mean(dim=-1, keepdim=True)
        y = (x - mean) * torch.rsqrt(var + self.eps) * self.weight
        return y + self.bias if self.bias is not None else y


def build_norm(cfg: DecoderConfig) -> nn.Module:
    if cfg.norm == "rmsnorm":
        return RMSNorm(cfg.d_model, cfg.norm_eps)
    return LayerNorm(cfg.d_model, cfg.norm_eps, bias=cfg.bias)


# ---- rotary positions --------------------------------------------------------------------------
class RotaryEmbedding(nn.Module):
    """Rotary position embedding: rotates each (even, odd) channel pair of q and k by angle pos * theta^(-2i/d).

    The rotation makes q·k depend only on the *relative* offset between positions.
    """

    def __init__(self, head_dim: int, max_seq_len: int, theta: float = 10000.0) -> None:
        super().__init__()
        inv_freq = 1.0 / (theta ** (torch.arange(0, head_dim, 2, dtype=torch.float64) / head_dim))
        angles = torch.outer(torch.arange(max_seq_len, dtype=torch.float64), inv_freq)  # (T, d/2)
        self.register_buffer("cos", angles.cos().float(), persistent=False)
        self.register_buffer("sin", angles.sin().float(), persistent=False)

    def forward(self, x: torch.Tensor, offset: int = 0) -> torch.Tensor:
        """x: (B, H, T, D). Returns x rotated for positions offset .. offset+T-1."""
        t = x.shape[-2]
        cos = self.cos[offset: offset + t].to(x.dtype)
        sin = self.sin[offset: offset + t].to(x.dtype)
        x1, x2 = x[..., 0::2], x[..., 1::2]
        out = torch.stack((x1 * cos - x2 * sin, x1 * sin + x2 * cos), dim=-1)
        return out.flatten(-2)


# ---- attention ---------------------------------------------------------------------------------
class CausalSelfAttention(nn.Module):
    """Multi-head causal self-attention with optional grouped-query heads (n_kv_heads < n_heads)."""

    def __init__(self, cfg: DecoderConfig) -> None:
        super().__init__()
        self.n_heads, self.kv_heads, self.head_dim = cfg.n_heads, cfg.kv_heads, cfg.head_dim
        self.q_proj = nn.Linear(cfg.d_model, cfg.n_heads * cfg.head_dim, bias=cfg.bias)
        self.k_proj = nn.Linear(cfg.d_model, cfg.kv_heads * cfg.head_dim, bias=cfg.bias)
        self.v_proj = nn.Linear(cfg.d_model, cfg.kv_heads * cfg.head_dim, bias=cfg.bias)
        self.o_proj = nn.Linear(cfg.n_heads * cfg.head_dim, cfg.d_model, bias=cfg.bias)
        self.o_proj.nawa_residual_out = True  # scaled at init (see NawaDecoder._init_weights)
        self.dropout = cfg.dropout
        self.rope = RotaryEmbedding(cfg.head_dim, cfg.max_seq_len, cfg.rope_theta) if cfg.positional == "rope" else None

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        b, t, _ = x.shape
        q = self.q_proj(x).view(b, t, self.n_heads, self.head_dim).transpose(1, 2)   # (B, H, T, D)
        k = self.k_proj(x).view(b, t, self.kv_heads, self.head_dim).transpose(1, 2)  # (B, Hkv, T, D)
        v = self.v_proj(x).view(b, t, self.kv_heads, self.head_dim).transpose(1, 2)
        if self.rope is not None:
            q, k = self.rope(q), self.rope(k)
        if self.kv_heads != self.n_heads:
            rep = self.n_heads // self.kv_heads
            k = k.repeat_interleave(rep, dim=1)
            v = v.repeat_interleave(rep, dim=1)
        out = causal_attention(q, k, v, dropout=self.dropout if self.training else 0.0)
        return self.o_proj(out.transpose(1, 2).reshape(b, t, self.n_heads * self.head_dim))


def causal_attention(q: torch.Tensor, k: torch.Tensor, v: torch.Tensor, dropout: float = 0.0) -> torch.Tensor:
    """softmax(q k^T / sqrt(d) + causal_mask) v, written out. Shapes: (B, H, T, D)."""
    t = q.shape[-2]
    scores = (q @ k.transpose(-2, -1)) / math.sqrt(q.shape[-1])
    mask = torch.ones(t, t, dtype=torch.bool, device=q.device).triu(1)
    scores = scores.masked_fill(mask, float("-inf"))
    probs = torch.softmax(scores.float(), dim=-1).to(q.dtype)
    if dropout:
        probs = F.dropout(probs, p=dropout)
    return probs @ v


# ---- feed-forward ------------------------------------------------------------------------------
class MLP(nn.Module):
    """gelu: W2 gelu(W1 x). swiglu: W2 (silu(Wg x) * W1 x)."""

    def __init__(self, cfg: DecoderConfig) -> None:
        super().__init__()
        hidden = cfg.resolved_d_ff
        self.kind = cfg.mlp
        self.up = nn.Linear(cfg.d_model, hidden, bias=cfg.bias)
        self.gate = nn.Linear(cfg.d_model, hidden, bias=cfg.bias) if cfg.mlp == "swiglu" else None
        self.down = nn.Linear(hidden, cfg.d_model, bias=cfg.bias)
        self.down.nawa_residual_out = True
        self.drop = nn.Dropout(cfg.dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if self.gate is not None:
            h = F.silu(self.gate(x)) * self.up(x)
        else:
            h = F.gelu(self.up(x))
        return self.drop(self.down(h))


# ---- block -------------------------------------------------------------------------------------
class DecoderBlock(nn.Module):
    """Pre-norm residual block: x + attn(norm(x)), then + mlp(norm(x))."""

    def __init__(self, cfg: DecoderConfig) -> None:
        super().__init__()
        self.attn_norm = build_norm(cfg)
        self.attn = CausalSelfAttention(cfg)
        self.mlp_norm = build_norm(cfg)
        self.mlp = MLP(cfg)
        self.drop = nn.Dropout(cfg.dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = x + self.drop(self.attn(self.attn_norm(x)))
        return x + self.mlp(self.mlp_norm(x))
