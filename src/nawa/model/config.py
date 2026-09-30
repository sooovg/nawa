"""Configuration for the NAWA reference decoder (ROADMAP P3-04).

Every architectural choice is a named, validated field, so P4 ablations can change one
choice at a time and every run records a stable ``config_hash`` (AGENTS.md §8).
The defaults are a *reference* setting, not a claim that they are best: P4 decides by measurement.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any

NORMS = ("rmsnorm", "layernorm")
MLPS = ("swiglu", "gelu")
POSITIONALS = ("rope", "learned", "none")


class ModelConfigError(ValueError):
    """Raised when a decoder configuration is invalid."""


@dataclass(frozen=True)
class DecoderConfig:
    vocab_size: int
    d_model: int = 256
    n_layers: int = 4
    n_heads: int = 4
    n_kv_heads: int | None = None      # None = n_heads (plain multi-head); fewer = grouped-query attention
    d_ff: int | None = None            # None = derived from `mlp` (see resolved_d_ff)
    max_seq_len: int = 512
    norm: str = "rmsnorm"
    norm_eps: float = 1e-5
    mlp: str = "swiglu"
    positional: str = "rope"
    rope_theta: float = 10000.0
    dropout: float = 0.0
    bias: bool = False
    tie_embeddings: bool = True
    init_std: float = 0.02

    def __post_init__(self) -> None:
        self.validate()

    # ---- validation -------------------------------------------------------------------------
    def validate(self) -> None:
        def positive(name: str) -> None:
            v = getattr(self, name)
            if not isinstance(v, int) or isinstance(v, bool) or v <= 0:
                raise ModelConfigError(f"{name} must be a positive int, got {v!r}")

        for name in ("vocab_size", "d_model", "n_layers", "n_heads", "max_seq_len"):
            positive(name)
        if self.d_model % self.n_heads:
            raise ModelConfigError(f"d_model ({self.d_model}) must be divisible by n_heads ({self.n_heads})")
        kv = self.kv_heads
        if not isinstance(kv, int) or kv <= 0 or self.n_heads % kv:
            raise ModelConfigError(f"n_kv_heads ({self.n_kv_heads}) must be a positive divisor of n_heads ({self.n_heads})")
        if self.d_ff is not None:
            positive("d_ff")
        if self.norm not in NORMS:
            raise ModelConfigError(f"norm must be one of {NORMS}, got {self.norm!r}")
        if self.mlp not in MLPS:
            raise ModelConfigError(f"mlp must be one of {MLPS}, got {self.mlp!r}")
        if self.positional not in POSITIONALS:
            raise ModelConfigError(f"positional must be one of {POSITIONALS}, got {self.positional!r}")
        if self.positional == "rope" and self.head_dim % 2:
            raise ModelConfigError(f"rope needs an even head_dim, got {self.head_dim}")
        if not 0.0 <= self.dropout < 1.0:
            raise ModelConfigError(f"dropout must be in [0, 1), got {self.dropout}")
        if self.norm_eps <= 0 or self.init_std <= 0 or self.rope_theta <= 0:
            raise ModelConfigError("norm_eps, init_std and rope_theta must be > 0")

    # ---- derived values ---------------------------------------------------------------------
    @property
    def head_dim(self) -> int:
        return self.d_model // self.n_heads

    @property
    def kv_heads(self) -> int:
        return self.n_heads if self.n_kv_heads is None else self.n_kv_heads

    @property
    def resolved_d_ff(self) -> int:
        """Hidden width of the MLP.

        gelu: 4*d_model. swiglu: 2/3 of that (rounded up to a multiple of 8), so both variants
        have about the same parameter count and an ablation compares like with like.
        """
        if self.d_ff is not None:
            return self.d_ff
        if self.mlp == "gelu":
            return 4 * self.d_model
        return 8 * ((int(8 * self.d_model / 3) + 7) // 8)

    # ---- serialisation ----------------------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def config_hash(self) -> str:
        """sha256 of the canonical JSON of all fields (first 16 hex chars, as in experiments/log.jsonl)."""
        blob = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DecoderConfig":
        known = {f.name for f in fields(cls)}
        unknown = set(data) - known
        if unknown:
            raise ModelConfigError(f"unknown config keys: {sorted(unknown)}")
        return cls(**data)

    @classmethod
    def from_yaml(cls, path: str | Path) -> "DecoderConfig":
        from nawa.config import load_yaml

        data = load_yaml(path)
        if "model" not in data or not isinstance(data["model"], dict):
            raise ModelConfigError(f"{path}: expected a top-level 'model' mapping")
        return cls.from_dict(data["model"])
