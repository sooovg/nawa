"""P3-05 checks: the synthetic source is exact, and the reference decoder learns (fast CI versions).

The full pre-registered run is ``python -m nawa.training.sanity`` (EXP log). These tests keep CI short.
"""

from __future__ import annotations

import math
import os

import pytest

if os.environ.get("NAWA_REQUIRE_TORCH") == "1":
    import torch
else:
    torch = pytest.importorskip("torch")

from nawa.training.sanity import (  # noqa: E402
    ARABIC_ALPHABET, CRITERIA, MarkovSource, count_model_heldout_loss, train_char_lm, train_xor, xor_batch,
)


def test_xor_batch_supervises_only_the_answer() -> None:
    inp, tgt = xor_batch()
    assert inp.shape == (4, 3)
    assert (tgt[:, :-1] == -100).all()
    assert tgt[:, -1].tolist() == [0, 1, 1, 0]


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_xor_is_learned_perfectly(seed: int) -> None:
    assert train_xor(seed)["accuracy"] == CRITERIA["xor_accuracy"]


def test_markov_source_is_deterministic_and_normalised() -> None:
    a, b = MarkovSource.make(8, seed=3), MarkovSource.make(8, seed=3)
    assert torch.equal(a.probs, b.probs)
    torch.testing.assert_close(a.probs.sum(-1), torch.ones(8, 8, dtype=torch.float64))
    assert torch.equal(a.sample(500, seed=1), b.sample(500, seed=1))
    assert not torch.equal(a.probs, MarkovSource.make(8, seed=4).probs)


def test_stationary_distribution_is_a_fixed_point() -> None:
    s = MarkovSource.make(6, seed=5)
    pi = s.stationary_pairs()
    torch.testing.assert_close(torch.einsum("ab,abc->bc", pi, s.probs), pi, rtol=0, atol=1e-10)
    assert math.isclose(float(pi.sum()), 1.0, rel_tol=1e-12)


def test_exact_entropy_rates_match_an_unbiased_sample_estimate() -> None:
    """H2 from the formula equals mean -log p_true(x_t | x_{t-2}, x_{t-1}) on a long sample."""
    s = MarkovSource.make(len(ARABIC_ALPHABET), seed=42)
    rates = s.entropy_rates()
    x = s.sample(100_000, seed=7)
    est = float(-torch.log(s.probs[x[:-2], x[1:-1], x[2:]]).mean())
    assert abs(est - rates["H2"]) < 0.02, (est, rates)
    assert rates["H2"] < rates["H1"] <= rates["H0"] <= math.log(len(ARABIC_ALPHABET)) + 1e-9


def test_count_reference_approaches_h2_with_more_data() -> None:
    s = MarkovSource.make(len(ARABIC_ALPHABET), seed=42)
    val = s.sample(20_000, seed=2)
    small = count_model_heldout_loss(s.sample(50_000, seed=1), val, s.k)
    large = count_model_heldout_loss(s.sample(1_000_000, seed=1), val, s.k)
    assert large < small and large - s.entropy_rates()["H2"] < 0.03


def test_tiny_char_lm_learns_to_use_two_character_context() -> None:
    """Short CI run (not the pre-registered criterion): loss must fall well below H1, i.e. beyond any
    order-1 predictor, which needs attention over the previous two characters."""
    # Thresholds chosen from the measured learning curve of the first (failed) full run, EXP-0007:
    # val loss 3.41 at step 0 and 2.90 at step 500 (batch 32). A broken model stays near H1 (3.31).
    r = train_char_lm(seed=42, steps=600, batch=32, train_chars=200_000, val_chars=10_000, log_every=600)
    assert r["curve"][-1]["val_loss"] < r["curve"][0]["val_loss"] - 0.3, r["curve"]
    assert r["margin_below_H1"] > 0.2, r
