"""KV cache for the reference decoder (ROADMAP P4-05, ADR-0007 D2).

The reference ``NawaDecoder`` recomputes the whole context at every generated token. This module reuses the *same*
modules and weights, but keeps each layer's keys and values (after RoPE, before GQA repetition), so each new token
costs one position instead of the whole context. It changes no weight and no config: it is an inference path that
must match the reference within the tolerance registered in ``nawa.efficiency.p4_05``.

Limits (documented, tested):

* eval mode only (dropout would make the two paths differ by design);
* while the sequence fits in ``max_seq_len`` the cache is used; beyond it the reference crops the context to the last
  ``max_seq_len`` tokens (positions restart), so this path falls back to the same full recomputation on the cropped
  window and the result stays identical.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import torch
from nawa.model.decoder import NawaDecoder
from nawa.model.layers import CausalSelfAttention


@dataclass
class KVCache:
    keys: list[torch.Tensor | None] = field(default_factory=list)    # per layer (B, Hkv, T, D)
    values: list[torch.Tensor | None] = field(default_factory=list)
    length: int = 0

    @classmethod
    def empty(cls, n_layers: int) -> "KVCache":
        return cls([None] * n_layers, [None] * n_layers, 0)


def _attention_step(attn: CausalSelfAttention, x: torch.Tensor, cache: KVCache, layer: int) -> torch.Tensor:
    """Attention for the new positions ``cache.length .. cache.length + t - 1`` against cached + new keys."""
    b, t, _ = x.shape
    offset = cache.length
    q = attn.q_proj(x).view(b, t, attn.n_heads, attn.head_dim).transpose(1, 2)
    k = attn.k_proj(x).view(b, t, attn.kv_heads, attn.head_dim).transpose(1, 2)
    v = attn.v_proj(x).view(b, t, attn.kv_heads, attn.head_dim).transpose(1, 2)
    if attn.rope is not None:
        q, k = attn.rope(q, offset=offset), attn.rope(k, offset=offset)
    if cache.keys[layer] is not None:
        k = torch.cat([cache.keys[layer], k], dim=2)
        v = torch.cat([cache.values[layer], v], dim=2)
    cache.keys[layer], cache.values[layer] = k, v
    if attn.kv_heads != attn.n_heads:
        rep = attn.n_heads // attn.kv_heads
        k, v = k.repeat_interleave(rep, dim=1), v.repeat_interleave(rep, dim=1)
    total = k.shape[-2]
    scores = (q @ k.transpose(-2, -1)) / math.sqrt(q.shape[-1])
    # query i sits at absolute position offset + i and may see keys 0 .. offset + i
    mask = torch.arange(total, device=x.device)[None, :] > (offset + torch.arange(t, device=x.device))[:, None]
    scores = scores.masked_fill(mask, float("-inf"))
    probs = torch.softmax(scores.float(), dim=-1).to(q.dtype)
    out = probs @ v
    return attn.o_proj(out.transpose(1, 2).reshape(b, t, attn.n_heads * attn.head_dim))


@torch.no_grad()
def forward_cached(model: NawaDecoder, input_ids: torch.Tensor, cache: KVCache) -> torch.Tensor:
    """Logits for ``input_ids`` appended after the cached prefix; updates ``cache`` in place. (B, t, vocab)."""
    if model.training:
        raise ValueError("forward_cached needs eval mode (dropout would make it differ from the reference)")
    t = input_ids.shape[1]
    if cache.length + t > model.cfg.max_seq_len:
        raise ValueError(f"cached length {cache.length} + {t} exceeds max_seq_len {model.cfg.max_seq_len}")
    x = model.tok_emb(input_ids)
    if model.pos_emb is not None:
        x = x + model.pos_emb(torch.arange(cache.length, cache.length + t, device=input_ids.device))
    for i, block in enumerate(model.blocks):
        x = x + _attention_step(block.attn, block.attn_norm(x), cache, i)
        x = x + block.mlp(block.mlp_norm(x))
    cache.length += t
    return model.lm_head(model.final_norm(x))


@torch.no_grad()
def generate_cached(model: NawaDecoder, input_ids: torch.Tensor, max_new_tokens: int, temperature: float = 0.0,
                    generator: torch.Generator | None = None) -> torch.Tensor:
    """Same contract and same sampling calls as ``NawaDecoder.generate``, with a KV cache."""
    if max_new_tokens < 0 or temperature < 0:
        raise ValueError("max_new_tokens and temperature must be >= 0")
    was_training = model.training
    model.eval()
    limit = model.cfg.max_seq_len
    out = input_ids
    cache: KVCache | None = None
    for _ in range(max_new_tokens):
        if out.shape[1] <= limit:
            if cache is None:
                cache = KVCache.empty(model.cfg.n_layers)
                logits = forward_cached(model, out, cache)[:, -1, :]
            else:
                logits = forward_cached(model, out[:, -1:], cache)[:, -1, :]
        else:  # the reference crops and restarts positions: recompute exactly as it does
            cache = None
            logits = model(out[:, -limit:]).logits[:, -1, :]
        if temperature == 0:
            nxt = logits.argmax(dim=-1, keepdim=True)
        else:
            probs = torch.softmax(logits.float() / temperature, dim=-1)
            nxt = torch.multinomial(probs, 1, generator=generator)
        out = torch.cat([out, nxt], dim=1)
    model.train(was_training)
    return out


__all__ = ["KVCache", "forward_cached", "generate_cached"]
