"""Filesystem interlock shared by the G2 operator pause and merge executor."""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

CONTROL_INTERLOCK = "merge.interlock"


def control_interlock(root: Path) -> Path:
    """Derive the only valid interlock from the shared controls root."""
    return Path(root) / CONTROL_INTERLOCK


def _fcntl():
    if os.name != "posix":
        raise RuntimeError("G2 operational interlock requires a POSIX host")
    import fcntl

    return fcntl


def _validated_lock(path: Path) -> Path:
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise RuntimeError(f"G2 operational interlock is not provisioned: {path}")
    return path


def require_interlock(path: Path) -> Path:
    """Validate the operator-owned lock before any provider access."""
    return _validated_lock(path)


@contextmanager
def shared_interlock(path: Path) -> Iterator[None]:
    """Block a completed pause from racing a merge POST."""
    fcntl = _fcntl()
    with _validated_lock(path).open("rb") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_SH)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@contextmanager
def exclusive_interlock(path: Path) -> Iterator[None]:
    """Wait for in-flight merge POSTs before materializing an operator pause."""
    fcntl = _fcntl()
    with _validated_lock(path).open("r+b") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
