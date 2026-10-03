"""NAWA memory (ROADMAP P7-05; code-only scope, ADR-0009).

Five core kinds (conversation, durable user memory with consent, task, knowledge with source and confidence,
experience/procedures) plus a transient sensory buffer by modality; an extended registry that gives every requested
memory name an explicit status; one store with isolation per (user, project), provenance and confidence on every item,
logical time, deterministic consolidation and replay, and real forgetting with a hash-chained log.

Synthetic users only (``user_alpha``, ``user_beta``, ``user_gamma``). This is NOT a final privacy policy: OD-12 (personal
memory privacy policy) must be decided by the owner before any real user memory is stored (P7-05a, BLOCKED). No external
model, no network, no Hugging Face.
"""

from nawa.memory.forgetting import ForgetEntry, ForgettingLog, trace_scan
from nawa.memory.isolation import DEFAULT_PROJECT, OD12_NOTICE, SYNTHETIC_USERS, IsolationError, Principal
from nawa.memory.orchestrator import MemoryOrchestrator, UnknownOperation
from nawa.memory.policy import PolicyViolation
from nawa.memory.provenance import Provenance, ProvenanceError, SourceType
from nawa.memory.store import Hit, LogicalClock, MemoryStore
from nawa.memory.types import REGISTRY, MemoryItem, MemoryKind, Modality, RegistryStatus, TaskStatus, lookup

__all__ = ["DEFAULT_PROJECT", "OD12_NOTICE", "REGISTRY", "SYNTHETIC_USERS", "ForgetEntry", "ForgettingLog", "Hit",
           "IsolationError", "LogicalClock", "MemoryItem", "MemoryKind", "MemoryOrchestrator", "MemoryStore",
           "Modality", "PolicyViolation", "Principal", "Provenance", "ProvenanceError", "RegistryStatus",
           "SourceType", "TaskStatus", "UnknownOperation", "lookup", "trace_scan"]
