"""Ternary {-1, 0, +1} and 4-bit weights with quantization-aware training (ROADMAP P4-03, ADR-0007 D2).

Written from scratch on the P3-04 reference core (Track S). Nothing here is adopted (ADR-0007 D4): the reference core
keeps full-precision weights, and ``configs/base_model.yaml`` is unchanged. Whether ternary or 4-bit weights are good
enough is a quality question for P4-03a (BLOCKED, needs licensed real text). This module only has to be *correct*:

* **Codes.** ``ternary``: per-row absmean scale ``s = mean|w|``, codes ``clamp(round(w / s), -1, 1)``.
  ``int4``: symmetric per-row absmax scale ``s = max|w| / 7``, codes ``clamp(round(w / s), -7, 7)`` (the value -8 is
  not used, so the grid is symmetric). ``granularity="tensor"`` uses one scale for the whole matrix.
* **QAT.** The forward pass uses exactly ``codes * scale``. The backward pass is the straight-through estimator (STE):
  the gradient with respect to the dequantized weight is passed unchanged to the full-precision latent weight. The
  scale is treated as a constant in the backward pass.
* **Export.** ``PackedLinear`` stores the codes packed (ternary: 4 codes per byte, 2 bits each; int4: 2 codes per
  byte) plus one float32 scale per row, and computes ``(x @ codes^T) * scale + bias``. It must match the QAT forward.
* **Fallback.** ``choose_precision`` is the "fallback to 4-bit if ternary fails" rule of P4-03, written as code with a
  margin given by the caller. On synthetic data its outcome is evidence only, never a decision (ADR-0007 D2, D4).

Only the linear layers inside the decoder blocks are quantized (attention q/k/v/o and MLP up/gate/down). Token
embeddings, the (tied) lm_head and the norms stay in full precision. This is a stated scope, not a claim about which
layers should be quantized.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import torch
from torch import nn
from torch.nn import functional as F

from nawa.model.decoder import NawaDecoder

MODES = ("ternary", "int4")
GRANULARITIES = ("row", "tensor")
INT4_QMAX = 7
EPS = 1e-8
BLOCK_LINEARS = (("attn", "q_proj"), ("attn", "k_proj"), ("attn", "v_proj"), ("attn", "o_proj"),
                 ("mlp", "up"), ("mlp", "gate"), ("mlp", "down"))


def _check(mode: str, granularity: str) -> None:
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}, got {mode!r}")
    if granularity not in GRANULARITIES:
        raise ValueError(f"granularity must be one of {GRANULARITIES}, got {granularity!r}")


# ---- codes and scales ------------------------------------------------------------------------------------------------
@torch.no_grad()
def quantize(w: torch.Tensor, mode: str, granularity: str = "row") -> tuple[torch.Tensor, torch.Tensor]:
    """Return ``(codes int8 of w.shape, scale float of shape (rows, 1))`` for a 2-D weight ``w``."""
    _check(mode, granularity)
    if w.dim() != 2:
        raise ValueError(f"expected a 2-D weight, got shape {tuple(w.shape)}")
    a = w.detach().abs()
    if mode == "ternary":
        s = a.mean(dim=1, keepdim=True) if granularity == "row" else a.mean().expand(w.shape[0], 1)
        qmax = 1
    else:
        s = (a.amax(dim=1, keepdim=True) if granularity == "row" else a.amax().expand(w.shape[0], 1)) / INT4_QMAX
        qmax = INT4_QMAX
    s = s.clamp_min(EPS).contiguous()
    codes = torch.round(w.detach() / s).clamp(-qmax, qmax).to(torch.int8)
    return codes, s


def dequantize(codes: torch.Tensor, scale: torch.Tensor) -> torch.Tensor:
    return codes.to(scale.dtype) * scale


class _STEQuant(torch.autograd.Function):
    """Forward: exactly ``dequantize(quantize(w))``. Backward: identity to the latent weight (straight-through)."""

    @staticmethod
    def forward(ctx, w: torch.Tensor, mode: str, granularity: str) -> torch.Tensor:  # type: ignore[override]
        return dequantize(*quantize(w, mode, granularity)).to(w.dtype)

    @staticmethod
    def backward(ctx, grad: torch.Tensor):  # type: ignore[override]
        return grad, None, None


def fake_quant(w: torch.Tensor, mode: str, granularity: str = "row") -> torch.Tensor:
    return _STEQuant.apply(w, mode, granularity)


# ---- QAT layer -------------------------------------------------------------------------------------------------------
class QuantLinear(nn.Module):
    """Linear layer whose forward uses quantized weights; the full-precision latent ``weight`` is what is trained."""

    def __init__(self, layer: nn.Linear, mode: str, granularity: str = "row") -> None:
        super().__init__()
        _check(mode, granularity)
        self.mode, self.granularity = mode, granularity
        self.in_features, self.out_features = layer.in_features, layer.out_features
        self.weight = nn.Parameter(layer.weight.detach().clone())
        self.bias = nn.Parameter(layer.bias.detach().clone()) if layer.bias is not None else None

    def codes(self) -> tuple[torch.Tensor, torch.Tensor]:
        return quantize(self.weight, self.mode, self.granularity)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return F.linear(x, fake_quant(self.weight, self.mode, self.granularity), self.bias)


def _replace(model: NawaDecoder, fn) -> NawaDecoder:
    for block in model.blocks:
        for parent, name in BLOCK_LINEARS:
            owner = getattr(block, parent)
            layer = getattr(owner, name, None)
            if layer is not None:
                setattr(owner, name, fn(layer))
    return model


def apply_quant(model: NawaDecoder, mode: str, granularity: str = "row") -> NawaDecoder:
    """Replace every block linear with a ``QuantLinear``. In place. Embeddings, lm_head and norms are untouched."""
    _check(mode, granularity)
    return _replace(model, lambda layer: QuantLinear(layer, mode, granularity) if isinstance(layer, nn.Linear) else layer)


def quant_layers(model: nn.Module) -> list[QuantLinear]:
    return [m for m in model.modules() if isinstance(m, QuantLinear)]


# ---- packing ---------------------------------------------------------------------------------------------------------
def pack_codes(codes: torch.Tensor, mode: str) -> torch.Tensor:
    """Pack int8 codes into uint8: ternary 4 per byte (code + 1 in 2 bits), int4 2 per byte (code + 8 in 4 bits)."""
    flat = codes.flatten().to(torch.int16)
    if mode == "ternary":
        if flat.numel() and (flat.min() < -1 or flat.max() > 1):
            raise ValueError("ternary codes must be in {-1, 0, 1}")
        bits, per, offset = 2, 4, 1
    elif mode == "int4":
        if flat.numel() and (flat.min() < -INT4_QMAX or flat.max() > INT4_QMAX):
            raise ValueError(f"int4 codes must be in [-{INT4_QMAX}, {INT4_QMAX}]")
        bits, per, offset = 4, 2, 8
    else:
        raise ValueError(f"mode must be one of {MODES}")
    pad = (-flat.numel()) % per
    u = torch.cat([flat + offset, torch.zeros(pad, dtype=torch.int16) + offset]).view(-1, per)
    shifts = torch.arange(per, dtype=torch.int16) * bits
    return (u << shifts).sum(dim=1).to(torch.uint8)


def unpack_codes(packed: torch.Tensor, mode: str, shape: tuple[int, ...]) -> torch.Tensor:
    if mode == "ternary":
        bits, per, offset = 2, 4, 1
    elif mode == "int4":
        bits, per, offset = 4, 2, 8
    else:
        raise ValueError(f"mode must be one of {MODES}")
    n = math.prod(shape)
    p = packed.to(torch.int16)[:, None]
    shifts = torch.arange(per, dtype=torch.int16) * bits
    vals = ((p >> shifts) & ((1 << bits) - 1)).flatten()[:n] - offset
    return vals.to(torch.int8).view(shape)


def packed_bytes(n_weights: int, n_rows: int, mode: str, bias: int = 0) -> int:
    """Closed form: packed code bytes + float32 scales (+ float32 bias). Used to check ``PackedLinear.nbytes``."""
    per = 4 if mode == "ternary" else 2
    return math.ceil(n_weights / per) + 4 * n_rows + 4 * bias


class PackedLinear(nn.Module):
    """Inference-only export of a ``QuantLinear``: packed codes + float32 scales. ``y = (x @ codes^T) * scale + b``."""

    def __init__(self, layer: QuantLinear) -> None:
        super().__init__()
        codes, scale = layer.codes()
        self.mode, self.shape = layer.mode, tuple(codes.shape)
        self.register_buffer("packed", pack_codes(codes, layer.mode))
        self.register_buffer("scale", scale.detach().float().view(-1).clone())
        self.register_buffer("bias", layer.bias.detach().float().clone() if layer.bias is not None else None)

    @property
    def nbytes(self) -> int:
        return sum(t.numel() * t.element_size() for t in (self.packed, self.scale, self.bias) if t is not None)

    def codes(self) -> torch.Tensor:
        return unpack_codes(self.packed, self.mode, self.shape)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        y = (x @ self.codes().to(x.dtype).t()) * self.scale.to(x.dtype)
        return y + self.bias.to(x.dtype) if self.bias is not None else y


@torch.no_grad()
def to_packed(model: NawaDecoder) -> NawaDecoder:
    """Replace every ``QuantLinear`` with its ``PackedLinear`` export. In place; the model becomes inference-only."""
    model.eval()
    return _replace(model, lambda layer: PackedLinear(layer) if isinstance(layer, QuantLinear) else layer)


def memory_report(model: NawaDecoder) -> dict[str, int]:
    """Bytes of the quantized block linears: float32 dense vs packed export (closed form). Embeddings excluded."""
    fp32, packed, n = 0, 0, 0
    for m in model.modules():
        if isinstance(m, (QuantLinear, PackedLinear)):
            rows, cols = (m.out_features, m.in_features) if isinstance(m, QuantLinear) else m.shape
            has_bias = int(m.bias is not None)
            fp32 += 4 * (rows * cols + has_bias * rows)
            packed += packed_bytes(rows * cols, rows, m.mode, has_bias * rows)
            n += rows * cols
    return {"weights": n, "fp32_bytes": fp32, "packed_bytes": packed}


# ---- fallback rule ---------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class FallbackRule:
    """Ternary is kept for further study only if its held-out loss is within ``max_loss_gap`` nats of the
    full-precision reference trained the same way; otherwise 4-bit is tried; otherwise full precision stays."""

    max_loss_gap: float

    def __post_init__(self) -> None:
        if not (self.max_loss_gap >= 0 and math.isfinite(self.max_loss_gap)):
            raise ValueError("max_loss_gap must be a finite number >= 0")


def choose_precision(ref_loss: float, ternary_loss: float, int4_loss: float, rule: FallbackRule) -> str:
    """Return "ternary", "int4" or "fp". Non-finite losses fail their option. Not a decision on synthetic data."""
    for name, loss in (("ternary", ternary_loss), ("int4", int4_loss)):
        if math.isfinite(loss) and loss <= ref_loss + rule.max_loss_gap:
            return name
    return "fp"
