"""P3-05 sanity training: prove the NAWA reference decoder (P3-04) can learn, before any real training.

Two tasks, both on local CPU with data NAWA generates itself (no external data, no licence question):

1. **XOR** as a sequence task: ``a b =`` → ``a xor b``. Must reach 100% accuracy for every seed.
2. **Tiny character LM** on a synthetic Arabic-alphabet source: an order-2 Markov chain with a fixed,
   seeded transition table. Its entropy rates are computed exactly, so the optimum is known in advance:

   - ``H0`` = entropy of the stationary character distribution (best context-free predictor),
   - ``H1`` = conditional entropy given the previous character (best order-1 predictor),
   - ``H2`` = conditional entropy given the previous two characters (the true optimum).

   The model learns if its held-out loss approaches ``H2`` and is clearly below ``H1`` — that shows it uses
   the two-character context through attention, and is not just fitting frequencies.

Acceptance thresholds are fixed in ``CRITERIA`` *before* any run (no tuning to the result).
This module is a minimal loop for P3-05 only; the full trainer (optimizer schedules, checkpoints, resume,
distributed) is P3-06/P3-08.
"""

from __future__ import annotations

import argparse
import json
import math
import platform
import sys
import time
from dataclasses import dataclass

import torch

from nawa import budget
from nawa.model import IGNORE_INDEX, DecoderConfig, NawaDecoder

# Pre-registered acceptance criteria (fixed before the first run).
CRITERIA = {
    "xor_accuracy": 1.0,             # every one of the 4 cases, for every seed
    "lm_gap_to_h2_nats": 0.05,       # held-out loss <= H2 + 0.05
    "lm_margin_below_h1_nats": 0.10,  # held-out loss <= H1 - 0.10 (uses 2-char context)
}

ARABIC_ALPHABET = list("ابتثجحخدذرزسشصضطظعغفقكلمنهوي") + [" "]


# ---- XOR -----------------------------------------------------------------------------------------
XOR_VOCAB = {"0": 0, "1": 1, "=": 2}


def xor_batch() -> tuple[torch.Tensor, torch.Tensor]:
    """All 4 cases. Input ``a b =`` ; the only supervised position is the answer after ``=``."""
    rows, tgts = [], []
    for a in (0, 1):
        for b in (0, 1):
            rows.append([a, b, XOR_VOCAB["="], a ^ b])
    x = torch.tensor(rows)
    inp, tgt = x[:, :-1], x[:, 1:].clone()
    tgt[:, :-1] = IGNORE_INDEX
    return inp, tgt


def train_xor(seed: int, steps: int = 300, lr: float = 3e-3) -> dict:
    torch.manual_seed(seed)
    cfg = DecoderConfig(vocab_size=3, d_model=32, n_layers=2, n_heads=2, max_seq_len=8)
    model = NawaDecoder(cfg).train()
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.0)
    inp, tgt = xor_batch()
    for _ in range(steps):
        loss = model(inp, targets=tgt).loss
        opt.zero_grad(set_to_none=True)
        loss.backward()
        opt.step()
    model.eval()
    with torch.no_grad():
        pred = model(inp).logits[:, -1].argmax(-1)
    acc = (pred == tgt[:, -1]).float().mean().item()
    return {"seed": seed, "steps": steps, "final_loss": round(loss.item(), 6), "accuracy": acc,
            "config_hash": cfg.config_hash()}


