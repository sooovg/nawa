"""P6-02: exact calculator, sandbox without network, read-only file inspector, permissions and audit (ADR-0008).

Deterministic tests only; no external model, no network, no real data. Search/API (P6-02a) stays BLOCKED (OD-11).
"""

from __future__ import annotations

import dataclasses
import json
import os
import random
import subprocess
import sys
import sysconfig
from decimal import ROUND_HALF_UP, Decimal, localcontext
from fractions import Fraction
from pathlib import Path

import pytest

from nawa.tools import audit as au
from nawa.tools.audit import AuditLog, verify_chain
from nawa.tools.calculator import MAX_EXPONENT, CalcError, CalcResult, calculate
from nawa.tools.files import FileAccessError, FileInspector
from nawa.tools.registry import Permission, ToolRegistry, ToolSpec, default_registry
from nawa.tools.sandbox import SandboxPolicy, run_code

ROOT = Path(__file__).resolve().parents[1]
IS_ROOT = hasattr(os, "geteuid") and os.geteuid() == 0
OUTSIDE = f"/tmp/nawa-should-not-exist-{os.getpid()}-{random.Random().getrandbits(32):08x}"   # unique per run


# ==== calculator ====================================================================================================
@pytest.mark.parametrize("expr,exact", [
    ("0.1 + 0.2", "3/10"), ("1/3 * 3", "1"), ("2 ** -2", "1/4"), ("7 // 2", "3"), ("-7 // 2", "-4"), ("7 % 3", "1"),
    ("-(3 - 5) * 4", "8"), ("(1 + 2) * (3 + 4) / 7", "3"), (".5 + 5.", "11/2"), ("10 ** 20", "1" + "0" * 20),
    ("٣ × ٤", "12"), ("(" * 100 + "1" + ")" * 100, "1"), ("٢٫٥ + ١", "7/2"), ("۱۲ ÷ ۴", "3"), ("5 − 7", "-2"), ("0 ** 0", "1"),
])
def test_calculator_exact_results(expr: str, exact: str) -> None:
    assert calculate(expr).exact == exact


@pytest.mark.parametrize("expr,code", [
    ("x + 1", "not_allowed"), ("abs(-1)", "not_allowed"), ("__import__('os')", "not_allowed"),
    ("(1).real", "not_allowed"), ("'a' * 3", "bad_literal"), ("1 < 2", "not_allowed"), ("1 and 2", "not_allowed"),
    ("lambda: 1", "not_allowed"), ("[1][0]", "not_allowed"), ("1e5", "bad_literal"), ("0x10", "bad_literal"),
    ("1_000", "bad_literal"), ("1j", "bad_literal"), ("True + 1", "bad_literal"), ("2 ** 0.5", "non_integer_exponent"),
    ("2 ** 100000", "too_large"), ("9 ** 9 ** 9", "too_large"), ("123456789 ** 1000", "too_large"),
    ("1 / 0", "division_by_zero"), ("1 % 0", "division_by_zero"), ("1 // (2 - 2)", "division_by_zero"),
    ("0 ** -1", "division_by_zero"), ("", "bad_input"), ("1 +", "syntax"), ("1" * 600, "too_long"),
    ("(1+" * 70 + "1" + ")" * 70, "too_deep"), ("-" * 200 + "1", "too_deep"),
])
def test_calculator_refuses_with_a_stable_code(expr: str, code: str) -> None:
    with pytest.raises(CalcError) as e:
        calculate(expr)
    assert e.value.code == code


def test_calculator_rejects_non_strings() -> None:
    with pytest.raises(CalcError):
        calculate(3)  # type: ignore[arg-type]


