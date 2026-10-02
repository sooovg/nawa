"""Python sandbox tool without network (ROADMAP P6-02, SECURITY.md §4, ADR-0008).

Layers, each tested by behaviour:

1. **Separate interpreter:** ``python -I -S -B -X utf8``. It runs with an empty environment (``HOME`` and ``TMPDIR``
   point to a fresh temporary directory), and that directory is the working directory. It is deleted afterwards.
2. **Resource limits (rlimits):** CPU seconds, address space, file size, open files, and no new processes
   (``RLIMIT_NPROC`` = 0). There is also a wall-clock timeout. stdout and stderr are truncated to a fixed size.
3. **A runtime audit hook** (:pep:`578`), installed before the user code runs. Python code cannot remove it. It denies:
   - every ``socket.*`` event (no network);
   - importing network, process or FFI modules (``socket``, ``ssl``, ``subprocess``, ``ctypes``, ...);
   - process creation (``os.system``, ``os.exec*``, ``os.posix_spawn``, ``os.fork``, ``subprocess.Popen``, ...);
   - writes, deletes, renames and permission changes outside the working directory;
   - reads outside the working directory and the standard library (installed third-party packages excluded), except
     ``/dev/urandom``, ``/dev/random`` and ``/dev/null``.

   Denied modules are also set to ``None`` in ``sys.modules``, so ``importlib.import_module`` fails as well.

   A denied action raises ``PermissionError`` inside the user code. It is also reported on a private pipe, as a
   best-effort list in :attr:`SandboxResult.denied`. Enforcement does not depend on that list: user code can close the
   pipe, but cannot undo a denial.

Limitation (unchanged from ``nawa.evaluation.sandbox``): this is process-level isolation, not a container or VM. It is
meant for short tool snippets. It is not meant for untrusted production workloads; that is a deployment decision
(P9/P10). ``nawa.evaluation.sandbox`` is deliberately left unchanged. Switching the evaluation runner and the P2
verifier to this sandbox is a separate step, because it could change code-suite results (Eval role).
"""

from __future__ import annotations

import os
import subprocess
import sys
import sysconfig
import tempfile
from dataclasses import dataclass

DENY_IMPORTS = ("socket", "_socket", "ssl", "_ssl", "select", "selectors", "asyncio", "subprocess", "_posixsubprocess",
                "multiprocessing", "_multiprocessing", "concurrent", "ctypes", "_ctypes", "cffi", "urllib", "http",
                "ftplib", "smtplib", "imaplib", "poplib", "telnetlib", "xmlrpc", "socketserver", "webbrowser", "pty")
DENY_EVENTS = ("os.system", "os.exec", "os.posix_spawn", "os.spawn", "os.fork", "os.forkpty", "os.kill", "os.killpg",
               "subprocess.Popen", "pty.spawn", "ctypes.", "resource.setrlimit", "os.startfile", "webbrowser.open",
               "sys.remote_exec")
PATH_EVENTS = ("os.remove", "os.rename", "os.rmdir", "os.mkdir", "os.chmod", "os.chown", "os.symlink", "os.link",
               "os.truncate", "os.utime", "shutil.rmtree", "shutil.move", "shutil.copyfile", "os.chdir")

BOOT = r'''
import os as _os, sys as _sys
_WORK = _os.path.realpath({work!r})
_READ = tuple(_os.path.realpath(p) for p in {read_roots!r}) + (_WORK,)
_NOREAD = tuple(_os.path.realpath(p) for p in {noread_roots!r})
_READ_FILES = frozenset(("/dev/urandom", "/dev/random", "/dev/null"))
_DENY_IMPORTS = frozenset({deny_imports!r})
_DENY_EVENTS = {deny_events!r}
_PATH_EVENTS = frozenset({path_events!r})
_FD = {fd}
_WFLAGS = _os.O_WRONLY | _os.O_RDWR | _os.O_CREAT | _os.O_APPEND | _os.O_TRUNC
_count = [0]

def _under(p, roots):
    return any(p == r or p.startswith(r + _os.sep) for r in roots)

def _readable(p):
    return p in _READ_FILES or (_under(p, _READ) and not _under(p, _NOREAD))

def _real(p):
    if isinstance(p, bytes):
        p = _os.fsdecode(p)
    return _os.path.realpath(_os.path.join(_WORK, p))

def _deny(event, detail):
    if _count[0] < 50:
        _count[0] += 1
        try:
            _os.write(_FD, (event + " " + str(detail)[:120]).encode("utf-8", "replace").replace(b"\n", b" ") + b"\n")
        except OSError:
            pass
    raise PermissionError("NAWA sandbox denied " + event)

def _hook(event, args):
    if event.startswith("socket."):
        _deny(event, args[:1] if args else "")
    if event == "import":
        name = str(args[0])
        if name.split(".")[0] in _DENY_IMPORTS:
            _deny("import", name)
        return
    if event.startswith(_DENY_EVENTS):
        _deny(event, "")
    if event == "open":
        path, mode, flags = (tuple(args) + (None, None, None))[:3]
        if isinstance(path, int) or path is None:
            return
        real = _real(path)
        writing = (isinstance(mode, str) and any(c in mode for c in "wax+")) or \
                  (isinstance(flags, int) and flags & _WFLAGS)
        if writing and not _under(real, (_WORK,)):
            _deny("open-write", real)
        if not writing and not _readable(real):
            _deny("open-read", real)
        return
    if event in ("os.listdir", "os.scandir"):
        if args and args[0] is not None and not isinstance(args[0], int) and not _readable(_real(args[0])):
            _deny(event, _real(args[0]))
        return
    if event in _PATH_EVENTS:
        for a in args:
            if isinstance(a, (str, bytes, _os.PathLike)) and not _under(_real(_os.fspath(a)), (_WORK,)):
                _deny(event, _real(_os.fspath(a)))

with open(_os.path.join(_WORK, "main.py"), encoding="utf-8") as _fh:
    _code = compile(_fh.read(), "main.py", "exec")
for _name in _DENY_IMPORTS:
    _sys.modules[_name] = None      # importlib.import_module() raises ModuleNotFoundError as well
_sys.addaudithook(_hook)
del _fh, _name
exec(_code, {{"__name__": "__main__", "__builtins__": __builtins__}})
'''


