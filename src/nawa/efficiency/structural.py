"""Structural variants of the reference decoder: weight sharing, low-rank, sparsity (ROADMAP P4-05, ADR-0007 D2).

These change the model, so there is no equivalence to the reference to test. P4-05 tests only their correctness:
exact parameter count, shapes, gradient flow, causality, and the one exact identity each has (full-rank
factorisation reproduces the layer; zero sparsity is the identity). Their effect on quality is P4-05a (BLOCKED,
needs licensed real text). None of them is used by the reference core (ADR-0007 D4).
"""

from __future__ import annotations

import torch
from torch import nn
from torch.nn import functional as F

from nawa.model.decoder import NawaDecoder

MLP_LINEARS = ("up", "gate", "down")


# ---- cross-layer weight sharing -------------------------------------------------------------------------------------
def share_layers(model: NawaDecoder, n_unique: int) -> NawaDecoder:
    """Layer i uses the weights of block i % n_unique (cyclic sharing). Changes the model in place."""
    n = len(model.blocks)
    if not 1 <= n_unique <= n:
        raise ValueError(f"n_unique must be in [1, {n}]")
    blocks = list(model.blocks)
    model.blocks = nn.ModuleList(blocks[i % n_unique] for i in range(n))
    return model


def block_parameters(model: NawaDecoder) -> int:
    return sum(p.numel() for p in model.blocks[0].parameters())


# ---- low-rank factorisation -----------------------------------------------------------------------------------------
class LowRankLinear(nn.Module):
    """y = B (A x) + bias, with A: (rank, in), B: (out, rank). Parameters: rank * (in + out) (+ out)."""

    def __init__(self, in_features: int, out_features: int, rank: int, bias: bool = False) -> None:
        super().__init__()
        if not 1 <= rank <= min(in_features, out_features):
            raise ValueError(f"rank must be in [1, {min(in_features, out_features)}]")
        self.rank = rank
        self.a = nn.Linear(in_features, rank, bias=False)
        self.b = nn.Linear(rank, out_features, bias=bias)

    @classmethod
    def from_linear(cls, layer: nn.Linear, rank: int) -> "LowRankLinear":
        """Truncated SVD of the layer weight (best rank-r approximation in Frobenius norm)."""
        out = cls(layer.in_features, layer.out_features, rank, bias=layer.bias is not None)
        u, s, vh = torch.linalg.svd(layer.weight.detach().double(), full_matrices=False)
        root = s[:rank].sqrt()
        with torch.no_grad():
            out.b.weight.copy_((u[:, :rank] * root).to(layer.weight.dtype))
            out.a.weight.copy_((root[:, None] * vh[:rank]).to(layer.weight.dtype))
            if layer.bias is not None:
                out.b.bias.copy_(layer.bias)
        return out

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.b(self.a(x))


def apply_low_rank(model: NawaDecoder, rank: int, names: tuple[str, ...] = MLP_LINEARS) -> NawaDecoder:
    """Replace the named MLP linears of every block with their rank-r SVD factorisation. In place."""
    for block in model.blocks:
        for name in names:
            layer = getattr(block.mlp, name)
            if isinstance(layer, nn.Linear):
                setattr(block.mlp, name, LowRankLinear.from_linear(layer, min(rank, *layer.weight.shape)))
    return model


# ---- unstructured magnitude sparsity --------------------------------------------------------------------------------
class MaskedLinear(nn.Module):
    """Linear with a fixed binary mask: y = x (W * M)^T + b. Masked weights get zero gradient."""

    def __init__(self, layer: nn.Linear, sparsity: float) -> None:
        super().__init__()
        if not 0.0 <= sparsity < 1.0:
            raise ValueError("sparsity must be in [0, 1)")
        self.weight = nn.Parameter(layer.weight.detach().clone())
        self.bias = nn.Parameter(layer.bias.detach().clone()) if layer.bias is not None else None
        n = self.weight.numel()
        keep = n - int(round(sparsity * n))
        mask = torch.zeros(n, dtype=torch.bool)
        mask[self.weight.detach().abs().flatten().topk(keep).indices] = True   # ties: topk order, deterministic
        self.register_buffer("mask", mask.view_as(self.weight), persistent=True)

    @property
    def sparsity(self) -> float:
        return 1.0 - self.mask.sum().item() / self.mask.numel()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return F.linear(x, self.weight * self.mask, self.bias)


def apply_sparsity(model: NawaDecoder, sparsity: float, names: tuple[str, ...] = MLP_LINEARS) -> NawaDecoder:
    for block in model.blocks:
        for name in names:
            layer = getattr(block.mlp, name)
            if isinstance(layer, nn.Linear):
                setattr(block.mlp, name, MaskedLinear(layer, sparsity))
    return model


# ---- shared correctness probes ----------------------------------------------------------------------------------------
@torch.no_grad()
def causality_violations(model: NawaDecoder, seq_len: int, seed: int = 0, trials: int = 4) -> int:
    """Count positions whose logits change when only a *later* token changes (must be 0)."""
    model.eval()
    g = torch.Generator().manual_seed(seed)
    bad = 0
    for _ in range(trials):
        x = torch.randint(0, model.cfg.vocab_size, (1, seq_len), generator=g)
        cut = int(torch.randint(1, seq_len, (1,), generator=g))
        y = x.clone()
        y[0, cut:] = (y[0, cut:] + 1) % model.cfg.vocab_size
        a, b = model(x).logits[0, :cut], model(y).logits[0, :cut]
        bad += int((a - b).abs().amax(-1).gt(0).sum())
    return bad


def gradient_report(model: NawaDecoder, seq_len: int, seed: int = 0) -> dict[str, bool]:
    """One backward pass: every parameter gets a finite gradient that is not all zero; masked weights get exactly 0."""
    model.train()
    g = torch.Generator().manual_seed(seed)
    x = torch.randint(0, model.cfg.vocab_size, (2, seq_len + 1), generator=g)
    model.zero_grad(set_to_none=True)
    model(x[:, :-1], targets=x[:, 1:]).loss.backward()
    grads = [p.grad for p in model.parameters()]
    masked_zero = all(bool((m.weight.grad[~m.mask] == 0).all()) for m in model.modules() if isinstance(m, MaskedLinear))
    model.zero_grad(set_to_none=True)
    model.eval()
    return {"all_have_grad": all(g_ is not None for g_ in grads),
            "all_finite": all(bool(torch.isfinite(g_).all()) for g_ in grads if g_ is not None),
            "none_all_zero": all(bool(g_.abs().sum() > 0) for g_ in grads if g_ is not None),
            "masked_grad_zero": masked_zero}