def _rand_expr(rng: random.Random, depth: int) -> tuple[str, Fraction]:
    """An independent reference: build an expression and its value with Fraction directly."""
    if depth == 0 or rng.random() < 0.3:
        if rng.random() < 0.5:
            n = rng.randint(0, 999)
            return str(n), Fraction(n)
        a, b = rng.randint(0, 99), rng.randint(0, 999)
        return f"{a}.{b:03d}", Fraction(a) + Fraction(b, 1000)
    op = rng.choice(["+", "-", "*", "/", "neg", "**"])
    if op == "neg":
        s, v = _rand_expr(rng, depth - 1)
        return f"-({s})", -v
    if op == "**":
        s, v = _rand_expr(rng, depth - 1)
        e = rng.randint(-3, 3)
        if v == 0 and e < 0:
            e = -e
        return f"({s}) ** {e}", v ** e
    sa, va = _rand_expr(rng, depth - 1)
    sb, vb = _rand_expr(rng, depth - 1)
    if op == "/" and vb == 0:
        op = "+"
    return f"({sa}) {op} ({sb})", {"+": va + vb, "-": va - vb, "*": va * vb, "/": va / vb if vb else va + vb}[op]


def test_calculator_matches_fraction_reference_on_random_expressions() -> None:
    rng = random.Random(0)
    for _ in range(500):
        s, v = _rand_expr(rng, 4)
        try:
            got = calculate(s).value
        except CalcError as e:
            assert e.code == "too_large", (s, e)
            continue
        assert got == v, s


def test_decimal_rendering_matches_decimal_round_half_up() -> None:
    rng = random.Random(1)
    with localcontext() as ctx:
        ctx.prec = 200
        for _ in range(500):
            v = Fraction(rng.randint(-10 ** 6, 10 ** 6), rng.randint(1, 10 ** 4))
            places = rng.randint(0, 8)
            want = (Decimal(v.numerator) / Decimal(v.denominator)).quantize(Decimal(1).scaleb(-places),
                                                                            rounding=ROUND_HALF_UP)
            want_s = format(want.normalize(), "f") if want != 0 else "0"
            assert CalcResult(v).decimal(places) == want_s, (v, places)


@pytest.mark.parametrize("v,places,s", [(Fraction(1, 3), 4, "0.3333"), (Fraction(2, 3), 4, "0.6667"),
                                         (Fraction(-1, 8), 2, "-0.13"), (Fraction(1, 2), 0, "1"),
                                         (Fraction(-2, 5), 0, "0"), (Fraction(-5, 2), 0, "-3"), (Fraction(7), 3, "7")])
def test_decimal_rendering_examples(v: Fraction, places: int, s: str) -> None:
    assert CalcResult(v).decimal(places) == s


def test_exponent_limit_is_exact() -> None:
    assert calculate(f"1 ** {MAX_EXPONENT}").exact == "1"
    with pytest.raises(CalcError):
        calculate(f"1 ** {MAX_EXPONENT + 1}")


def test_calculator_never_uses_eval() -> None:
    src = (ROOT / "src/nawa/tools/calculator.py").read_text(encoding="utf-8")
    assert "eval(" not in src.replace("_eval(", "") and "exec(" not in src


# ==== sandbox =======================================================================================================
def sbx(code: str, **kw) -> object:
    return run_code(code, SandboxPolicy(**kw) if kw else None)


def test_sandbox_runs_ordinary_code_and_stdlib_imports() -> None:
    r = sbx("import json, math, re, fractions, decimal, statistics, collections, itertools, datetime, random\n"
            "print(json.dumps({'s': statistics.mean([1, 2, 3])}))")
    assert r.ok and r.stdout.strip() == '{"s": 2}' and r.denied == ()


def test_sandbox_can_write_and_read_its_own_directory_which_is_then_removed() -> None:
    r = sbx("import os\nopen('a.txt', 'w').write('hi')\nprint(open('a.txt').read(), os.getcwd())")
    word, cwd = r.stdout.split()
    assert r.ok and word == "hi" and not Path(cwd).exists()


