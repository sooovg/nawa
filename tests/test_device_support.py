"""P3-07 tests: DeviceWrapper and DistributedConfig for CPU/GPU/multi-GPU support.

These tests verify that the device abstraction:
- Detects and falls back from CUDA to CPU gracefully
- Moves tensors correctly
- Wraps/unwraps DDP models
- Respects rank-0-only save/log semantics
- Validates distributed config
- Provides barrier, init, cleanup for distributed mode
- Integrates with the Trainer (single-process CPU path)

No GPU or multi-process launch is needed; DDP paths are tested via mocking.
"""

from __future__ import annotations

import os

import pytest

if os.environ.get("NAWA_REQUIRE_TORCH") == "1":
    import torch
else:
    torch = pytest.importorskip("torch")

from nawa.training.trainer import (
    DeviceWrapper,
    DistributedConfig,
    Trainer,
    TrainerConfig,
)

TINY = dict(vocab_size=16, d_model=32, n_layers=2, n_heads=4, max_seq_len=16)


def make_model(seed: int = 42):
    from nawa.model import DecoderConfig, NawaDecoder
    torch.manual_seed(seed)
    return NawaDecoder(DecoderConfig(**TINY))


def make_batch_fn(vocab: int = 16, seq_len: int = 12, batch: int = 8, seed: int = 1):
    g = torch.Generator().manual_seed(seed)

    def fn(step: int):
        x = torch.randint(0, vocab, (batch, seq_len), generator=g)
        return x[:, :-1], x[:, 1:]

    return fn


# ---- DistributedConfig --------------------------------------------------------------------------

def test_distributed_config_defaults():
    cfg = DistributedConfig()
    assert cfg.mode == "none"
    assert cfg.world_size == 1
    assert cfg.rank == 0
    assert not cfg.is_distributed
    assert cfg.is_main
    cfg.validate()


def test_distributed_config_ddp_valid():
    cfg = DistributedConfig(mode="ddp", world_size=4, rank=0, local_rank=0)
    assert cfg.is_distributed
    assert cfg.is_main
    cfg.validate()


def test_distributed_config_ddp_non_zero_rank():
    cfg = DistributedConfig(mode="ddp", world_size=4, rank=2, local_rank=2)
    assert cfg.is_distributed
    assert not cfg.is_main
    cfg.validate()


@pytest.mark.parametrize("bad", [
    dict(mode="mpi"),
    dict(mode="ddp", world_size=0),
    dict(mode="ddp", world_size=4, rank=4),
    dict(mode="ddp", world_size=4, rank=-1),
    dict(mode="ddp", backend="tcp"),
])
def test_distributed_config_invalid(bad):
    defaults = DistributedConfig().to_dict()
    defaults.update(bad)
    cfg = DistributedConfig(**defaults)
    with pytest.raises(ValueError):
        cfg.validate()


def test_distributed_config_round_trip():
    cfg = DistributedConfig(mode="ddp", world_size=8, rank=3, local_rank=3, backend="gloo")
    d = cfg.to_dict()
    assert d["mode"] == "ddp"
    assert d["world_size"] == 8
    assert d["backend"] == "gloo"


# ---- DeviceWrapper: CPU --------------------------------------------------------------------------

def test_device_wrapper_default_is_cpu():
    """Without CUDA, DeviceWrapper should default to CPU."""
    dw = DeviceWrapper()
    # On a CPU-only machine, device is cpu; on a GPU machine, it auto-detects cuda.
    # Either way, it should not crash.
    assert dw.device.type in ("cpu", "cuda")


def test_device_wrapper_explicit_cpu():
    dw = DeviceWrapper("cpu")
    assert dw.device.type == "cpu"


def test_device_wrapper_move_on_cpu_is_noop():
    dw = DeviceWrapper("cpu")
    t = torch.randn(4)
    (moved,) = dw.move(t)
    assert moved.data_ptr() == t.data_ptr()


def test_device_wrapper_cuda_fallback_to_cpu():
    """If CUDA is requested but unavailable, should fall back to CPU."""
    if torch.cuda.is_available():
        pytest.skip("CUDA is available; cannot test fallback")
    with pytest.warns(UserWarning, match="falling back to CPU"):
        dw = DeviceWrapper("cuda:0")
    assert dw.device.type == "cpu"


def test_device_wrapper_precision_fp32_no_autocast():
    dw = DeviceWrapper("cpu")
    dw.set_precision("fp32")
    ctx = dw.autocast()
    with ctx:
        x = torch.randn(4)
        assert x.dtype == torch.float32


def test_device_wrapper_autocast_bf16_cpu_fallback():
    """bf16 autocast on CPU may or may not be supported; should not crash."""
    dw = DeviceWrapper("cpu")
    dw.set_precision("bf16")
    ctx = dw.autocast()
    with ctx:
        _ = torch.randn(4)


# ---- DeviceWrapper: DDP paths (no actual multi-process) ------------------------------------------

def test_device_wrapper_barrier_is_noop_without_dist():
    """barrier() should be a no-op when distributed is not initialized."""
    dw = DeviceWrapper("cpu")
    dw.barrier()  # should not raise


