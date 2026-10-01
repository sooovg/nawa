"""P3-08 tests: numerical verification, deterministic seeds, checkpoint resume identity.

These tests verify the formal G3 requirements:
- Same seed → identical weights and training trajectory
- Checkpoint resume → identical continuation (within float precision)
- Determinism: two runs with the same config and seed produce identical outputs
- RNG state is fully captured and restored
- Gradient accumulation preserves numerical equivalence
- Optimizer state is fully restored on resume
- Scheduler state is fully restored on resume
- Numerical stability: loss is finite throughout training

CPU-only, synthetic data, no external weights.
"""

from __future__ import annotations

import os
import tempfile

import pytest

if os.environ.get("NAWA_REQUIRE_TORCH") == "1":
    import torch
else:
    torch = pytest.importorskip("torch")

from nawa.model import DecoderConfig, NawaDecoder
from nawa.training.trainer import (
    Trainer,
    TrainerConfig,
    capture_rng,
    restore_rng,
)

TINY = dict(vocab_size=16, d_model=32, n_layers=2, n_heads=4, max_seq_len=16)
TRAIN_STEPS = 30


def make_model(seed: int = 42) -> NawaDecoder:
    torch.manual_seed(seed)
    return NawaDecoder(DecoderConfig(**TINY))


def make_batch_fn(vocab: int = 16, seq_len: int = 12, batch: int = 8, seed: int = 1):
    g = torch.Generator().manual_seed(seed)

    def fn(step: int):
        x = torch.randint(0, vocab, (batch, seq_len), generator=g)
        return x[:, :-1], x[:, 1:]

    return fn


def make_cfg(steps: int = TRAIN_STEPS, seed: int = 42, **kw) -> TrainerConfig:
    defaults = dict(
        max_steps=steps,
        warmup_steps=5,
        log_interval=steps + 1,
        checkpoint_interval=steps + 1,
        eval_interval=steps + 1,
        seed=seed,
    )
    defaults.update(kw)
    return TrainerConfig(**defaults)


# ---- Determinism: same seed → identical trajectory -----------------------------------------------

def test_same_seed_produces_identical_weights():
    """Two models initialised with the same seed must have identical weights."""
    model_a = make_model(seed=42)
    model_b = make_model(seed=42)
    for p_a, p_b in zip(model_a.parameters(), model_b.parameters()):
        torch.testing.assert_close(p_a.data, p_b.data)


def test_different_seed_produces_different_weights():
    model_a = make_model(seed=42)
    model_b = make_model(seed=99)
    diffs = [
        (p_a.data - p_b.data).abs().sum().item()
        for p_a, p_b in zip(model_a.parameters(), model_b.parameters())
    ]
    assert sum(diffs) > 0.0, "different seeds should produce different weights"


def test_same_config_same_seed_identical_training_trajectory():
    """Two training runs with identical config and seed must produce identical loss curves."""
    cfg = make_cfg()

    # Run A
    model_a = make_model(seed=42)
    trainer_a = Trainer(model_a, make_batch_fn(), config=cfg)
    trainer_a.train()

    # Run B (fresh model, same seed)
    model_b = make_model(seed=42)
    trainer_b = Trainer(model_b, make_batch_fn(), config=cfg)
    trainer_b.train()

    # Loss curves must be identical
    assert len(trainer_a.train_history) == len(trainer_b.train_history)
    for i, (a, b) in enumerate(zip(trainer_a.train_history, trainer_b.train_history)):
        assert a.train_loss == b.train_loss, f"step {i}: {a.train_loss} != {b.train_loss}"
        assert a.learning_rate == b.learning_rate, f"step {i}: LR mismatch"
        assert a.grad_norm == b.grad_norm, f"step {i}: grad_norm mismatch"

    # Final weights must be identical
    for p_a, p_b in zip(trainer_a.model.parameters(), trainer_b.model.parameters()):
        torch.testing.assert_close(p_a.data, p_b.data)