@pytest.mark.parametrize("name,code,event", [
    ("import socket", "import socket", "import socket"),
    ("dynamic import", "__import__('so' + 'cket')", "import socket"),
    ("urllib", "import urllib.request", "import urllib"),
    ("subprocess", "import subprocess", "import subprocess"),
    ("socket after unhiding", "import sys, importlib\ndel sys.modules['_socket']\n"
                              "importlib.import_module('_socket').socket()", ("import _socket", "socket.__new__")),
    ("ctypes after unhiding", "import sys, importlib\ndel sys.modules['_ctypes']\n"
                              "importlib.import_module('_ctypes').dlopen(None)", ("import _ctypes", "ctypes.dlopen")),
    ("os.system", "import os\nos.system('true')", "os.system"),
    ("posix_spawn", "import os\nos.posix_spawn('/bin/true', ['true'], {})", "os.posix_spawn"),
    ("fork", "import os\nos.fork()", "os.fork"),
    ("read /etc/passwd", "open('/etc/passwd').read()", "open-read /etc/passwd"),
    ("read via os.open", "import os\nos.open('/etc/passwd', os.O_RDONLY)", "open-read /etc/passwd"),
    ("read the repo", f"open({str(ROOT / 'AGENTS.md')!r}).read()", "open-read"),
    ("read site-packages", f"open({sysconfig.get_paths()['purelib'] + '/x.py'!r})", "open-read"),
    ("write /tmp", f"open({OUTSIDE!r}, 'w')", f"open-write {OUTSIDE}"),
    ("write via os.open", f"import os\nos.open({OUTSIDE!r}, os.O_WRONLY | os.O_CREAT)", "open-write"),
    ("list /home", "import os\nos.listdir('/home')", "os.listdir"),
    ("remove outside", f"import os\nos.remove({OUTSIDE!r})", "os.remove"),
    ("symlink escape", "import os\nos.symlink('/etc/passwd', 'p')", "os.symlink"),
    ("chdir out", "import os\nos.chdir('/')", "os.chdir"),
    ("raise limits", "import resource\nresource.setrlimit(resource.RLIMIT_CPU, (100, 100))", "resource.setrlimit"),
])
def test_sandbox_denies_and_reports(name: str, code: str, event: str | tuple[str, ...]) -> None:
    """A tuple means either layer may stop it: a builtin module (no import event) is stopped at use, an extension module
    (``lib-dynload``, as on CI's Python) already at import. Either is a denial."""
    r = sbx(code)
    assert not r.ok and "PermissionError" in r.stderr, name
    assert any(d.startswith(event) for d in r.denied), (name, r.denied)
    assert not Path(OUTSIDE).exists()


def test_sandbox_hidden_module_cannot_be_imported_by_importlib() -> None:
    r = sbx("import importlib\nimportlib.import_module('_socket')")
    assert not r.ok and "ModuleNotFoundError" in r.stderr


@pytest.mark.skipif(IS_ROOT, reason="RLIMIT_NPROC does not bind root")
def test_sandbox_cannot_fork_through_an_unaudited_path() -> None:
    code = ("import sys, importlib, os\ndel sys.modules['_posixsubprocess']\n"
            "p = importlib.import_module('_posixsubprocess')\nr, w = os.pipe()\n"
            "p.fork_exec(['/bin/true'], [b'/bin/true'], True, (), None, None, -1, -1, -1, -1, -1, -1, r, w, True,"
            " False, 0, None, None, None, -1, None)\nprint('forked')")
    r = sbx(code)
    assert not r.ok and "forked" not in r.stdout


def test_sandbox_limits_time_cpu_memory_file_size_and_output() -> None:
    r = sbx("import time\ntime.sleep(5)", timeout_s=0.5)
    assert r.timed_out and not r.ok
    r = sbx("while True:\n    pass", cpu_s=1, timeout_s=10)
    assert not r.ok and not r.timed_out and r.returncode < 0
    r = sbx("x = bytearray(2 * 1024 ** 3)")
    assert not r.ok and "MemoryError" in r.stderr
    r = sbx("open('big', 'wb').write(b'x' * (2 * 1024 * 1024))")
    assert not r.ok and "File too large" in r.stderr
    r = sbx("print('x' * 10000)", max_output_chars=500)
    assert r.ok and r.truncated and len(r.stdout) == 500


