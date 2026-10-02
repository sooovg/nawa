"""Tool permissions, allowlist and calls with audit (ROADMAP P6-02, SECURITY.md §4, ADR-0008).

* A tool runs only if it is on the registry's **allowlist** and its **permission** has been granted to the registry.
  The default grant is empty (least privilege).
* The ``NETWORK`` permission cannot be granted and no tool that needs it can be registered: search and external APIs are
  P6-02a, BLOCKED until the owner decides OD-11 (ADR-0008 D3). A request for ``search`` is refused with that reason.
* Every call, including refused and failed ones, appends one record to the :class:`~nawa.tools.audit.AuditLog`.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from nawa.tools.audit import AuditLog
from nawa.tools.calculator import CalcError, calculate
from nawa.tools.files import FileAccessError, FileInspector
from nawa.tools.sandbox import SandboxPolicy, run_code


class Permission(str, Enum):
    CALCULATE = "CALCULATE"
    EXECUTE_CODE = "EXECUTE_CODE"
    READ_FILES = "READ_FILES"
    NETWORK = "NETWORK"


BLOCKED = {Permission.NETWORK: "P6-02a BLOCKED until OD-11 (ADR-0008): no search or external API"}
BLOCKED_TOOLS = {"search": BLOCKED[Permission.NETWORK], "web": BLOCKED[Permission.NETWORK],
                 "http": BLOCKED[Permission.NETWORK], "api": BLOCKED[Permission.NETWORK]}


@dataclass(frozen=True)
class ToolSpec:
    name: str
    permission: Permission
    func: Callable[[dict], object]
    description: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.isidentifier():
            raise ValueError("tool name must be an identifier")
        if not isinstance(self.permission, Permission):
            raise ValueError("permission must be a Permission")
        if self.permission in BLOCKED or self.name in BLOCKED_TOOLS:
            raise ValueError(BLOCKED.get(self.permission) or BLOCKED_TOOLS[self.name])


@dataclass(frozen=True)
class ToolResult:
    ok: bool
    outcome: str          # ok | error | denied | timeout
    reason: str
    output: object
    audit_seq: int


class ToolRegistry:
    def __init__(self, tools: Iterable[ToolSpec], grants: Iterable[Permission] = (), audit: AuditLog | None = None):
        self.tools: dict[str, ToolSpec] = {}
        for t in tools:
            if t.name in self.tools:
                raise ValueError(f"duplicate tool {t.name!r}")
            self.tools[t.name] = t
        grants = frozenset(grants)
        for g in grants:
            if not isinstance(g, Permission):
                raise ValueError(f"not a Permission: {g!r}")
            if g in BLOCKED:
                raise ValueError(BLOCKED[g])
        self.grants = grants
        self.audit = audit if audit is not None else AuditLog()

    def _finish(self, name: str, perm: Permission | None, caller: str, outcome: str, reason: str, payload: object,
                output: object) -> ToolResult:
        rec = self.audit.append(tool=name, permission=None if perm is None else perm.value, caller=caller,
                                outcome=outcome, reason=reason, payload=payload,
                                output=None if outcome == "denied" else output)
        return ToolResult(outcome == "ok", outcome, reason, output, rec.seq)

    def call(self, name: str, payload: dict, caller: str = "agent") -> ToolResult:
        if not isinstance(payload, dict):
            return self._finish(str(name), None, caller, "denied", "bad_payload: payload must be a dict", repr(payload),
                                None)
        if name in BLOCKED_TOOLS:
            return self._finish(name, Permission.NETWORK, caller, "denied", BLOCKED_TOOLS[name], payload, None)
        spec = self.tools.get(name)
        if spec is None:
            return self._finish(str(name), None, caller, "denied", "not_allowlisted", payload, None)
        if spec.permission not in self.grants:
            return self._finish(name, spec.permission, caller, "denied", "permission_not_granted", payload, None)
        try:
            out = spec.func(payload)
        except (CalcError, FileAccessError) as e:
            return self._finish(name, spec.permission, caller, "error", e.code, payload, None)
        except (KeyError, TypeError, ValueError) as e:
            return self._finish(name, spec.permission, caller, "error", f"bad_payload: {type(e).__name__}", payload,
                                None)
        if isinstance(out, dict) and out.get("timed_out"):
            return self._finish(name, spec.permission, caller, "timeout", "timeout", payload, out)
        if isinstance(out, dict) and out.get("ok") is False:
            return self._finish(name, spec.permission, caller, "error", "execution_failed", payload, out)
        return self._finish(name, spec.permission, caller, "ok", "ok", payload, out)


def _calc(payload: dict) -> dict:
    r = calculate(payload["expression"])
    return {"exact": r.exact, "decimal": r.decimal(int(payload.get("places", 12)))}


def _python(policy: SandboxPolicy) -> Callable[[dict], dict]:
    def run(payload: dict) -> dict:
        code = payload["code"]
        if not isinstance(code, str):
            raise TypeError("code must be a string")
        r = run_code(code, policy)
        return {"ok": r.ok, "returncode": r.returncode, "stdout": r.stdout, "stderr": r.stderr,
                "timed_out": r.timed_out, "truncated": r.truncated, "denied": list(r.denied)}
    return run


def _files(root: Path) -> list[ToolSpec]:
    fi = FileInspector(root)

    def read(payload: dict) -> dict:
        t = fi.read_text(payload["path"], payload.get("max_bytes"))
        return {"path": t.path, "text": t.text, "size": t.size, "truncated": t.truncated, "sha256": t.sha256}

    return [ToolSpec("list_files", Permission.READ_FILES, lambda p: fi.list_dir(p.get("path", ".")),
                     "list a directory under the root"),
            ToolSpec("stat_file", Permission.READ_FILES, lambda p: fi.stat(p["path"]), "size, type and sha256"),
            ToolSpec("read_file", Permission.READ_FILES, read, "read a text file under the root (read-only)")]


def default_registry(*, grants: Iterable[Permission] = (), files_root: Path | str | None = None,
                     policy: SandboxPolicy | None = None, audit: AuditLog | None = None) -> ToolRegistry:
    """calculator and python always registered; file tools only when a root is given. Nothing is granted by default."""
    tools = [ToolSpec("calculator", Permission.CALCULATE, _calc, "exact rational arithmetic"),
             ToolSpec("python", Permission.EXECUTE_CODE, _python(policy or SandboxPolicy()),
                      "run Python in the sandbox without network")]
    if files_root is not None:
        tools += _files(Path(files_root))
    return ToolRegistry(tools, grants, audit)