def test_same_config_different_seed_different_trajectory():
    """Two runs with different seeds must produce different loss curves."""
    cfg_a = make_cfg(seed=42)
    cfg_b = make_cfg(seed=99)

    model_a = make_model(seed=42)
    trainer_a = Trainer(model_a, make_batch_fn(), config=cfg_a)
    trainer_a.train()

    model_b = make_model(seed=99)
    trainer_b = Trainer(model_b, make_batch_fn(seed=2), config=cfg_b)
    trainer_b.train()

    # At least some steps should differ
    diffs = sum(
        1 for a, b in zip(trainer_a.train_history, trainer_b.train_history)
        if a.train_loss != b.train_loss
    )
    assert diffs > 0, "different seeds should produce different trajectories"


# ---- Checkpoint resume identity ------------------------------------------------------------------

def test_resume_produces_identical_continuation():
    """Training resumed from a checkpoint must produce the same trajectory as
    a continuous run that never stopped."""
    cfg = make_cfg(steps=TRAIN_STEPS)

    # Continuous run: 30 steps
    model_full = make_model(seed=42)
    trainer_full = Trainer(model_full, make_batch_fn(), config=cfg)
    trainer_full.train()

    # Interrupted run: 15 steps, then checkpoint, then resume for 15 more
    model_part = make_model(seed=42)
    trainer_part = Trainer(model_part, make_batch_fn(), config=cfg)

    # We need to train 15 steps, checkpoint, then train 15 more
    # But the batch_fn uses a generator that advances. We need to capture its state.
    # The Trainer's batch_fn is called with step index, so we need a batch_fn
    # whose state is deterministic based on step, not on an advancing generator.

    # Use a step-seeded batch_fn for this test
    def step_seeded_fn(step: int):
        g = torch.Generator().manual_seed(step + 1000)
        x = torch.randint(0, 16, (8, 12), generator=g)
        return x[:, :-1], x[:, 1:]

    # Redo with step-seeded batch_fn
    cfg_step = make_cfg(steps=TRAIN_STEPS)

    model_full2 = make_model(seed=42)
    trainer_full2 = Trainer(model_full2, step_seeded_fn, config=cfg_step)
    trainer_full2.train()

    model_part2 = make_model(seed=42)
    trainer_part2 = Trainer(model_part2, step_seeded_fn, config=cfg_step)
    trainer_part2.train(max_steps=15)

    with tempfile.TemporaryDirectory() as tmpdir:
        ckpt = os.path.join(tmpdir, "resume.pt")
        trainer_part2.save_checkpoint(ckpt)

        # Resume
        model_resume = make_model(seed=42)
        trainer_resume = Trainer(model_resume, step_seeded_fn, config=cfg_step)
        trainer_resume.load_checkpoint(ckpt)
        trainer_resume.train(max_steps=15)

    # Compare: the continuous run and the interrupted+resumed run should match
    full_losses = [s.train_loss for s in trainer_full2.train_history]
    part_losses = [s.train_loss for s in trainer_part2.train_history]
    resume_losses = [s.train_loss for s in trainer_resume.train_history]

    # First 15 steps must be identical (same seed, same data)
    for i in range(15):
        assert full_losses[i] == part_losses[i], f"step {i}: {full_losses[i]} != {part_losses[i]}"

    # Steps 15-29 must be identical between continuous and resumed
    for i in range(15):
        full_idx = 15 + i
        assert full_losses[full_idx] == resume_losses[i], (
            f"step {full_idx}: continuous {full_losses[full_idx]} != resumed {resume_losses[i]}"
        )

    # Final weights must match
    for p_full, p_resume in zip(
        trainer_full2.model.parameters(), trainer_resume.model.parameters()
    ):
        torch.testing.assert_close(p_full.data, p_resume.data)


