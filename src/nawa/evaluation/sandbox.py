"""Minimal sandbox for running model-written Python (SECURITY.md §4).

Limits: separate interpreter in isolated mode (-I), a temporary working directory, a CPU-time
and address-space rlimit, a wall-clock timeout, an empty environment, and a socket module
disabled by a prelude.
Limitation: this is process-level isolation, not a container or VM. It is sufficient for short
evaluation snippets, not for untrusted production workloads (P6-02 must replace it).
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass

PRELUDE = """
import socket as _s
def _blocked(*a, **k):
    raise OSError("network disabled in NAWA sandbox")
_s.socket = _blocked; _s.create_connection = _blocked
"""


@dataclass
class RunResult:
    ok: bool
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool


def _limits() -> None:  # pragma: no cover - runs in child
    import resource
    resource.setrlimit(resource.RLIMIT_CPU, (5, 5))
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_FSIZE, (1024 * 1024, 1024 * 1024))
    os.setsid()


def run_python(code: str, timeout: float = 10.0) -> RunResult:
    with tempfile.TemporaryDirectory(prefix="nawa-sbx-") as d:
        path = os.path.join(d, "main.py")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(PRELUDE + "\n" + code)
        try:
            p = subprocess.run([sys.executable, "-I", path], cwd=d, capture_output=True, text=True,
                               timeout=timeout, env={"PATH": "/usr/bin:/bin"}, preexec_fn=_limits)
            return RunResult(p.returncode == 0, p.returncode, p.stdout[-4000:], p.stderr[-4000:], False)
        except subprocess.TimeoutExpired as e:
            return RunResult(False, -1, "", str(e)[-500:], True)