# ---- order-2 Markov source -----------------------------------------------------------------------
@dataclass
class MarkovSource:
    """Order-2 Markov chain over ``k`` symbols. ``probs[a, b]`` is the distribution of the next symbol."""

    probs: torch.Tensor  # (k, k, k), float64

    @classmethod
    def make(cls, k: int, seed: int, concentration: float = 0.3) -> "MarkovSource":
        g = torch.Generator().manual_seed(seed)
        gamma = torch.distributions.Gamma(torch.full((k, k, k), concentration, dtype=torch.float64),
                                          torch.ones(k, k, k, dtype=torch.float64))
        # Seeded Dirichlet draw via normalised Gammas (torch distributions use the global RNG, so fork it).
        with torch.random.fork_rng():
            torch.manual_seed(int(torch.randint(0, 2**31 - 1, (1,), generator=g)))
            raw = gamma.sample() + 1e-12
        return cls(raw / raw.sum(-1, keepdim=True))

    @property
    def k(self) -> int:
        return self.probs.shape[0]

    def stationary_pairs(self, iters: int = 5000) -> torch.Tensor:
        """Stationary distribution over (prev2, prev1) pairs by power iteration. (k, k)."""
        pi = torch.full((self.k, self.k), 1.0 / self.k ** 2, dtype=torch.float64)
        for _ in range(iters):
            new = torch.einsum("ab,abc->bc", pi, self.probs)
            if torch.allclose(new, pi, atol=1e-15, rtol=0):
                break
            pi = new
        return new / new.sum()

    def entropy_rates(self) -> dict[str, float]:
        """Exact H0, H1, H2 in nats for the stationary chain."""
        pi = self.stationary_pairs()
        def h(p: torch.Tensor) -> torch.Tensor:
            return -(p * torch.log(p.clamp_min(1e-300))).sum(-1)
        h2 = float((pi * h(self.probs)).sum())
        joint_bc = torch.einsum("ab,abc->bc", pi, self.probs)      # p(prev1=b, next=c)
        p_b = joint_bc.sum(-1, keepdim=True)
        h1 = float((p_b.squeeze(-1) * h(joint_bc / p_b.clamp_min(1e-300))).sum())
        h0 = float(h(joint_bc.sum(0)))
        return {"H0": h0, "H1": h1, "H2": h2}

    def sample(self, n: int, seed: int) -> torch.Tensor:
        """Sample n symbols, starting from the stationary pair distribution (inverse-CDF, seeded)."""
        import bisect
        g = torch.Generator().manual_seed(seed)
        pi = self.stationary_pairs().flatten()
        start = int(torch.multinomial(pi.float(), 1, generator=g))
        cdf = self.probs.cumsum(-1).tolist()
        u = torch.rand(n, generator=g, dtype=torch.float64).tolist()
        a, b = divmod(start, self.k)
        out = [a, b]
        last = self.k - 1
        for i in range(2, n):
            c = min(bisect.bisect_right(cdf[a][b], u[i]), last)
            out.append(c)
            a, b = b, c
        return torch.tensor(out, dtype=torch.long)


def count_model_heldout_loss(train: torch.Tensor, val: torch.Tensor, k: int, alpha: float = 0.5) -> float:
    """Internal reference: add-alpha order-2 count model fitted on the same training stream.

    It is the natural estimator for this source, so its held-out loss shows how close to H2 *any*
    learner can get from this amount of data (the data limit), independent of the decoder.
    """
    counts = torch.zeros(k, k, k, dtype=torch.float64)
    counts.index_put_((train[:-2], train[1:-1], train[2:]), torch.ones(len(train) - 2, dtype=torch.float64),
                      accumulate=True)
    probs = (counts + alpha) / (counts + alpha).sum(-1, keepdim=True)
    return float(-torch.log(probs[val[:-2], val[1:-1], val[2:]]).mean())


def batches(stream: torch.Tensor, seq_len: int, batch: int, g: torch.Generator) -> tuple[torch.Tensor, torch.Tensor]:
    idx = torch.randint(0, len(stream) - seq_len - 1, (batch,), generator=g)
    x = torch.stack([stream[i: i + seq_len + 1] for i in idx.tolist()])
    return x[:, :-1], x[:, 1:]


@torch.no_grad()
def heldout_loss(model: NawaDecoder, stream: torch.Tensor, seq_len: int, skip: int = 2) -> float:
    """Mean loss on non-overlapping windows, skipping the first ``skip`` positions of each window
    (they lack the two-symbol context the optimum H2 assumes)."""
    model.eval()
    n = (len(stream) - 1) // seq_len
    x = stream[: n * seq_len + 1]
    inp = x[:-1].view(n, seq_len)
    tgt = x[1:].view(n, seq_len).clone()
    tgt[:, :skip] = IGNORE_INDEX
    losses = []
    for i in range(0, n, 64):
        losses.append(model(inp[i: i + 64], targets=tgt[i: i + 64]).loss.item() * inp[i: i + 64].shape[0])
    model.train()
    return sum(losses) / n


