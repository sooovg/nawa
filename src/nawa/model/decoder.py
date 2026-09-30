"""NAWA reference decoder (ROADMAP P3-04): token embeddings → N pre-norm blocks → final norm → lm_head.

This is NAWA's own internal reference core (ADR-0003 D0). It contains no external weights and loads none.
It is deliberately plain: every later technique (ternary weights, hybrid blocks, MoE, sharing, KV cache —
ROADMAP P4) is measured against it by ablation, and is not assumed to be better.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import torch
from torch import nn
from torch.nn import functional as F

from nawa.model.config import DecoderConfig
from nawa.model.layers import DecoderBlock, build_norm

IGNORE_INDEX = -100


@dataclass
class DecoderOutput:
    logits: torch.Tensor                      # (B, T, vocab)
    loss: torch.Tensor | None = None          # mean next-token cross-entropy over non-ignored targets
    hidden_states: torch.Tensor | None = None  # (B, T, d_model) after the final norm, when requested


class NawaDecoder(nn.Module):
    def __init__(self, cfg: DecoderConfig) -> None:
        super().__init__()
        self.cfg = cfg
        self.tok_emb = nn.Embedding(cfg.vocab_size, cfg.d_model)
        self.pos_emb = nn.Embedding(cfg.max_seq_len, cfg.d_model) if cfg.positional == "learned" else None
        self.drop = nn.Dropout(cfg.dropout)
        self.blocks = nn.ModuleList(DecoderBlock(cfg) for _ in range(cfg.n_layers))
        self.final_norm = build_norm(cfg)
        self.lm_head = nn.Linear(cfg.d_model, cfg.vocab_size, bias=False)
        if cfg.tie_embeddings:
            self.lm_head.weight = self.tok_emb.weight
        self.apply(self._init_weights)

    def _init_weights(self, module: nn.Module) -> None:
        """N(0, init_std) for weights; residual output projections are scaled by 1/sqrt(2*n_layers),
        so the residual stream variance does not grow with depth at initialisation."""
        std = self.cfg.init_std
        if isinstance(module, nn.Linear):
            if getattr(module, "nawa_residual_out", False):
                std = std / math.sqrt(2 * self.cfg.n_layers)
            nn.init.normal_(module.weight, mean=0.0, std=std)
            if module.bias is not None:
                nn.init.zeros_(module.bias)
        elif isinstance(module, nn.Embedding):
            nn.init.normal_(module.weight, mean=0.0, std=std)

    def num_parameters(self, include_embeddings: bool = True) -> int:
        """Unique trainable parameters (a tied lm_head is counted once)."""
        seen: set[int] = set()
        total = 0
        for p in self.parameters():
            if id(p) in seen:
                continue
            seen.add(id(p))
            total += p.numel()
        if not include_embeddings:
            total -= self.tok_emb.weight.numel()
            if self.pos_emb is not None:
                total -= self.pos_emb.weight.numel()
        return total

    def forward(self, input_ids: torch.Tensor, targets: torch.Tensor | None = None,
                return_hidden: bool = False) -> DecoderOutput:
        if input_ids.dim() != 2:
            raise ValueError(f"input_ids must be (batch, seq), got shape {tuple(input_ids.shape)}")
        _, t = input_ids.shape
        if t > self.cfg.max_seq_len:
            raise ValueError(f"sequence length {t} exceeds max_seq_len {self.cfg.max_seq_len}")
        x = self.tok_emb(input_ids)
        if self.pos_emb is not None:
            x = x + self.pos_emb(torch.arange(t, device=input_ids.device))
        x = self.drop(x)
        for block in self.blocks:
            x = block(x)
        h = self.final_norm(x)
        logits = self.lm_head(h)
        loss = None
        if targets is not None:
            loss = F.cross_entropy(logits.reshape(-1, logits.size(-1)).float(), targets.reshape(-1),
                                   ignore_index=IGNORE_INDEX)
        return DecoderOutput(logits=logits, loss=loss, hidden_states=h if return_hidden else None)

    @torch.no_grad()
    def generate(self, input_ids: torch.Tensor, max_new_tokens: int, temperature: float = 0.0,
                 generator: torch.Generator | None = None) -> torch.Tensor:
        """Autoregressive sampling. temperature=0 is greedy. No KV cache (that is P4-05/P8-04).

        The context is cropped to the last max_seq_len tokens; with positional='learned' this means
        positions restart, which is the documented behaviour of the reference.
        """
        if max_new_tokens < 0:
            raise ValueError("max_new_tokens must be >= 0")
        if temperature < 0:
            raise ValueError("temperature must be >= 0")
        was_training = self.training
        self.eval()
        out = input_ids
        for _ in range(max_new_tokens):
            ctx = out[:, -self.cfg.max_seq_len:]
            logits = self(ctx).logits[:, -1, :]
            if temperature == 0:
                nxt = logits.argmax(dim=-1, keepdim=True)
            else:
                probs = torch.softmax(logits.float() / temperature, dim=-1)
                nxt = torch.multinomial(probs, 1, generator=generator)
            out = torch.cat([out, nxt], dim=1)
        self.train(was_training)
        return out


def expected_num_parameters(cfg: DecoderConfig) -> int:
    """Closed-form parameter count. Used by tests to check the implementation and by P4-01 scaling curves."""
    d, hd = cfg.d_model, cfg.head_dim
    norm = d * (2 if (cfg.norm == "layernorm" and cfg.bias) else 1)
    b = 1 if cfg.bias else 0
    attn = (d * cfg.n_heads * hd + b * cfg.n_heads * hd) \
        + 2 * (d * cfg.kv_heads * hd + b * cfg.kv_heads * hd) \
        + (cfg.n_heads * hd * d + b * d)
    f = cfg.resolved_d_ff
    n_in = 2 if cfg.mlp == "swiglu" else 1
    mlp = n_in * (d * f + b * f) + (f * d + b * d)
    block = 2 * norm + attn + mlp
    total = cfg.vocab_size * d + cfg.n_layers * block + norm
    if cfg.positional == "learned":
        total += cfg.max_seq_len * d
    if not cfg.tie_embeddings:
        total += cfg.vocab_size * d
    return total
