"""NAWA tools (ROADMAP P6-02; code-only scope, ADR-0008): exact calculator, Python sandbox without network, read-only
file inspector, permissions, allowlist and audit log. No search or external API (P6-02a, BLOCKED until OD-11)."""

from nawa.tools.audit import AuditLog, AuditRecord, verify_chain
from nawa.tools.calculator import CalcError, CalcResult, calculate
from nawa.tools.files import FileAccessError, FileInspector
from nawa.tools.registry import Permission, ToolRegistry, ToolResult, ToolSpec, default_registry
from nawa.tools.sandbox import SandboxPolicy, SandboxResult, run_code

__all__ = ["AuditLog", "AuditRecord", "CalcError", "CalcResult", "FileAccessError", "FileInspector", "Permission",
           "SandboxPolicy", "SandboxResult", "ToolRegistry", "ToolResult", "ToolSpec", "calculate", "default_registry",
           "run_code", "verify_chain"]
