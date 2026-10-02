"""Causal convolution mixer and attention + convolution hybrid layouts of the reference core (P4-04).

Written from scratch (Track S, ADR-0007 D2). Nothing here is adopted into the reference core (D4), and no
attention:convolution ratio is adopted (ROADMAP §4 P4-04: "لا تعتمد 1:2 أو أي نسبة قبل ablation").

Definitions used by P4-04 (a stated scope, not a claim about which design is right):

* **Attention block**: the P3-04 reference block, unchanged (``x + attn(norm x)``, then ``+ mlp(norm x)``).
* **Convolution block**: the same pre-norm block with the attention sub-layer replaced by :class:`ConvMixer`:
  ``o_proj( conv(v) * act(g) )`` with ``(v, g) = in_proj(x)``. ``conv`` is a depthwise causal 1-D convolution of
  ``kernel_size`` taps per channel: ``y[t, c] = b[c] + sum_{j=0}^{K-1} w[c, j] * v[t - j, c]`` with ``v[s] = 0`` for
  ``s < 0``. ``act`` is SiLU, sigmoid, or none (then ``in_proj`` has no gate half). The MLP sub-layer is unchanged.
* **Layout**: which blocks use the convolution mixer (``conv_layers``). All attention = the reference;
  all convolution = a pure short-convolution model; anything in between is a hybrid with a stated ratio.

The convolution is computed as a sum of ``K`` shifted, element-wise scaled copies of ``v``. Every output position
reads only itself and the ``K - 1`` positions before it, with fixed shapes, so causality and the receptive field are
exact (bit for bit), not up to rounding. :meth:`CausalDepthwiseConv.reference` is an independent path through
``torch.nn.functional.conv1d`` that the shifted sum must match, and :meth:`ConvMixer.step` is the streaming form
(a rolling state of the last ``K - 1`` inputs) that must match the full forward.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass

import torch
from torch import nn
from torch.nn import functional as F

from nawa.model.config import DecoderConfig
from nawa.model.decoder import NawaDecoder, expected_num_parameters

GATES = ("silu", "sigmoid", "none")


@dataclass(frozen=True)
class ConvConfig:
    kernel_size: int = 4
    gate: str = "silu"

    def __post_init__(self) -> None:
        if not isinstance(self.kernel_size, int) or isinstance(self.kernel_size, bool) or self.kernel_size < 1:
            raise ValueError("kernel_size must be a positive int")
        if self.gate not in GATES:
            raise ValueError(f"gate must be one of {GATES}")

    def to_dict(self) -> dict:
        return asdict(self)


class CausalDepthwiseConv(nn.Module):
    """Depthwise causal convolution over time. x: (B, T, C) -> (B, T, C). ``weight[c, j]`` multiplies lag ``j``."""

    def __init__(self, channels: int, kernel_size: int, bias: bool = False) -> None:
        super().__init__()
        self.kernel_size = kernel_size
        self.weight = nn.Parameter(torch.empty(channels, kernel_size))
        self.bias = nn.Parameter(torch.zeros(channels)) if bias else None
        self.reset_parameters()

    def reset_parameters(self, generator: torch.Generator | None = None) -> None:
        """U(-1/sqrt(K), 1/sqrt(K)): the fan-in of one depthwise channel is K (stated convention)."""
        bound = 1.0 / math.sqrt(self.kernel_size)
        with torch.no_grad():
            self.weight.uniform_(-bound, bound, generator=generator)
            if self.bias is not None:
                self.bias.zero_()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        t = x.shape[1]
        y = x * self.weight[:, 0]
        for j in range(1, min(self.kernel_size, t)):
            y = y + F.pad(x[:, : t - j], (0, 0, j, 0)) * self.weight[:, j]
        return y + self.bias if self.bias is not None else y

    def reference(self, x: torch.Tensor) -> torch.Tensor:
        """Independent path: grouped ``conv1d`` with K - 1 zeros of left padding. conv1d is a cross-correlation, so
        the kernel is flipped to put lag 0 at the last tap."""
        k = self.kernel_size
        w = self.weight.flip(-1).unsqueeze(1)                                       # (C, 1, K)
        y = F.conv1d(F.pad(x.transpose(1, 2), (k - 1, 0)), w, self.bias, groups=x.shape[-1])
        return y.transpose(1, 2)

    def step(self, x_t: torch.Tensor, state: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """One position. x_t: (B, C); state: (B, K - 1, C), oldest first (zeros at the start).
        Returns y_t (B, C) and the new state."""
        window = torch.cat([state, x_t.unsqueeze(1)], dim=1)                       # (B, K, C), lag K-1 .. 0
        y = (window * self.weight.flip(-1).t().unsqueeze(0)).sum(dim=1)
        if self.bias is not None:
            y = y + self.bias
        return y, window[:, 1:]


class ConvMixer(nn.Module):
    """Gated short-convolution token mixer, a drop-in replacement for the attention sub-layer."""

    def __init__(self, cfg: DecoderConfig, conv: ConvConfig) -> None:
        super().__init__()
        self.conv_cfg = conv
        d = cfg.d_model
        self.in_proj = nn.Linear(d, d if conv.gate == "none" else 2 * d, bias=cfg.bias)
        self.conv = CausalDepthwiseConv(d, conv.kernel_size, bias=cfg.bias)
        self.o_proj = nn.Linear(d, d, bias=cfg.bias)
        self.o_proj.nawa_residual_out = True  # scaled at init like the attention output (NawaDecoder._init_weights)

    def _act(self, g: torch.Tensor) -> torch.Tensor:
        return F.silu(g) if self.conv_cfg.gate == "silu" else torch.sigmoid(g)

    def _split(self, h: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor | None]:
        if self.conv_cfg.gate == "none":
            return h, None
        v, g = h.chunk(2, dim=-1)
        return v, g

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        v, g = self._split(self.in_proj(x))
        h = self.conv(v)
        return self.o_proj(h if g is None else h * self._act(g))

    def reference_forward(self, x: torch.Tensor) -> torch.Tensor:
        v, g = self._split(self.in_proj(x))
        h = self.conv.reference(v)
        return self.o_proj(h if g is None else h * self._act(g))

    def init_state(self, batch: int, dtype: torch.dtype = torch.float32) -> torch.Tensor:
        return torch.zeros(batch, self.conv.kernel_size - 1, self.conv.weight.shape[0], dtype=dtype)

    def step(self, x_t: torch.Tensor, state: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """Streaming form. x_t: (B, d). Memory per layer is K - 1 vectors, independent of the position."""
        v, g = self._split(self.in_proj(x_t))
        h, state = self.conv.step(v, state)
        return self.o_proj(h if g is None else h * self._act(g)), state


# ---- model surgery ------------------------------------------------------------------------------------------------
def apply_conv(model: NawaDecoder, conv: ConvConfig, conv_layers: tuple[int, ...] | None = None,
               seed: int = 0) -> NawaDecoder:
    """Replace the attention sub-layer of the listed blocks (all if None) with a fresh :class:`ConvMixer`. In place.

    Linear weights use the reference init (N(0, init_std), residual outputs scaled by 1/sqrt(2 n_layers)); the
    convolution taps use :meth:`CausalDepthwiseConv.reset_parameters`. All from a dedicated generator, so the MLPs,
    norms, embeddings and the remaining attention blocks stay identical to the reference built with the same seed.
    """
    n = len(model.blocks)
    layers = tuple(range(n)) if conv_layers is None else tuple(conv_layers)
    if not layers or len(set(layers)) != len(layers) or not all(
            isinstance(i, int) and not isinstance(i, bool) and 0 <= i < n for i in layers):
        raise ValueError(f"conv_layers must be distinct block indices in [0, {n})")
    state = torch.random.get_rng_state()
    torch.manual_seed(seed)
    try:
        g = torch.Generator().manual_seed(seed)
        for i in sorted(layers):
            mixer = ConvMixer(model.cfg, conv)
            mixer.apply(model._init_weights)
            mixer.conv.reset_parameters(generator=g)
            model.blocks[i].attn = mixer
    finally:
        torch.random.set_rng_state(state)
    model.nawa_conv = {"conv": conv.to_dict(), "conv_layers": sorted(layers)}
    return model


def conv_mixers_of(model: nn.Module) -> list[ConvMixer]:
    return [m for m in model.modules() if isinstance(m, ConvMixer)]


def receptive_field(cfg: DecoderConfig, conv: ConvConfig, conv_layers: tuple[int, ...] | None) -> int | None:
    """Number of past positions an output can read: L_conv * (K - 1) when every block is convolutional, else None
    (any attention block reads the whole prefix)."""
    layers = cfg.n_layers if conv_layers is None else len(conv_layers)
    if layers < cfg.n_layers:
        return None
    return layers * (conv.kernel_size - 1)


# ---- closed forms ---------------------------------------------------------------------------------------------------
def _attn_params(cfg: DecoderConfig) -> int:
    d, hd, b = cfg.d_model, cfg.head_dim, 1 if cfg.bias else 0
    return (d * cfg.n_heads * hd + b * cfg.n_heads * hd) + 2 * (d * cfg.kv_heads * hd + b * cfg.kv_heads * hd) \
        + (cfg.n_heads * hd * d + b * d)


def mixer_params(cfg: DecoderConfig, conv: ConvConfig) -> int:
    d, b = cfg.d_model, 1 if cfg.bias else 0
    width = d if conv.gate == "none" else 2 * d
    return (d * width + b * width) + (d * conv.kernel_size + b * d) + (d * d + b * d)


def param_counts(cfg: DecoderConfig, conv: ConvConfig | None, conv_layers: tuple[int, ...] | None) -> int:
    """Closed-form parameter count (embeddings included, tied lm_head counted once). Every parameter is active for
    every token, so total = active."""
    dense = expected_num_parameters(cfg)
    if conv is None:
        return dense
    layers = cfg.n_layers if conv_layers is None else len(conv_layers)
    return dense + layers * (mixer_params(cfg, conv) - _attn_params(cfg))


def forward_flops_per_token(cfg: DecoderConfig, conv: ConvConfig | None, conv_layers: tuple[int, ...] | None,
                            seq_len: int) -> int:
    """Multiply-accumulate FLOPs (2 per MAC) of one token's forward pass at context ``seq_len``, with the P4-02
    convention: every weight matmul it touches, the attention scores and weighted sum (2 * seq_len * n_heads *
    head_dim MACs per attention layer), and the K taps per channel of each convolution (d * K MACs). Element-wise
    gates, softmax and norms are not counted. A convolution layer's cost does not depend on ``seq_len``."""
    d, hd = cfg.d_model, cfg.head_dim
    attn = d * cfg.n_heads * hd + 2 * d * cfg.kv_heads * hd + cfg.n_heads * hd * d + 2 * seq_len * cfg.n_heads * hd
    n_in = 2 if cfg.mlp == "swiglu" else 1
    mlp = (n_in + 1) * d * cfg.resolved_d_ff
    conv_set = set(range(cfg.n_layers) if conv_layers is None else conv_layers) if conv else set()
    macs = 0
    for i in range(cfg.n_layers):
        if i in conv_set:
            width = d if conv.gate == "none" else 2 * d
            macs += d * width + d * conv.kernel_size + d * d
        else:
            macs += attn
        macs += mlp
    macs += d * cfg.vocab_size   # lm_head
    return 2 * macs


def mixer_state_floats(cfg: DecoderConfig, conv: ConvConfig | None, conv_layers: tuple[int, ...] | None,
                       seq_len: int) -> int:
    """Floats of decoding state per sequence at context ``seq_len`` (evidence of the memory trade-off, not runtime
    memory): an attention layer caches keys and values, 2 * seq_len * kv_heads * head_dim; a convolution layer keeps
    its last K - 1 inputs, (K - 1) * d_model."""
    conv_set = set(range(cfg.n_layers) if conv_layers is None else conv_layers) if conv else set()
    total = 0
    for i in range(cfg.n_layers):
        if i in conv_set:
            total += (conv.kernel_size - 1) * cfg.d_model
        else:
            total += 2 * seq_len * cfg.kv_heads * cfg.head_dim
    return total