def test_resume_restores_optimizer_state():
    """The optimizer state (momentum buffers) must be restored on resume."""
    cfg = make_cfg(steps=20)

    def step_seeded_fn(step: int):
        g = torch.Generator().manual_seed(step + 500)
        x = torch.randint(0, 16, (8, 12), generator=g)
        return x[:, :-1], x[:, 1:]

    model_a = make_model(seed=42)
    trainer_a = Trainer(model_a, step_seeded_fn, config=cfg)
    trainer_a.train(max_steps=10)

    with tempfile.TemporaryDirectory() as tmpdir:
        ckpt = os.path.join(tmpdir, "opt.pt")
        trainer_a.save_checkpoint(ckpt)

        model_b = make_model(seed=42)
        trainer_b = Trainer(model_b, step_seeded_fn, config=cfg)
        trainer_b.load_checkpoint(ckpt)

        # Optimizer state should match
        for (k_a, v_a), (k_b, v_b) in zip(
            trainer_a.optimizer.state_dict()["state"].items(),
            trainer_b.optimizer.state_dict()["state"].items(),
        ):
            assert k_a == k_b
            for sk in v_a:
                if isinstance(v_a[sk], torch.Tensor):
                    torch.testing.assert_close(v_a[sk], v_b[sk])
                else:
                    assert v_a[sk] == v_b[sk], f"optimizer state {k_a}.{sk}: {v_a[sk]} != {v_b[sk]}"


def test_resume_restores_scheduler_state():
    """The scheduler state must be restored on resume."""
    cfg = make_cfg(steps=20)

    def step_seeded_fn(step: int):
        g = torch.Generator().manual_seed(step + 500)
        x = torch.randint(0, 16, (8, 12), generator=g)
        return x[:, :-1], x[:, 1:]

    model_a = make_model(seed=42)
    trainer_a = Trainer(model_a, step_seeded_fn, config=cfg)
    trainer_a.train(max_steps=10)

    with tempfile.TemporaryDirectory() as tmpdir:
        ckpt = os.path.join(tmpdir, "sched.pt")
        trainer_a.save_checkpoint(ckpt)

        model_b = make_model(seed=42)
        trainer_b = Trainer(model_b, step_seeded_fn, config=cfg)
        trainer_b.load_checkpoint(ckpt)

        # Scheduler LR should match
        lr_a = trainer_a.scheduler.get_last_lr()[0]
        lr_b = trainer_b.scheduler.get_last_lr()[0]
        assert lr_a == lr_b, f"scheduler LR mismatch: {lr_a} != {lr_b}"


def test_resume_restores_step_count():
    """The step counter must be restored on resume."""
    cfg = make_cfg(steps=20)

    def step_seeded_fn(step: int):
        g = torch.Generator().manual_seed(step + 500)
        x = torch.randint(0, 16, (8, 12), generator=g)
        return x[:, :-1], x[:, 1:]

    model = make_model(seed=42)
    trainer = Trainer(model, step_seeded_fn, config=cfg)
    trainer.train(max_steps=10)

    with tempfile.TemporaryDirectory() as tmpdir:
        ckpt = os.path.join(tmpdir, "step.pt")
        trainer.save_checkpoint(ckpt)

        model2 = make_model(seed=42)
        trainer2 = Trainer(model2, step_seeded_fn, config=cfg)
        assert trainer2.step == 0
        trainer2.load_checkpoint(ckpt)
        assert trainer2.step == 10


def test_resume_restores_rng_state():
    """The RNG state must be restored on resume, ensuring downstream randomness matches."""
    # Capture RNG, advance, restore, verify
    torch.manual_seed(777)
    state = capture_rng()
    a = torch.randn(5)
    _ = torch.randn(200)  # advance
    restore_rng(state)
    b = torch.randn(5)
    torch.testing.assert_close(a, b)


# ---- Numerical stability ------------------------------------------------------------------------

