"""NAWA trainer (ROADMAP P3-06): optimizer, scheduler, checkpoint/resume, metrics, precision, gradient accumulation.

This is the full trainer that ``nawa.training.sanity`` (P3-05) was a minimal loop for. It is designed
for Track S (from scratch), works on CPU by default, and integrates with the budget guard (P0-07a).

Design goals (AGENTS.md §8):
- Every run is reproducible: the checkpoint stores model, optimizer, scheduler, RNG, step, and config hash.
- Resume produces an identical trajectory within float precision (P3-08 verifies this formally).
- Gradient accumulation lets the effective batch size exceed the physical batch size.
- Mixed precision via ``torch.autocast`` (fp32 default; fp16/bf16 where the device supports it).
- The device wrapper is a thin abstraction: single-CPU now, single-GPU and multi-GPU in P3-07.
- No external weights are loaded; the trainer works with any ``nn.Module`` that returns a loss.
"""

from __future__ import annotations

import json
import math
import os
import platform
import random
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol

import torch
from torch import nn
from torch.optim import Optimizer
from torch.optim.lr_scheduler import LambdaLR

from nawa import budget
from nawa.model import DecoderConfig, NawaDecoder

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

class BatchProvider(Protocol):
    """A callable that returns ``(input_ids, targets)`` for one micro-batch."""
    def __call__(self, step: int) -> tuple[torch.Tensor, torch.Tensor]: ...


@dataclass
class TrainStep:
    """One logged training step."""
    step: int
    train_loss: float
    learning_rate: float
    grad_norm: float
    tokens_seen: int
    elapsed_s: float


@dataclass
class EvalResult:
    """One evaluation point."""
    step: int
    val_loss: float
    elapsed_s: float