def train_char_lm(seed: int = 42, steps: int = 3000, seq_len: int = 64, batch: int = 64, lr: float = 3e-3,
                  train_chars: int = 2_000_000, val_chars: int = 50_000, log_every: int = 500) -> dict:
    source = MarkovSource.make(k=len(ARABIC_ALPHABET), seed=seed)
    rates = source.entropy_rates()
    train, val = source.sample(train_chars, seed=seed + 1), source.sample(val_chars, seed=seed + 2)
    count_ref = count_model_heldout_loss(train, val, source.k)
    torch.manual_seed(seed)
    cfg = DecoderConfig(vocab_size=source.k, d_model=64, n_layers=2, n_heads=4, max_seq_len=seq_len)
    model = NawaDecoder(cfg).train()
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.01)
    sched = torch.optim.lr_scheduler.LambdaLR(
        opt, lambda s: min(1.0, (s + 1) / 100) * 0.5 * (1 + math.cos(math.pi * min(s, steps) / steps)))
    g = torch.Generator().manual_seed(seed + 3)
    curve = [{"step": 0, "val_loss": round(heldout_loss(model, val, seq_len), 4)}]
    t0 = time.perf_counter()
    for step in range(1, steps + 1):
        x, y = batches(train, seq_len, batch, g)
        loss = model(x, targets=y).loss
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        sched.step()
        if step % log_every == 0 or step == steps:
            curve.append({"step": step, "train_loss": round(loss.item(), 4),
                          "val_loss": round(heldout_loss(model, val, seq_len), 4)})
    final = curve[-1]["val_loss"]
    return {
        "seed": seed, "steps": steps, "seconds": round(time.perf_counter() - t0, 1),
        "config_hash": cfg.config_hash(), "parameters": model.num_parameters(),
        "entropy_nats": {k: round(v, 4) for k, v in rates.items()},
        "data": {"train_chars": train_chars, "val_chars": val_chars, "batch": batch, "seq_len": seq_len,
                 "train_tokens_seen": steps * batch * seq_len},
        "count_model_reference_val_loss": round(count_ref, 4),
        "final_val_loss": final, "gap_to_H2": round(final - rates["H2"], 4),
        "margin_below_H1": round(rates["H1"] - final, 4), "curve": curve,
        "passed": final <= rates["H2"] + CRITERIA["lm_gap_to_h2_nats"]
        and final <= rates["H1"] - CRITERIA["lm_margin_below_h1_nats"],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="P3-05 sanity training (XOR + tiny character LM), CPU only.")
    ap.add_argument("--xor-seeds", type=int, nargs="+", default=[0, 1, 2])
    ap.add_argument("--lm-seed", type=int, default=42)
    ap.add_argument("--lm-steps", type=int, default=3000)
    ap.add_argument("--lm-train-chars", type=int, default=2_000_000)
    ap.add_argument("--lm-batch", type=int, default=64)
    ap.add_argument("--out", help="write the JSON result here")
    args = ap.parse_args(argv)
    decision = budget.check("cpu_local")
    if not decision.allowed:
        print(f"budget guard refused: {decision.reason}", file=sys.stderr)
        return 2
    torch.set_num_threads(max(1, torch.get_num_threads()))
    xor = [train_xor(s) for s in args.xor_seeds]
    lm = train_char_lm(seed=args.lm_seed, steps=args.lm_steps, train_chars=args.lm_train_chars, batch=args.lm_batch)
    result = {
        "task_id": "P3-05", "criteria": CRITERIA,
        "xor": xor, "xor_passed": all(r["accuracy"] >= CRITERIA["xor_accuracy"] for r in xor),
        "char_lm": lm,
        "software": {"python": platform.python_version(), "torch": torch.__version__},
        "hardware": {"machine": platform.machine(), "threads": torch.get_num_threads(), "gpu": None},
    }
    result["passed"] = result["xor_passed"] and lm["passed"]
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
    print(text)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