def test_loss_is_finite_throughout_training():
    """Loss must be finite at every step (no NaN, no Inf)."""
    cfg = make_cfg(steps=30)

    model = make_model(seed=42)
    trainer = Trainer(model, make_batch_fn(), config=cfg)
    trainer.train()

    for step in trainer.train_history:
        assert step.train_loss == step.train_loss, "loss is NaN"  # NaN != NaN
        assert abs(step.train_loss) != float("inf"), "loss is Inf"
        assert step.grad_norm == step.grad_norm, "grad_norm is NaN"
        assert abs(step.grad_norm) != float("inf"), "grad_norm is Inf"


def test_grad_norm_is_non_negative():
    """Gradient norm must be non-negative."""
    cfg = make_cfg(steps=10)

    model = make_model(seed=42)
    trainer = Trainer(model, make_batch_fn(), config=cfg)
    trainer.train()

    for step in trainer.train_history:
        assert step.grad_norm >= 0.0, f"grad_norm must be >= 0, got {step.grad_norm}"


def test_learning_rate_is_positive():
    """Learning rate must be positive throughout training."""
    cfg = make_cfg(steps=30, warmup_steps=5)

    model = make_model(seed=42)
    trainer = Trainer(model, make_batch_fn(), config=cfg)
    trainer.train()

    for step in trainer.train_history:
        assert step.learning_rate > 0, f"LR must be > 0, got {step.learning_rate}"


# ---- Gradient accumulation numerical equivalence ------------------------------------------------

def test_gradient_accumulation_numerical_equivalence():
    """Gradient accumulation of K micro-batches of size B should produce
    the same gradient as one batch of size K*B (modulo floating point)."""
    torch.manual_seed(42)
    model_a = make_model(seed=42)
    model_b = make_model(seed=42)

    # Same data: 4 micro-batches of size 2 = 1 batch of size 8
    # We need the same data in both cases
    g = torch.Generator().manual_seed(123)
    micro_batches = []
    for _ in range(4):
        x = torch.randint(0, 16, (2, 12), generator=g)
        micro_batches.append((x[:, :-1], x[:, 1:]))

    # Large batch: concatenate all micro-batches into one batch of size 8
    big_x = torch.cat([mb[0] for mb in micro_batches], dim=0)
    big_y = torch.cat([mb[1] for mb in micro_batches], dim=0)

    # Train A: one step with large batch.
    # SGD, not AdamW: SGD's update is linear in the gradient, so equal gradients must give equal weights.
    # AdamW's first step is ~lr * g / (|g| + eps), which turns float-summation noise in near-zero gradients
    # into differences up to ~lr; with AdamW this check failed on the CI runner (1 of 2816 elements, 1.8e-6)
    # while passing locally (fixed during P3-01/02, PR #23). The gradient check below is unchanged.
    model_a.train()
    opt_a = torch.optim.SGD(model_a.parameters(), lr=1e-2)
    loss_a = model_a(big_x, targets=big_y).loss
    opt_a.zero_grad(set_to_none=True)
    loss_a.backward()
    opt_a.step()

    # Train B: 4 micro-steps with accumulation (do NOT zero grad between micro-steps)
    model_b.train()
    opt_b = torch.optim.SGD(model_b.parameters(), lr=1e-2)
    opt_b.zero_grad(set_to_none=True)
    for mb_x, mb_y in micro_batches:
        loss_b = model_b(mb_x, targets=mb_y).loss / 4
        loss_b.backward()
    opt_b.step()

    # The gradients should be very close (accumulated = averaged)
    for p_a, p_b in zip(model_a.parameters(), model_b.parameters()):
        if p_a.grad is not None and p_b.grad is not None:
            torch.testing.assert_close(p_a.grad, p_b.grad, rtol=1e-5, atol=1e-6)

    # After the optimizer step, weights should be very close
    for p_a, p_b in zip(model_a.parameters(), model_b.parameters()):
        torch.testing.assert_close(p_a.data, p_b.data, rtol=1e-5, atol=1e-6)


# ---- Checkpoint integrity -----------------------------------------------------------------------