@dataclass(frozen=True)
class TrainerConfig:
    """All hyper-parameters needed to reproduce a training run.

    Stored in every checkpoint so P3-08 can verify that resume matches.
    """
    # Optimizer
    optimizer: str = "adamw"               # "adamw" or "sgd"
    learning_rate: float = 3e-3
    weight_decay: float = 0.01
    betas: tuple[float, float] = (0.9, 0.999)
    eps: float = 1e-8
    momentum: float = 0.9                  # for SGD

    # Scheduler
    warmup_steps: int = 100
    lr_schedule: str = "cosine"            # "cosine", "linear", "constant"
    min_lr_ratio: float = 0.1              # cosine floor as fraction of peak LR

    # Training
    max_steps: int = 1000
    gradient_accumulation_steps: int = 1
    max_grad_norm: float = 1.0

    # Precision
    precision: str = "fp32"               # "fp32", "fp16", "bf16"

    # Checkpointing
    checkpoint_interval: int = 500
    checkpoint_dir: str = "checkpoints"

    # Evaluation
    eval_interval: int = 100
    eval_steps: int = 10                    # micro-batches per eval

    # Logging
    log_interval: int = 10

    # Reproducibility
    seed: int = 42

    # Budget
    work_kind: str = "cpu_local"

    def validate(self) -> None:
        if self.optimizer not in ("adamw", "sgd"):
            raise ValueError(f"optimizer must be 'adamw' or 'sgd', got {self.optimizer!r}")
        if self.lr_schedule not in ("cosine", "linear", "constant"):
            raise ValueError(f"lr_schedule must be 'cosine', 'linear', or 'constant', got {self.lr_schedule!r}")
        if self.precision not in ("fp32", "fp16", "bf16"):
            raise ValueError(f"precision must be 'fp32', 'fp16', or 'bf16', got {self.precision!r}")
        if self.learning_rate <= 0:
            raise ValueError(f"learning_rate must be > 0, got {self.learning_rate}")
        if self.max_steps <= 0:
            raise ValueError(f"max_steps must be > 0, got {self.max_steps}")
        if self.gradient_accumulation_steps < 1:
            raise ValueError(f"gradient_accumulation_steps must be >= 1, got {self.gradient_accumulation_steps}")
        if self.warmup_steps < 0:
            raise ValueError(f"warmup_steps must be >= 0, got {self.warmup_steps}")
        if not 0.0 <= self.min_lr_ratio <= 1.0:
            raise ValueError(f"min_lr_ratio must be in [0, 1], got {self.min_lr_ratio}")
        if self.work_kind not in budget.WORK_KINDS:
            raise ValueError(f"work_kind must be one of {sorted(budget.WORK_KINDS)}, got {self.work_kind!r}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TrainerConfig":
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[arg-type]
        # betas comes back as a list from JSON
        d = dict(data)
        if "betas" in d and isinstance(d["betas"], list):
            d["betas"] = tuple(d["betas"])
        unknown = set(d) - known
        if unknown:
            raise ValueError(f"unknown TrainerConfig keys: {sorted(unknown)}")
        return cls(**d)


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------

def make_scheduler(opt: Optimizer, cfg: TrainerConfig) -> LambdaLR:
    """Build the LR scheduler described by ``cfg``.

    cosine: linear warmup to ``learning_rate``, then cosine decay to
            ``min_lr_ratio * learning_rate`` at ``max_steps``.
    linear: linear warmup then linear decay to ``min_lr_ratio * learning_rate``.
    constant: linear warmup then constant at ``learning_rate``.
    """
    peak = cfg.learning_rate
    floor = cfg.min_lr_ratio * peak
    warmup = max(1, cfg.warmup_steps)
    total = max(1, cfg.max_steps)

    def lr_lambda(step: int) -> float:
        if step < warmup:
            return (step + 1) / warmup
        progress = min(1.0, (step - warmup) / max(1, total - warmup))
        if cfg.lr_schedule == "cosine":
            cos = 0.5 * (1.0 + math.cos(math.pi * progress))
            return (floor + (peak - floor) * cos) / peak
        elif cfg.lr_schedule == "linear":
            return (floor + (peak - floor) * (1.0 - progress)) / peak
        else:  # constant
            return 1.0

    return LambdaLR(opt, lr_lambda)


# ---------------------------------------------------------------------------
# Checkpoint
# ---------------------------------------------------------------------------

@dataclass
class CheckpointState:
    """Everything needed to resume training identically."""
    step: int
    model_state: dict[str, Any]
    optimizer_state: dict[str, Any]
    scheduler_state: dict[str, Any]
    config: dict[str, Any]
    model_config: dict[str, Any]
    rng_state: dict[str, Any]
    metrics: dict[str, Any]
    config_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "step": self.step,
            "model_state": self.model_state,
            "optimizer_state": self.optimizer_state,
            "scheduler_state": self.scheduler_state,
            "config": self.config,
            "model_config": self.model_config,
            "rng_state": self.rng_state,
            "metrics": self.metrics,
            "config_hash": self.config_hash,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CheckpointState":
        return cls(**data)


def save_checkpoint(path: str | Path, state: CheckpointState) -> None:
    """Save a checkpoint to ``path`` (a .pt file)."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    torch.save(state.to_dict(), str(p))


def load_checkpoint(path: str | Path) -> CheckpointState:
    """Load a checkpoint from ``path``."""
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"checkpoint not found: {p}")
    data = torch.load(str(p), map_location="cpu", weights_only=False)
    return CheckpointState.from_dict(data)


def capture_rng() -> dict[str, Any]:
    """Capture all RNG states for reproducibility.

    torch RNG state is a ByteTensor; we store it as a list of ints so it survives
    JSON serialisation inside a checkpoint. ``restore_rng`` rebuilds the ByteTensor.
    """
    rng = torch.get_rng_state()
    return {
        "python": random.getstate(),
        "torch": rng.tolist() if rng.numel() > 0 else [],
    }


def restore_rng(state: dict[str, Any]) -> None:
    """Restore all RNG states."""
    if "python" in state:
        random.setstate(state["python"])
    if "torch" in state and state["torch"]:
        # torch.set_rng_state requires a ByteTensor (uint8)
        torch.set_rng_state(torch.tensor(state["torch"], dtype=torch.uint8))


# ---------------------------------------------------------------------------
# Device wrapper (P3-06: single device; P3-07 extends to multi-GPU)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DistributedConfig:
    """Distributed training configuration (ROADMAP P3-07).

    - ``"none"``: single process (CPU or one GPU).
    - ``"ddp"``: DistributedDataParallel across ``world_size`` processes.

    DDP requires ``torch.distributed`` and a process group; the trainer handles
    the boilerplate but the caller is responsible for launching processes
    (e.g. ``torchrun`` or ``mp.spawn``).
    """
    mode: str = "none"          # "none" or "ddp"
    world_size: int = 1
    rank: int = 0
    local_rank: int = 0
    backend: str = "nccl"      # "nccl" (GPU) or "gloo" (CPU)

    def validate(self) -> None:
        if self.mode not in ("none", "ddp"):
            raise ValueError(f"distributed mode must be 'none' or 'ddp', got {self.mode!r}")
        if self.mode == "ddp":
            if self.world_size < 1:
                raise ValueError(f"world_size must be >= 1, got {self.world_size}")
            if not 0 <= self.rank < self.world_size:
                raise ValueError(f"rank must be in [0, {self.world_size}), got {self.rank}")
            if self.backend not in ("nccl", "gloo"):
                raise ValueError(f"backend must be 'nccl' or 'gloo', got {self.backend!r}")

    @property
    def is_distributed(self) -> bool:
        return self.mode == "ddp"

    @property
    def is_main(self) -> bool:
        """True on the rank-0 process (the one that logs, saves checkpoints, evaluates)."""
        return self.rank == 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class DeviceWrapper:
    """Device abstraction (ROADMAP P3-06 + P3-07).

    - Single CPU (P3-06).
    - Single GPU: auto-detect or explicit ``device="cuda:N"``.
    - Multi-GPU via DDP: wrap the model with ``DistributedDataParallel`` and
      set the device to ``cuda:local_rank``.

    The wrapper is intentionally thin: it moves tensors, manages autocast,
    and provides hooks for distributed barriers. It does NOT hide the fact
    that multi-GPU requires a process group — the caller must initialise and
    tear down ``torch.distributed`` (the Trainer does this in ``train()``).
    """

    def __init__(
        self,
        device: str | torch.device | None = None,
        distributed: DistributedConfig | None = None,
    ) -> None:
        self.distributed = distributed or DistributedConfig()
        self.distributed.validate()

        if device is None:
            if self.distributed.is_distributed:
                device = f"cuda:{self.distributed.local_rank}"
            elif torch.cuda.is_available():
                device = "cuda"
            else:
                device = "cpu"

        self.device = torch.device(device)
        self._precision: str = "fp32"

        # If CUDA is requested but unavailable, fall back to CPU with a warning
        if self.device.type == "cuda" and not torch.cuda.is_available():
            import warnings
            warnings.warn("CUDA requested but not available; falling back to CPU.")
            self.device = torch.device("cpu")

        # Set the CUDA device for this process
        if self.device.type == "cuda" and torch.cuda.is_available():
            torch.cuda.set_device(self.device)

    def move(self, *tensors: torch.Tensor) -> tuple[torch.Tensor, ...]:
        """Move tensors to the configured device."""
        if self.device.type == "cpu":
            return tensors
        return tuple(t.to(self.device) for t in tensors)

    def autocast(self):
        """Return an autocast context manager for the configured precision."""
        dtype_map = {"fp32": torch.float32, "fp16": torch.float16, "bf16": torch.bfloat16}
        dtype = dtype_map.get(self._precision, torch.float32)

        if dtype == torch.float32:
            from contextlib import nullcontext
            return nullcontext()

        # fp16/bf16 autocast — may not be supported on CPU
        try:
            return torch.autocast(device_type=self.device.type, dtype=dtype)
        except (RuntimeError, ValueError):
            from contextlib import nullcontext
            return nullcontext()

    def set_precision(self, precision: str) -> None:
        self._precision = precision

    def barrier(self) -> None:
        """Synchronise all processes in distributed mode. No-op for single process."""
        if self.distributed.is_distributed and torch.distributed.is_initialized():
            torch.distributed.barrier()

    def wrap_model(self, model: nn.Module) -> nn.Module:
        """Wrap the model for distributed training if needed.

        Returns the model (possibly wrapped in DDP) on the correct device.
        """
        model = model.to(self.device)
        if self.distributed.is_distributed and torch.distributed.is_initialized():
            from torch.nn.parallel import DistributedDataParallel as DDP
            # device_ids=[] for CPU (gloo), [local_rank] for CUDA (nccl)
            device_ids = [self.distributed.local_rank] if self.device.type == "cuda" else []
            model = DDP(model, device_ids=device_ids or None)
        return model

    def unwrap_model(self, model: nn.Module) -> nn.Module:
        """Strip DDP wrapper to access the underlying model."""
        from torch.nn.parallel import DistributedDataParallel as DDP
        if isinstance(model, DDP):
            return model.module
        return model

    def should_save(self) -> bool:
        """Only rank 0 should save checkpoints and log."""
        return self.distributed.is_main

    def should_log(self) -> bool:
        """Only rank 0 should print logs."""
        return self.distributed.is_main

    @staticmethod
    def init_distributed(cfg: DistributedConfig) -> None:
        """Initialise the process group for DDP. Call once per process."""
        if not cfg.is_distributed:
            return
        if torch.distributed.is_initialized():
            return
        import os
        # torchrun sets these env vars
        if not all(k in os.environ for k in ("RANK", "WORLD_SIZE")):
            # Manual init via env vars
            os.environ.setdefault("RANK", str(cfg.rank))
            os.environ.setdefault("WORLD_SIZE", str(cfg.world_size))
            os.environ.setdefault("MASTER_ADDR", "127.0.0.1")
            os.environ.setdefault("MASTER_PORT", "29500")
        torch.distributed.init_process_group(
            backend=cfg.backend,
            rank=cfg.rank,
            world_size=cfg.world_size,
        )

    @staticmethod
    def cleanup_distributed() -> None:
        """Destroy the process group. Call once at the end."""
        if torch.distributed.is_initialized():
            torch.distributed.destroy_process_group()


# ---------------------------------------------------------------------------
# Trainer
# ---------------------------------------------------------------------------

class Trainer:
    """Full training loop for NAWA models.

    Integrates: optimizer, LR scheduler, gradient accumulation, mixed precision,
    checkpoint save/resume, metrics tracking, and budget guard.

    The trainer is generic: it works with any ``nn.Module`` whose ``forward``
    accepts ``(input_ids, targets=...)`` and returns an object with a ``.loss``
    attribute (like ``NawaDecoder``).
    """

    def __init__(
        self,
        model: nn.Module,
        train_fn: Callable[[int], tuple[torch.Tensor, torch.Tensor]],
        val_fn: Callable[[], torch.Tensor] | None = None,
        config: TrainerConfig | None = None,
        device: str | torch.device | None = None,
        distributed: DistributedConfig | None = None,
    ) -> None:
        self.config = config or TrainerConfig()
        self.config.validate()

        self.model = model
        self.train_fn = train_fn
        self.val_fn = val_fn

        # Initialise distributed if requested
        if distributed and distributed.is_distributed:
            DeviceWrapper.init_distributed(distributed)

        self.device = DeviceWrapper(device, distributed)
        self.device.set_precision(self.config.precision)

        # Wrap model for distributed training and move to device
        self.model = self.device.wrap_model(self.model)

        # Seed everything
        torch.manual_seed(self.config.seed)
        random.seed(self.config.seed)

        # Build optimizer
        self.optimizer = self._make_optimizer()

        # Build scheduler
        self.scheduler = make_scheduler(self.optimizer, self.config)

        # State
        self.step = 0
        self.tokens_seen = 0
        self.train_history: list[TrainStep] = []
        self.eval_history: list[EvalResult] = []
        self._start_time: float | None = None

        # Check for resume
        self._resumed = False

    def _make_optimizer(self) -> Optimizer:
        params = [p for p in self.model.parameters() if p.requires_grad]
        if self.config.optimizer == "adamw":
            return torch.optim.AdamW(
                params,
                lr=self.config.learning_rate,
                weight_decay=self.config.weight_decay,
                betas=self.config.betas,
                eps=self.config.eps,
            )
        elif self.config.optimizer == "sgd":
            return torch.optim.SGD(
                params,
                lr=self.config.learning_rate,
                momentum=self.config.momentum,
                weight_decay=self.config.weight_decay,
            )
        raise ValueError(f"unknown optimizer: {self.config.optimizer}")

    # ---- checkpoint --------------------------------------------------------

    def state_dict(self) -> CheckpointState:
        """Capture the full training state for checkpointing."""
        # Use the unwrapped model for state_dict
        raw_model = self.device.unwrap_model(self.model)
        model_cfg = {}
        if hasattr(raw_model, "cfg") and isinstance(raw_model.cfg, DecoderConfig):
            model_cfg = raw_model.cfg.to_dict()

        config_hash = ""
        if hasattr(raw_model, "cfg") and isinstance(raw_model.cfg, DecoderConfig):
            config_hash = raw_model.cfg.config_hash()

        return CheckpointState(
            step=self.step,
            model_state=raw_model.state_dict(),
            optimizer_state=self.optimizer.state_dict(),
            scheduler_state=self.scheduler.state_dict(),
            config=self.config.to_dict(),
            model_config=model_cfg,
            rng_state=capture_rng(),
            metrics=self.metrics(),
            config_hash=config_hash,
        )

    def save_checkpoint(self, path: str | Path | None = None) -> Path:
        """Save a checkpoint. If ``path`` is None, uses ``checkpoint_dir/step_{N}.pt``."""
        if path is None:
            path = Path(self.config.checkpoint_dir) / f"step_{self.step}.pt"
        path = Path(path)
        save_checkpoint(path, self.state_dict())
        return path

    def load_checkpoint(self, path: str | Path) -> int:
        """Load a checkpoint and restore all state. Returns the step number."""
        ckpt = load_checkpoint(path)

        # Verify config matches
        saved_cfg = TrainerConfig.from_dict(ckpt.config)
        if saved_cfg.to_dict() != self.config.to_dict():
            raise ValueError(
                "checkpoint config does not match current config; "
                f"checkpoint: {saved_cfg}, current: {self.config}"
            )

        raw_model = self.device.unwrap_model(self.model)
        raw_model.load_state_dict(ckpt.model_state)
        self.optimizer.load_state_dict(ckpt.optimizer_state)
        self.scheduler.load_state_dict(ckpt.scheduler_state)
        self.step = ckpt.step
        self.tokens_seen = ckpt.metrics.get("tokens_seen", 0)
        restore_rng(ckpt.rng_state)
        self._resumed = True
        return self.step

    # ---- metrics ----------------------------------------------------------

    def metrics(self) -> dict[str, Any]:
        """Current training metrics."""
        last_train = self.train_history[-1] if self.train_history else None
        last_eval = self.eval_history[-1] if self.eval_history else None
        return {
            "step": self.step,
            "tokens_seen": self.tokens_seen,
            "train_loss": last_train.train_loss if last_train else None,
            "val_loss": last_eval.val_loss if last_eval else None,
            "learning_rate": last_train.learning_rate if last_train else self.config.learning_rate,
            "elapsed_s": (last_train.elapsed_s if last_train else 0.0),
            "resumed": self._resumed,
        }

    # ---- training loop ----------------------------------------------------

    def train(self, max_steps: int | None = None) -> dict[str, Any]:
        """Run the training loop.

        Args:
            max_steps: Override ``config.max_steps`` if provided.

        Returns:
            Final metrics dict.
        """
        # Budget guard
        decision = budget.check(self.config.work_kind)
        if not decision.allowed:
            raise RuntimeError(f"budget guard refused: {decision.reason}")

        steps = max_steps or self.config.max_steps
        self._start_time = time.perf_counter()

        self.model.train()

        accum = self.config.gradient_accumulation_steps
        total_micro = steps * accum

        for micro_step in range(total_micro):
            global_step = micro_step // accum

            # Get batch
            inp, tgt = self.train_fn(self.step)

            # Move to device
            inp, tgt = self.device.move(inp, tgt)

            # Forward with autocast
            with self.device.autocast():
                out = self.model(inp, targets=tgt)
                loss = out.loss / accum

            # Backward
            loss.backward()

            # Optimizer step every `accum` micro-steps
            if (micro_step + 1) % accum == 0:
                # Gradient clipping
                grad_norm = torch.nn.utils.clip_grad_norm_(
                    self.model.parameters(), self.config.max_grad_norm
                )

                # Optimizer + scheduler step
                self.optimizer.step()
                self.scheduler.step()
                self.optimizer.zero_grad(set_to_none=True)

                # Track tokens
                batch_tokens = inp.numel()
                self.tokens_seen += batch_tokens * accum

                # Record step
                lr = self.scheduler.get_last_lr()[0]
                elapsed = time.perf_counter() - (self._start_time or 0)
                self.train_history.append(TrainStep(
                    step=self.step,
                    train_loss=loss.item() * accum,
                    learning_rate=lr,
                    grad_norm=float(grad_norm),
                    tokens_seen=self.tokens_seen,
                    elapsed_s=round(elapsed, 3),
                ))

                # Evaluation
                if self.val_fn and (self.step + 1) % self.config.eval_interval == 0:
                    self.device.barrier()
                    if self.device.should_save():
                        val_loss = self._evaluate()
                        self.eval_history.append(EvalResult(
                            step=self.step,
                            val_loss=val_loss,
                            elapsed_s=round(elapsed, 3),
                        ))

                # Checkpoint (rank 0 only)
                if (self.step + 1) % self.config.checkpoint_interval == 0:
                    if self.device.should_save():
                        self.save_checkpoint()
                    self.device.barrier()

                self.step += 1

                # Logging (rank 0 only)
                if self.step % self.config.log_interval == 0 and self.device.should_log():
                    import sys as _sys
                    last = self.train_history[-1]
                    print(
                        f"step {last.step:>5d} | loss {last.train_loss:.4f} | "
                        f"lr {last.learning_rate:.2e} | grad {last.grad_norm:.3f} | "
                        f"tokens {last.tokens_seen}",
                        file=_sys.stderr,
                    )

        return self.metrics()

    def _evaluate(self) -> float:
        """Run evaluation and return mean validation loss."""
        if self.val_fn is None:
            return float("nan")
        self.model.eval()
        total_loss = 0.0
        count = 0
        with torch.no_grad():
            for _ in range(self.config.eval_steps):
                loss = self.val_fn()
                if isinstance(loss, torch.Tensor):
                    total_loss += loss.item()
                else:
                    total_loss += float(loss)
                count += 1
        self.model.train()
        return total_loss / max(1, count)

    # ---- summary ----------------------------------------------------------

    def summary(self) -> dict[str, Any]:
        """Full training summary for experiment logging."""
        return {
            "config": self.config.to_dict(),
            "model_config": (
                self.model.cfg.to_dict()
                if hasattr(self.model, "cfg") and isinstance(self.model.cfg, DecoderConfig)
                else {}
            ),
            "config_hash": (
                self.model.cfg.config_hash()
                if hasattr(self.model, "cfg") and isinstance(self.model.cfg, DecoderConfig)
                else ""
            ),
            "parameters": sum(
                p.numel() for p in self.model.parameters() if p.requires_grad
            ),
            "metrics": self.metrics(),
            "train_curve": [
                {"step": s.step, "loss": s.train_loss, "lr": s.learning_rate, "grad_norm": s.grad_norm}
                for s in self.train_history
            ],
            "eval_curve": [
                {"step": e.step, "val_loss": e.val_loss}
                for e in self.eval_history
            ],
            "hardware": {
                "machine": platform.machine(),
                "device": str(self.device.device),
                "threads": torch.get_num_threads(),
                "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
                "distributed": self.device.distributed.to_dict(),
            },
            "software": {
                "python": platform.python_version(),
                "torch": torch.__version__,
            },
        }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    """Smoke test: train the reference decoder on a tiny synthetic task."""
    import argparse
    import json

    ap = argparse.ArgumentParser(description="P3-06 trainer smoke test (tiny synthetic task, CPU).")
    ap.add_argument("--steps", type=int, default=200, help="training steps")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--precision", default="fp32", choices=["fp32", "fp16", "bf16"])
    ap.add_argument("--accum", type=int, default=1, help="gradient accumulation steps")
    ap.add_argument("--warmup", type=int, default=20)
    ap.add_argument("--schedule", default="cosine", choices=["cosine", "linear", "constant"])
    ap.add_argument("--lr", type=float, default=3e-3)
    ap.add_argument("--checkpoint-dir", default="checkpoints")
    ap.add_argument("--out", help="write the JSON summary here")
    args = ap.parse_args(argv)

    cfg = TrainerConfig(
        max_steps=args.steps,
        seed=args.seed,
        precision=args.precision,
        gradient_accumulation_steps=args.accum,
        warmup_steps=args.warmup,
        lr_schedule=args.schedule,
        learning_rate=args.lr,
        checkpoint_dir=args.checkpoint_dir,
        log_interval=max(1, args.steps // 10),
        checkpoint_interval=args.steps + 1,  # don't auto-save in smoke test
        eval_interval=args.steps + 1,       # don't auto-eval
    )

    # Tiny model + synthetic XOR-like task
    torch.manual_seed(args.seed)
    model_cfg = DecoderConfig(vocab_size=16, d_model=32, n_layers=2, n_heads=4, max_seq_len=16)
    model = NawaDecoder(model_cfg)

    # Synthetic batch provider: random sequences, predict next token
    g = torch.Generator().manual_seed(args.seed + 1)

    def train_fn(step: int) -> tuple[torch.Tensor, torch.Tensor]:
        x = torch.randint(0, model_cfg.vocab_size, (8, 12), generator=g)
        return x[:, :-1], x[:, 1:]

    trainer = Trainer(model, train_fn, config=cfg)
    trainer.train()

    result = {
        "task_id": "P3-06",
        "config": cfg.to_dict(),
        "model_config": model_cfg.to_dict(),
        "config_hash": model_cfg.config_hash(),
        "summary": trainer.summary(),
    }

    text = json.dumps(result, ensure_ascii=False, indent=2, default=str)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