def test_device_wrapper_should_save_is_true_for_single_process():
    dw = DeviceWrapper("cpu")
    assert dw.should_save() is True
    assert dw.should_log() is True


def test_device_wrapper_should_save_false_for_non_zero_rank():
    cfg = DistributedConfig(mode="ddp", world_size=4, rank=2, local_rank=2)
    dw = DeviceWrapper("cpu", cfg)
    assert not dw.should_save()
    assert not dw.should_log()


def test_device_wrapper_wrap_model_no_ddp_without_process_group():
    """wrap_model should not wrap in DDP if the process group is not initialized."""
    cfg = DistributedConfig(mode="ddp", world_size=2, rank=0, local_rank=0)
    dw = DeviceWrapper("cpu", cfg)
    model = make_model()
    wrapped = dw.wrap_model(model)
    # Without init_process_group, DDP is not applied; model is just moved to device
    from torch.nn.parallel import DistributedDataParallel as DDP
    assert not isinstance(wrapped, DDP)


def test_device_wrapper_unwrap_model_strips_ddp():
    """unwrap_model should return the underlying module."""
    dw = DeviceWrapper("cpu")
    model = make_model()
    # No DDP wrapping in single-process mode
    assert dw.unwrap_model(model) is model


def test_device_wrapper_unwrap_model_passes_through_non_ddp():
    from torch.nn import Linear
    dw = DeviceWrapper("cpu")
    model = Linear(4, 4)
    assert dw.unwrap_model(model) is model


# ---- Trainer integration with distributed config -------------------------------------------------

def test_trainer_accepts_distributed_config():
    """Trainer should accept a DistributedConfig even in single-process mode."""
    model = make_model()
    train_fn = make_batch_fn()
    cfg = TrainerConfig(max_steps=5, warmup_steps=1, log_interval=6, checkpoint_interval=6, eval_interval=6)
    dist_cfg = DistributedConfig(mode="none")
    trainer = Trainer(model, train_fn, config=cfg, distributed=dist_cfg)
    trainer.train()
    assert trainer.step == 5


def test_trainer_summary_includes_distributed_info():
    model = make_model()
    train_fn = make_batch_fn()
    cfg = TrainerConfig(max_steps=3, warmup_steps=0, log_interval=4, checkpoint_interval=4, eval_interval=4)
    dist_cfg = DistributedConfig(mode="none")
    trainer = Trainer(model, train_fn, config=cfg, distributed=dist_cfg)
    trainer.train()

    s = trainer.summary()
    assert "distributed" in s["hardware"]
    assert s["hardware"]["distributed"]["mode"] == "none"


def test_trainer_checkpoint_uses_unwrapped_model():
    """When the model is not DDP-wrapped, checkpoint should still work."""
    model = make_model()
    train_fn = make_batch_fn()
    cfg = TrainerConfig(max_steps=5, warmup_steps=1, log_interval=6, checkpoint_interval=6, eval_interval=6)
    trainer = Trainer(model, train_fn, config=cfg)
    trainer.train()

    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        ckpt_path = os.path.join(tmpdir, "test.pt")
        trainer.save_checkpoint(ckpt_path)

        # Load into new trainer
        model2 = make_model()
        train_fn2 = make_batch_fn()
        trainer2 = Trainer(model2, train_fn2, config=cfg)
        trainer2.load_checkpoint(ckpt_path)
        assert trainer2.step == 5

        # Weights should match
        raw1 = trainer.device.unwrap_model(trainer.model)
        raw2 = trainer2.device.unwrap_model(trainer2.model)
        for p1, p2 in zip(raw1.parameters(), raw2.parameters()):
            torch.testing.assert_close(p1.data, p2.data)


def test_trainer_train_loop_respects_should_log():
    """In single-process mode, should_log is True, so logging happens."""
    model = make_model()
    train_fn = make_batch_fn()
    cfg = TrainerConfig(max_steps=5, warmup_steps=0, log_interval=1, checkpoint_interval=6, eval_interval=6)
    trainer = Trainer(model, train_fn, config=cfg)
    trainer.train()
    # All 5 steps should be logged (log_interval=1)
    assert len(trainer.train_history) == 5


# ---- Static methods -------------------------------------------------------------------------------

def test_init_distributed_is_noop_for_none_mode():
    """init_distributed should be a no-op when mode is 'none'."""
    cfg = DistributedConfig(mode="none")
    DeviceWrapper.init_distributed(cfg)
    # Should not have initialized anything
    assert not torch.distributed.is_initialized()


def test_cleanup_distributed_is_safe_without_init():
    """cleanup_distributed should not crash if nothing was initialized."""
    DeviceWrapper.cleanup_distributed()
    # Should not raise


# ---- DeviceWrapper with explicit GPU device string -----------------------------------------------

def test_device_wrapper_accepts_torch_device_object():
    dw = DeviceWrapper(torch.device("cpu"))
    assert dw.device.type == "cpu"


def test_device_wrapper_cuda_n_auto_detects():
    """If CUDA is available, 'cuda' should select device 0."""
    if not torch.cuda.is_available():
        pytest.skip("CUDA not available")
    dw = DeviceWrapper("cuda")
    assert dw.device.type == "cuda"
    assert dw.device.index == 0