def test_checkpoint_contains_all_required_fields():
    """A checkpoint must contain all fields needed for full reproduction."""
    cfg = make_cfg(steps=5)
    model = make_model(seed=42)
    trainer = Trainer(model, make_batch_fn(), config=cfg)
    trainer.train()

    state = trainer.state_dict()
    required = ["step", "model_state", "optimizer_state", "scheduler_state",
                "config", "model_config", "rng_state", "metrics", "config_hash"]
    for field in required:
        assert field in state.to_dict(), f"checkpoint missing field: {field}"


def test_checkpoint_config_hash_matches_model():
    """The config_hash in the checkpoint must match the model's config_hash."""
    cfg = make_cfg(steps=5)
    model = make_model(seed=42)
    trainer = Trainer(model, make_batch_fn(), config=cfg)
    trainer.train()

    state = trainer.state_dict()
    assert state.config_hash == model.cfg.config_hash()


def test_checkpoint_model_config_is_saved():
    """The model config must be saved in the checkpoint for reproducibility."""
    cfg = make_cfg(steps=5)
    model = make_model(seed=42)
    trainer = Trainer(model, make_batch_fn(), config=cfg)
    trainer.train()

    state = trainer.state_dict()
    assert "vocab_size" in state.model_config
    assert "d_model" in state.model_config
    assert "n_layers" in state.model_config
    assert state.model_config["vocab_size"] == TINY["vocab_size"]
    assert state.model_config["d_model"] == TINY["d_model"]


# ---- Integration: full train → checkpoint → resume → eval ---------------------------------------

def test_full_pipeline_train_checkpoint_resume_eval():
    """Integration test: train, checkpoint, resume, and evaluate."""
    cfg = make_cfg(steps=20, eval_interval=10, eval_steps=2)

    def step_seeded_fn(step: int):
        g = torch.Generator().manual_seed(step + 2000)
        x = torch.randint(0, 16, (8, 12), generator=g)
        return x[:, :-1], x[:, 1:]

    def val_fn():
        g = torch.Generator().manual_seed(9999)
        x = torch.randint(0, 16, (8, 12), generator=g)
        return model(x[:, :-1], targets=x[:, 1:]).loss

    model = make_model(seed=42)
    trainer = Trainer(model, step_seeded_fn, val_fn=val_fn, config=cfg)
    trainer.train(max_steps=10)

    with tempfile.TemporaryDirectory() as tmpdir:
        ckpt = os.path.join(tmpdir, "pipeline.pt")
        trainer.save_checkpoint(ckpt)

        # Resume
        model2 = make_model(seed=42)
        trainer2 = Trainer(model2, step_seeded_fn, val_fn=val_fn, config=cfg)
        trainer2.load_checkpoint(ckpt)
        assert trainer2.step == 10

        # Continue training
        trainer2.train(max_steps=10)
        assert trainer2.step == 20
        assert len(trainer2.train_history) == 10  # only new steps
        assert len(trainer2.eval_history) >= 1  # at least one eval in the resumed portion


# ---- Determinism of model forward pass -----------------------------------------------------------

def test_model_forward_is_deterministic():
    """A model in eval mode must produce identical outputs for identical inputs."""
    model = make_model(seed=42)
    model.eval()
    x = torch.randint(0, 16, (4, 10))
    out_a = model(x).logits
    out_b = model(x).logits
    torch.testing.assert_close(out_a, out_b)


def test_model_backward_is_deterministic():
    """Backward pass must produce identical gradients for identical inputs."""
    model_a = make_model(seed=42)
    model_b = make_model(seed=42)
    x = torch.randint(0, 16, (4, 10))
    targets = x.clone()

    model_a.train()
    loss_a = model_a(x[:, :-1], targets=x[:, 1:]).loss
    loss_a.backward()

    model_b.train()
    loss_b = model_b(x[:, :-1], targets=x[:, 1:]).loss
    loss_b.backward()

    assert loss_a.item() == loss_b.item()
    for p_a, p_b in zip(model_a.parameters(), model_b.parameters()):
        if p_a.grad is not None and p_b.grad is not None:
            torch.testing.assert_close(p_a.grad, p_b.grad)