def test_sandbox_environment_is_empty() -> None:
    r = sbx("import os\nprint(sorted(k for k in os.environ if k not in ('LC_CTYPE',)))")
    assert r.ok and r.stdout.strip() == "['HOME', 'TMPDIR']"


@pytest.mark.parametrize("kw", [dict(timeout_s=0), dict(cpu_s=0), dict(memory_bytes=1), dict(open_files=1),
                                dict(max_output_chars=1), dict(cpu_s=True)])
def test_sandbox_policy_rejects_out_of_range(kw: dict) -> None:
    with pytest.raises(ValueError):
        SandboxPolicy(**kw)


def test_negative_control_the_same_reads_succeed_without_the_sandbox() -> None:
    """The denial tests are not vacuous: an ordinary interpreter can read these files and import socket."""
    p = subprocess.run([sys.executable, "-I", "-c", "import socket; print(len(open('/etc/passwd').read()) > 0)"],
                       capture_output=True, text=True, timeout=30)
    assert p.returncode == 0 and p.stdout.strip() == "True"


# ==== file inspector ================================================================================================
@pytest.fixture()
def tree(tmp_path: Path) -> Path:
    root = tmp_path / "root"
    (root / "sub").mkdir(parents=True)
    (root / "a.txt").write_text("مرحبا\nhello\n", encoding="utf-8")
    (root / "sub" / "b.txt").write_text("b" * 100, encoding="utf-8")
    (root / "bin.dat").write_bytes(b"\x00\x01\x02")
    (tmp_path / "secret.txt").write_text("secret", encoding="utf-8")
    (root / "out_link").symlink_to(tmp_path / "secret.txt")
    (root / "in_link").symlink_to(root / "a.txt")
    return root


def test_files_read_list_stat_inside_root(tree: Path) -> None:
    fi = FileInspector(tree)
    t = fi.read_text("a.txt")
    assert t.text == "مرحبا\nhello\n" and not t.truncated and t.size == len("مرحبا\nhello\n".encode())
    assert [e["name"] for e in fi.list_dir()] == ["a.txt", "bin.dat", "in_link", "out_link", "sub"]
    types = {e["name"]: e["type"] for e in fi.list_dir()}
    assert types["out_link"] == "outside_root" and types["in_link"] == "file" and types["sub"] == "dir"
    assert fi.stat("sub/b.txt")["size"] == 100 and len(fi.stat("sub/b.txt")["sha256"]) == 64
    assert fi.read_text("in_link").text.startswith("مرحبا")


def test_files_truncation_keeps_whole_file_hash(tree: Path) -> None:
    fi = FileInspector(tree)
    t = fi.read_text("sub/b.txt", max_bytes=10)
    assert t.truncated and t.text == "b" * 10 and t.sha256 == fi.stat("sub/b.txt")["sha256"]


@pytest.mark.parametrize("path,code", [("../secret.txt", "outside_root"), ("sub/../../secret.txt", "outside_root"),
                                       ("out_link", "outside_root"), ("/etc/passwd", "outside_root"),
                                       ("~/x", "outside_root"), ("a\x00b", "bad_path"), ("bin.dat", "binary"),
                                       ("missing.txt", "not_found"), ("sub", "not_found")])
def test_files_refuse(tree: Path, path: str, code: str) -> None:
    with pytest.raises(FileAccessError) as e:
        FileInspector(tree).read_text(path)
    assert e.value.code == code


def test_files_has_no_mutating_operation(tree: Path) -> None:
    names = [n for n in dir(FileInspector(tree)) if not n.startswith("_")]
    assert not [n for n in names if any(w in n for w in ("write", "delete", "remove", "rename", "chmod", "mkdir",
                                                          "move", "copy", "touch", "unlink"))]
    assert sorted(names) == ["list_dir", "max_bytes", "read_text", "rel", "root", "stat"]