@dataclass(frozen=True)
class SandboxPolicy:
    timeout_s: float = 10.0
    cpu_s: int = 5
    memory_bytes: int = 512 * 1024 * 1024
    file_bytes: int = 1024 * 1024
    open_files: int = 64
    max_output_chars: int = 4000

    def __post_init__(self) -> None:
        checks = [(self.timeout_s, 0.1, 120.0), (self.cpu_s, 1, 60), (self.memory_bytes, 64 * 1024 * 1024, 4 << 30),
                  (self.file_bytes, 0, 64 * 1024 * 1024), (self.open_files, 16, 1024),
                  (self.max_output_chars, 100, 1_000_000)]
        for value, lo, hi in checks:
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not lo <= value <= hi:
                raise ValueError(f"sandbox policy value {value!r} outside [{lo}, {hi}]")


@dataclass(frozen=True)
class SandboxResult:
    ok: bool
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool
    truncated: bool
    denied: tuple[str, ...]


def _limits(policy: SandboxPolicy):  # pragma: no cover - runs in the child
    def apply() -> None:
        import resource
        resource.setrlimit(resource.RLIMIT_CPU, (policy.cpu_s, policy.cpu_s))
        resource.setrlimit(resource.RLIMIT_AS, (policy.memory_bytes, policy.memory_bytes))
        resource.setrlimit(resource.RLIMIT_FSIZE, (policy.file_bytes, policy.file_bytes))
        resource.setrlimit(resource.RLIMIT_NOFILE, (policy.open_files, policy.open_files))
        resource.setrlimit(resource.RLIMIT_NPROC, (0, 0))
        os.setsid()
    return apply


def _read_roots() -> tuple[str, ...]:
    paths = sysconfig.get_paths()
    return tuple(sorted({paths["stdlib"], paths["platstdlib"]}))


def _noread_roots() -> tuple[str, ...]:
    """Installed third-party packages sit under the stdlib directory; they are not readable."""
    paths = sysconfig.get_paths()
    return tuple(sorted({paths["purelib"], paths["platlib"]}))


def run_code(code: str, policy: SandboxPolicy | None = None) -> SandboxResult:
    if not isinstance(code, str):
        raise ValueError("code must be a string")
    policy = policy or SandboxPolicy()
    with tempfile.TemporaryDirectory(prefix="nawa-tool-sbx-") as work:
        work = os.path.realpath(work)
        with open(os.path.join(work, "main.py"), "w", encoding="utf-8") as fh:
            fh.write(code)
        r_fd, w_fd = os.pipe()
        boot = BOOT.format(work=work, read_roots=_read_roots(), noread_roots=_noread_roots(), deny_imports=DENY_IMPORTS,
                           deny_events=DENY_EVENTS, path_events=PATH_EVENTS, fd=w_fd)
        env = {"HOME": work, "TMPDIR": work}
        timed_out = False
        try:
            p = subprocess.run([sys.executable, "-I", "-S", "-B", "-X", "utf8", "-c", boot], cwd=work,
                               capture_output=True, timeout=policy.timeout_s, env=env, pass_fds=(w_fd,),
                               preexec_fn=_limits(policy))
            rc, out, err = p.returncode, p.stdout, p.stderr
        except subprocess.TimeoutExpired as e:
            timed_out, rc, out, err = True, -9, e.stdout or b"", e.stderr or b""
        finally:
            os.close(w_fd)
        os.set_blocking(r_fd, False)
        try:
            raw = os.read(r_fd, 1 << 16)
        except BlockingIOError:
            raw = b""
        finally:
            os.close(r_fd)
    n = policy.max_output_chars
    out_s, err_s = out.decode("utf-8", "replace"), err.decode("utf-8", "replace")
    truncated = len(out_s) > n or len(err_s) > n
    denied = tuple(line for line in raw.decode("utf-8", "replace").splitlines() if line)
    return SandboxResult(rc == 0 and not timed_out, rc, out_s[:n], err_s[-n:], timed_out, truncated, denied)
