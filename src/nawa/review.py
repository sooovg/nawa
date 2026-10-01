"""Multi-model development review harness (ROADMAP R-03, ADR-0003 D1).

Provides the framework for using external models as development tools during
NAWA's construction. No decision rests on a single model. No frozen data, user
data, or secrets are sent to any external model.

This module is the harness, not the models themselves. It provides:
- Role registry and validation.
- Review record logging.
- Disagreement logging and resolution.
- Payload safety checks.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Roles
# ---------------------------------------------------------------------------

class ReviewRole(str, Enum):
    """Roles an external model may play during development (ADR-0003 D1)."""
    REVIEWER = "reviewer"
    DESIGNER = "designer"
    TESTER = "tester"
    ERROR_HUNTER = "error_hunter"
    DOC_WRITER = "doc_writer"

    @classmethod
    def from_str(cls, value: str) -> "ReviewRole":
        try:
            return cls(value)
        except ValueError:
            raise ValueError(
                f"unknown review role {value!r}; expected one of "
                f"{[r.value for r in cls]}"
            )


# ---------------------------------------------------------------------------
# Model registry
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ModelEntry:
    """A registered external model that may be used as a development tool."""
    model_id: str                    # e.g. "openai/gpt-4o"
    provider: str                    # e.g. "openai"
    roles: frozenset[str]            # subset of ReviewRole values
    authorized_by: str               # "owner" or "agent" (owner must confirm)
    date_added: str                  # ISO date
    notes: str = ""

    def has_role(self, role: ReviewRole | str) -> bool:
        if isinstance(role, ReviewRole):
            role = role.value
        return role in self.roles

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "provider": self.provider,
            "roles": sorted(self.roles),
            "authorized_by": self.authorized_by,
            "date_added": self.date_added,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ModelEntry":
        return cls(
            model_id=data["model_id"],
            provider=data["provider"],
            roles=frozenset(data["roles"]),
            authorized_by=data["authorized_by"],
            date_added=data["date_added"],
            notes=data.get("notes", ""),
        )


class ModelRegistry:
    """Registry of authorized external models for development review.

    A model not in this registry is not used. The registry is intentionally
    empty by default: providers are added when OD-10 is resolved or when the
    owner authorises a specific model.
    """

    def __init__(self) -> None:
        self._models: dict[str, ModelEntry] = {}

    def register(self, entry: ModelEntry) -> None:
        if entry.model_id in self._models:
            raise ValueError(f"model {entry.model_id!r} already registered")
        self._models[entry.model_id] = entry

    def get(self, model_id: str) -> ModelEntry | None:
        return self._models.get(model_id)

    def list_models(self) -> list[ModelEntry]:
        return sorted(self._models.values(), key=lambda m: m.model_id)

    def has_model(self, model_id: str) -> bool:
        return model_id in self._models

    def require_model(self, model_id: str) -> ModelEntry:
        entry = self.get(model_id)
        if entry is None:
            raise ValueError(
                f"model {model_id!r} is not registered; "
                "only registered models may be used as development tools (R-03)"
            )
        return entry

    def require_role(self, model_id: str, role: ReviewRole | str) -> ModelEntry:
        entry = self.require_model(model_id)
        if not entry.has_role(role):
            raise ValueError(
                f"model {model_id!r} is not registered for role "
                f"{role!r}; registered roles: {sorted(entry.roles)}"
            )
        return entry

    def to_dict(self) -> dict[str, Any]:
        return {"models": [m.to_dict() for m in self.list_models()]}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ModelRegistry":
        reg = cls()
        for m in data.get("models", []):
            reg.register(ModelEntry.from_dict(m))
        return reg


# ---------------------------------------------------------------------------
# Review records
# ---------------------------------------------------------------------------

@dataclass
class ReviewRecord:
    """A single review by an external model."""
    experiment_id: str
    model_id: str
    role: ReviewRole
    artifact: str                      # file or component reviewed
    review_date: str                   # ISO date
    findings: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    accepted: list[str] = field(default_factory=list)
    rejected: list[str] = field(default_factory=list)
    conclusion: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "model_id": self.model_id,
            "role": self.role.value,
            "artifact": self.artifact,
            "review_date": self.review_date,
            "findings": self.findings,
            "recommendations": self.recommendations,
            "accepted": self.accepted,
            "rejected": self.rejected,
            "conclusion": self.conclusion,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ReviewRecord":
        return cls(
            experiment_id=data["experiment_id"],
            model_id=data["model_id"],
            role=ReviewRole.from_str(data["role"]),
            artifact=data["artifact"],
            review_date=data["review_date"],
            findings=data.get("findings", []),
            recommendations=data.get("recommendations", []),
            accepted=data.get("accepted", []),
            rejected=data.get("rejected", []),
            conclusion=data.get("conclusion", ""),
        )


# ---------------------------------------------------------------------------
# Disagreement records
# ---------------------------------------------------------------------------

@dataclass
class DisagreementRecord:
    """A conflict between two or more external models on the same artifact."""
    disagreement_id: str
    artifact: str
    positions: list[dict[str, str]]    # [{"model": "...", "position": "..."}]
    resolution: str = "deferred"       # measurement|test|owner_decision|deferred
    resolved: bool = False
    resolution_note: str = ""

    def resolve(self, method: str, note: str) -> None:
        if method not in ("measurement", "test", "owner_decision", "deferred"):
            raise ValueError(
                f"resolution method must be 'measurement', 'test', "
                f"'owner_decision', or 'deferred'; got {method!r}"
            )
        self.resolution = method
        self.resolved = (method != "deferred")
        self.resolution_note = note

    def to_dict(self) -> dict[str, Any]:
        return {
            "disagreement_id": self.disagreement_id,
            "artifact": self.artifact,
            "positions": self.positions,
            "resolution": self.resolution,
            "resolved": self.resolved,
            "resolution_note": self.resolution_note,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DisagreementRecord":
        return cls(
            disagreement_id=data["disagreement_id"],
            artifact=data["artifact"],
            positions=data.get("positions", []),
            resolution=data.get("resolution", "deferred"),
            resolved=data.get("resolved", False),
            resolution_note=data.get("resolution_note", ""),
        )


# ---------------------------------------------------------------------------
# Review log (append-only)
# ---------------------------------------------------------------------------

class ReviewLog:
    """Append-only log of reviews and disagreements.

    Stored as JSONL in a file. Each line is either a review or a disagreement.
    """

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else None
        self.reviews: list[ReviewRecord] = []
        self.disagreements: list[DisagreementRecord] = []

    def add_review(self, review: ReviewRecord) -> None:
        self.reviews.append(review)
        self._append("review", review.to_dict())

    def add_disagreement(self, disagreement: DisagreementRecord) -> None:
        self.disagreements.append(disagreement)
        self._append("disagreement", disagreement.to_dict())

    def resolve_disagreement(self, disagreement_id: str, method: str, note: str) -> None:
        for d in self.disagreements:
            if d.disagreement_id == disagreement_id:
                d.resolve(method, note)
                self._append("disagreement_resolved", {
                    "disagreement_id": disagreement_id,
                    "method": method,
                    "note": note,
                })
                return
        raise ValueError(f"disagreement {disagreement_id!r} not found")

    def get_disagreements(self, resolved: bool | None = None) -> list[DisagreementRecord]:
        if resolved is None:
            return list(self.disagreements)
        return [d for d in self.disagreements if d.resolved == resolved]

    def get_reviews_for_artifact(self, artifact: str) -> list[ReviewRecord]:
        return [r for r in self.reviews if r.artifact == artifact]

    def get_reviews_by_model(self, model_id: str) -> list[ReviewRecord]:
        return [r for r in self.reviews if r.model_id == model_id]

    def has_multiple_models_reviewed(self, artifact: str) -> bool:
        """Check if an artifact has been reviewed by at least 2 different models."""
        models = {r.model_id for r in self.get_reviews_for_artifact(artifact)}
        return len(models) >= 2

    def can_decide(self, artifact: str) -> bool:
        """Check if a decision can be made on an artifact.

        A decision requires either:
        - At least 2 models have reviewed it, OR
        - 1 model has reviewed it AND a deterministic check exists (external).
        This method checks the multi-model condition only.
        """
        return self.has_multiple_models_reviewed(artifact)

    def _append(self, record_type: str, data: dict[str, Any]) -> None:
        if self.path is None:
            return
        entry = {"type": record_type, **data}
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def load(self) -> None:
        """Load from the file."""
        if self.path is None or not self.path.is_file():
            return
        self.reviews.clear()
        self.disagreements.clear()
        with self.path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                entry_type = entry.pop("type", None)
                if entry_type == "review":
                    self.reviews.append(ReviewRecord.from_dict(entry))
                elif entry_type == "disagreement":
                    self.disagreements.append(DisagreementRecord.from_dict(entry))
                elif entry_type == "disagreement_resolved":
                    # Update the disagreement in memory
                    for d in self.disagreements:
                        if d.disagreement_id == entry.get("disagreement_id"):
                            d.resolve(entry.get("method", "deferred"), entry.get("note", ""))

    def summary(self) -> dict[str, Any]:
        return {
            "total_reviews": len(self.reviews),
            "total_disagreements": len(self.disagreements),
            "unresolved_disagreements": len(self.get_disagreements(resolved=False)),
            "artifacts_reviewed": len({r.artifact for r in self.reviews}),
            "models_used": sorted({r.model_id for r in self.reviews}),
        }


# ---------------------------------------------------------------------------
# Payload safety checks
# ---------------------------------------------------------------------------

# Patterns that should never be sent to an external model
_FORBIDDEN_PATTERNS = [
    re.compile(r"(?i)hf_[a-zA-Z0-9_-]{10,}"),          # HF tokens (shorter threshold for safety)
    re.compile(r"(?i)ghp_[a-zA-Z0-9]{10,}"),            # GitHub PATs (shorter threshold)
    re.compile(r"(?i)gho_[a-zA-Z0-9]{36}"),             # GitHub OAuth
    re.compile(r"(?i)github_pat_[a-zA-Z0-9_]{10,}"),   # GitHub fine-grained
    re.compile(r"(?i)sk-[a-zA-Z0-9]{10,}"),              # OpenAI-style API keys
    re.compile(r"(?i)frozen[_-]?(v\d+|sha256|manifest)"),  # frozen eval references
    re.compile(r"(?i)(password|passwd|secret|token)\s*[:=]\s*\S+"),  # credential assignments
]

# File paths that should never be sent
_FORBIDDEN_PATHS = [
    "eval/frozen",
    "FROZEN.sha256",
    "frozen_manifest.yaml",
    "frozen_item_hashes.txt",
    ".env",
    ".secrets",
]


@dataclass
class PayloadCheck:
    """Result of a payload safety check."""
    safe: bool
    violations: list[str] = field(default_factory=list)


def check_payload(payload: str | dict[str, Any] | list) -> PayloadCheck:
    """Check if a payload is safe to send to an external model.

    Scans for:
    - API keys and tokens (HF, GitHub, OpenAI-style)
    - References to frozen evaluation data
    - Credential assignments
    - Forbidden file paths

    Returns a PayloadCheck with safe=False and violations list if any pattern matches.
    """
    text = json.dumps(payload, ensure_ascii=False) if not isinstance(payload, str) else payload
    violations: list[str] = []

    for pattern in _FORBIDDEN_PATTERNS:
        matches = pattern.findall(text)
        if matches:
            violations.append(f"forbidden pattern matched: {pattern.pattern[:50]}...")

    for forbidden_path in _FORBIDDEN_PATHS:
        if forbidden_path in text:
            violations.append(f"forbidden path reference: {forbidden_path}")

    return PayloadCheck(safe=len(violations) == 0, violations=violations)


# ---------------------------------------------------------------------------
# Decision gate
# ---------------------------------------------------------------------------

def can_decide(
    artifact: str,
    review_log: ReviewLog,
    deterministic_check_passed: bool = False,
) -> tuple[bool, str]:
    """Check if a decision can be made on an artifact.

    A decision is allowed if:
    1. At least 2 different models have reviewed it, OR
    2. 1 model has reviewed it AND a deterministic check has passed.

    This implements ADR-0003 D4: "A model's opinion is a hypothesis. It becomes
    a project fact only through a deterministic check, an executed test, a
    measurement with confidence intervals, or independent reviewers followed
    by one of these checks."

    Returns (can_decide, reason).
    """
    reviews = review_log.get_reviews_for_artifact(artifact)
    models = {r.model_id for r in reviews}

    if len(models) >= 2:
        return True, "multiple models reviewed the artifact"

    if len(models) == 1 and deterministic_check_passed:
        return True, "single model reviewed + deterministic check passed"

    if len(models) == 0:
        return False, "no model has reviewed this artifact"

    return False, (
        "single model reviewed without deterministic check; "
        "a decision requires either 2+ models or 1 model + deterministic check"
    )


# ---------------------------------------------------------------------------
# Convenience
# ---------------------------------------------------------------------------

def make_review(
    experiment_id: str,
    model_id: str,
    role: ReviewRole | str,
    artifact: str,
    findings: list[str] | None = None,
    recommendations: list[str] | None = None,
    conclusion: str = "",
) -> ReviewRecord:
    """Create a ReviewRecord with today's date."""
    if isinstance(role, str):
        role = ReviewRole.from_str(role)
    return ReviewRecord(
        experiment_id=experiment_id,
        model_id=model_id,
        role=role,
        artifact=artifact,
        review_date=date.today().isoformat(),
        findings=findings or [],
        recommendations=recommendations or [],
        conclusion=conclusion,
    )