def test_files_bad_root_and_limits(tmp_path: Path) -> None:
    with pytest.raises(FileAccessError):
        FileInspector(tmp_path / "nope")
    with pytest.raises(ValueError):
        FileInspector(tmp_path, max_bytes=0)


# ==== audit log =====================================================================================================
def clock():
    t = iter(range(1000))
    return lambda: float(next(t))


def filled(path: Path | None = None) -> AuditLog:
    log = AuditLog(path, clock=clock())
    for i in range(4):
        log.append(tool="calculator", permission="CALCULATE", caller="t", outcome="ok", reason="ok",
                   payload={"expression": f"{i}+1"}, output={"exact": str(i + 1)})
    return log


def test_audit_chain_is_valid_and_deterministic() -> None:
    a, b = filled(), filled()
    assert verify_chain(a.records) == [] and [r.hash for r in a.records] == [r.hash for r in b.records]
    assert a.records[0].prev_hash == au.GENESIS and a.records[1].prev_hash == a.records[0].hash


@pytest.mark.parametrize("tamper", ["edit", "delete", "reorder", "insert", "rehash_one"])
def test_audit_chain_detects_tampering(tamper: str) -> None:
    recs = list(filled().records)
    if tamper == "edit":
        recs[1] = dataclasses.replace(recs[1], outcome="denied")
    elif tamper == "delete":
        del recs[1]
    elif tamper == "reorder":
        recs[1], recs[2] = recs[2], recs[1]
    elif tamper == "insert":
        recs.insert(2, recs[1])
    else:   # edit a record and recompute its own hash: the next record's prev_hash no longer matches
        r = dataclasses.replace(recs[1], reason="forged")
        recs[1] = dataclasses.replace(r, hash=r.compute_hash())
    assert verify_chain(recs) != []


def test_audit_file_round_trip_and_tampered_file_is_refused(tmp_path: Path) -> None:
    p = tmp_path / "audit.jsonl"
    log = filled(p)
    again = AuditLog(p)
    assert [r.hash for r in again.records] == [r.hash for r in log.records]
    lines = p.read_text(encoding="utf-8").splitlines()
    d = json.loads(lines[2])
    d["reason"] = "forged"
    lines[2] = json.dumps(d)
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(ValueError):
        AuditLog(p)


def test_audit_stores_hashes_and_short_previews_not_full_payloads() -> None:
    log = AuditLog(clock=clock())
    rec = log.append(tool="python", permission="EXECUTE_CODE", caller="t", outcome="ok", reason="ok",
                     payload={"code": "x" * 1000}, output={"stdout": "y" * 1000})
    assert len(rec.input_preview) <= au.PREVIEW_CHARS + 1 and len(rec.input_sha256) == 64
    assert "y" * 100 not in json.dumps(dataclasses.asdict(rec))
    with pytest.raises(ValueError):
        log.append(tool="x", permission=None, caller="t", outcome="maybe", reason="", payload={}, output=None)


# ==== registry, permissions, allowlist ==============================================================================
def test_default_registry_grants_nothing_and_audits_the_denial() -> None:
    reg = default_registry()
    r = reg.call("calculator", {"expression": "1+1"})
    assert (r.ok, r.outcome, r.reason) == (False, "denied", "permission_not_granted")
    assert reg.audit.records[-1].outcome == "denied" and reg.audit.records[-1].output_sha256 is None


def test_granted_calculator_returns_exact_and_decimal() -> None:
    reg = default_registry(grants=[Permission.CALCULATE])
    r = reg.call("calculator", {"expression": "1/3", "places": 4})
    assert r.ok and r.output == {"exact": "1/3", "decimal": "0.3333"}
    r = reg.call("calculator", {"expression": "1/0"})
    assert (r.ok, r.outcome, r.reason) == (False, "error", "division_by_zero")
    r = reg.call("calculator", {"expr": "1"})
    assert (r.outcome, r.reason) == ("error", "bad_payload: KeyError")


