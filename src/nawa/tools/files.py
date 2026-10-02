"""Read-only file inspector (ROADMAP P6-02, ADR-0008).

Reads files under one root directory and nothing else. There is no write, delete, rename or chmod operation at all.
Paths are resolved (``..`` and symlinks) before the check, so a symlink that points outside the root is refused.
Absolute paths, NUL bytes, binary files (a NUL byte in the first 8 KiB) and files above ``max_bytes`` are refused or
truncated with an explicit flag.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

DEFAULT_MAX_BYTES = 64 * 1024
BINARY_SNIFF = 8192


class FileAccessError(PermissionError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


@dataclass(frozen=True)
class FileText:
    path: str
    text: str
    size: int
    truncated: bool
    sha256: str          # of the whole file, not only the returned part


class FileInspector:
    def __init__(self, root: Path | str, max_bytes: int = DEFAULT_MAX_BYTES) -> None:
        r = Path(root).resolve()
        if not r.is_dir():
            raise FileAccessError("bad_root", f"{root} is not a directory")
        if not isinstance(max_bytes, int) or isinstance(max_bytes, bool) or not 1 <= max_bytes <= 16 * 1024 * 1024:
            raise ValueError("max_bytes must be an int in 1..16 MiB")
        self.root, self.max_bytes = r, max_bytes

    def _resolve(self, rel: str) -> Path:
        if not isinstance(rel, str) or "\x00" in rel:
            raise FileAccessError("bad_path", "path must be a string without NUL bytes")
        if Path(rel).is_absolute() or rel.startswith("~"):
            raise FileAccessError("outside_root", "absolute paths are not allowed")
        p = (self.root / rel).resolve()
        if p != self.root and self.root not in p.parents:
            raise FileAccessError("outside_root", f"{rel!r} resolves outside the root")
        return p

    def rel(self, p: Path) -> str:
        return "." if p == self.root else p.relative_to(self.root).as_posix()

    def list_dir(self, rel: str = ".") -> list[dict]:
        p = self._resolve(rel)
        if not p.is_dir():
            raise FileAccessError("not_a_directory", f"{rel!r} is not a directory")
        out = []
        for child in sorted(p.iterdir(), key=lambda c: c.name):
            try:
                target = self._resolve(child.relative_to(self.root).as_posix())
            except FileAccessError:
                out.append({"name": child.name, "type": "outside_root"})
                continue
            out.append({"name": child.name, "type": "dir" if target.is_dir() else "file",
                        "size": None if target.is_dir() else target.stat().st_size})
        return out

    def stat(self, rel: str) -> dict:
        p = self._resolve(rel)
        if not p.exists():
            raise FileAccessError("not_found", f"{rel!r} does not exist")
        if p.is_dir():
            return {"path": self.rel(p), "type": "dir"}
        return {"path": self.rel(p), "type": "file", "size": p.stat().st_size, "sha256": _sha256(p)}

    def read_text(self, rel: str, max_bytes: int | None = None, encoding: str = "utf-8") -> FileText:
        p = self._resolve(rel)
        if not p.is_file():
            raise FileAccessError("not_found", f"{rel!r} is not a file")
        limit = self.max_bytes if max_bytes is None else min(max_bytes, self.max_bytes)
        size = p.stat().st_size
        with p.open("rb") as fh:
            head = fh.read(min(BINARY_SNIFF, limit + 1))
            if b"\x00" in head[:BINARY_SNIFF]:
                raise FileAccessError("binary", f"{rel!r} looks binary")
            data = head + fh.read(max(0, limit + 1 - len(head)))
        truncated = len(data) > limit
        text = data[:limit].decode(encoding, errors="replace")
        return FileText(self.rel(p), text, size, truncated, _sha256(p))


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()
