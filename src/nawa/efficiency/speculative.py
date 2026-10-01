"""Greedy speculative decoding (ROADMAP P4-05, ADR-0007 D2).

A small draft model proposes ``k`` tokens greedily; the target scores context + proposal in one forward pass and keeps
the longest prefix that equals its own greedy choice, then adds its own next token. The output is therefore, by
construction, the target's greedy output; the test is that it is token-identical to ``NawaDecoder.generate`` with
``temperature=0`` (no tolerance on tokens; ties are resolved by ``argmax`` as in the reference).

Scope: batch 1, greedy only, prompt + new tokens within ``max_seq_len`` of both models (no cropping); anything else
raises. Sampling-based speculative decoding (rejection sampling) is not implemented.
"""

from __future__ import annotations

from dataclasses import dataclass

import torch

from nawa.efficiency.kv_cache import generate_cached
from nawa.model.decoder import NawaDecoder


@dataclass
class SpecStats:
    target_calls: int = 0
    draft_tokens: int = 0
    accepted: int = 0
    generated: int = 0

    @property
    def acceptance_rate(self) -> float:
        return self.accepted / self.draft_tokens if self.draft_tokens else 0.0

    def to_dict(self) -> dict[str, float]:
        return {"target_calls": self.target_calls, "draft_tokens": self.draft_tokens, "accepted": self.accepted,
                "generated": self.generated, "acceptance_rate": round(self.acceptance_rate, 6)}


@torch.no_grad()
def speculative_generate(target: NawaDecoder, draft: NawaDecoder, input_ids: torch.Tensor, max_new_tokens: int,
                         k: int = 4) -> tuple[torch.Tensor, SpecStats]:
    if input_ids.shape[0] != 1:
        raise ValueError("speculative_generate supports batch size 1")
    if k < 1 or max_new_tokens < 0:
        raise ValueError("k must be >= 1 and max_new_tokens >= 0")
    if target.cfg.vocab_size != draft.cfg.vocab_size:
        raise ValueError("target and draft must share the vocabulary")
    total = input_ids.shape[1] + max_new_tokens
    if total > min(target.cfg.max_seq_len, draft.cfg.max_seq_len):
        raise ValueError("prompt + max_new_tokens must fit in max_seq_len of both models (no cropping)")
    modes = target.training, draft.training
    target.eval()
    draft.eval()
    stats, out = SpecStats(), input_ids
    while stats.generated < max_new_tokens:
        n = min(k, max_new_tokens - stats.generated)
        proposal = generate_cached(draft, out, n)[:, out.shape[1]:]                     # (1, n)
        logits = target(torch.cat([out, proposal], dim=1)).logits[0, out.shape[1] - 1:]  # (n + 1, vocab)
        preds = logits.argmax(dim=-1)
        stats.target_calls += 1
        stats.draft_tokens += n
        match = (preds[:n] == proposal[0]).long()
        m = int(match.cumprod(0).sum())
        stats.accepted += m
        new = torch.cat([proposal[0, :m], preds[m:m + 1]])[: max_new_tokens - stats.generated]
        out = torch.cat([out, new[None]], dim=1)
        stats.generated += new.numel()
    target.train(modes[0])
    draft.train(modes[1])
    return out, stats