@pytest.mark.parametrize("name", ["search", "web", "http", "api"])
def test_search_and_external_api_are_blocked_even_with_every_grant(name: str) -> None:
    reg = default_registry(grants=[p for p in Permission if p is not Permission.NETWORK])
    r = reg.call(name, {"q": "anything"})
    assert r.outcome == "denied" and "OD-11" in r.reason and "P6-02a" in r.reason
    assert reg.audit.records[-1].permission == "NETWORK"


def test_network_permission_and_network_tools_cannot_be_registered() -> None:
    with pytest.raises(ValueError, match="OD-11"):
        default_registry(grants=[Permission.NETWORK])
    with pytest.raises(ValueError, match="OD-11"):
        ToolSpec("fetch", Permission.NETWORK, lambda p: None)
    with pytest.raises(ValueError, match="OD-11"):
        ToolSpec("search", Permission.READ_FILES, lambda p: None)


def test_unknown_tool_and_bad_payload_are_denied_and_audited() -> None:
    reg = default_registry(grants=[Permission.CALCULATE])
    assert reg.call("shell", {"cmd": "ls"}).reason == "not_allowlisted"
    assert reg.call("calculator", "1+1").reason.startswith("bad_payload")   # type: ignore[arg-type]
    assert [r.outcome for r in reg.audit.records] == ["denied", "denied"]


def test_python_tool_reports_sandbox_denials_and_timeouts() -> None:
    reg = default_registry(grants=[Permission.EXECUTE_CODE], policy=SandboxPolicy(timeout_s=1))
    ok = reg.call("python", {"code": "print(6 * 7)"})
    assert ok.ok and ok.output["stdout"].strip() == "42"
    net = reg.call("python", {"code": "import socket"})
    assert net.outcome == "error" and net.reason == "execution_failed" and net.output["denied"] == ["import socket"]
    slow = reg.call("python", {"code": "import time\ntime.sleep(5)"})
    assert slow.outcome == "timeout"


def test_file_tools_only_with_a_root_and_stay_inside_it(tmp_path: Path) -> None:
    assert "read_file" not in default_registry().tools
    (tmp_path / "r").mkdir()
    (tmp_path / "r" / "x.txt").write_text("x", encoding="utf-8")
    reg = default_registry(grants=[Permission.READ_FILES], files_root=tmp_path / "r")
    assert reg.call("read_file", {"path": "x.txt"}).output["text"] == "x"
    bad = reg.call("read_file", {"path": "../x.txt"})
    assert (bad.outcome, bad.reason) == ("error", "outside_root")


def test_every_call_is_audited_in_one_valid_chain(tmp_path: Path) -> None:
    reg = default_registry(grants=[Permission.CALCULATE], audit=AuditLog(tmp_path / "a.jsonl", clock=clock()))
    for payload in ({"expression": "2*3"}, {"expression": "x"}, {"q": 1}):
        reg.call("calculator", payload)
    reg.call("search", {"q": "x"})
    reg.call("python", {"code": "print(1)"})
    recs = reg.audit.records
    assert [r.seq for r in recs] == list(range(5)) and verify_chain(recs) == []
    assert [r.outcome for r in recs] == ["ok", "error", "error", "denied", "denied"]
    assert len((tmp_path / "a.jsonl").read_text(encoding="utf-8").splitlines()) == 5


def test_registry_rejects_duplicates_and_bad_grants() -> None:
    t = ToolSpec("calc2", Permission.CALCULATE, lambda p: 1)
    with pytest.raises(ValueError):
        ToolRegistry([t, t])
    with pytest.raises(ValueError):
        ToolRegistry([t], grants=["CALCULATE"])     # type: ignore[list-item]
    with pytest.raises(ValueError):
        ToolSpec("bad name", Permission.CALCULATE, lambda p: 1)


def test_evaluation_sandbox_is_unchanged() -> None:
    """ADR-0008 D2: the evaluation runner and P2 verifier keep their sandbox; switching is a separate Eval decision."""
    from nawa.evaluation.sandbox import run_python
    r = run_python("print(1 + 1)")
    assert r.ok and r.stdout.strip() == "2"
