#!/usr/bin/env python3

"""Build and reconcile a fail-closed public repository projection."""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
from typing import Any, Iterable


SCHEMA_VERSION = 1
MAX_OBSERVATIONS = 100
TEXT_EXTENSIONS = {
    "", ".cfg", ".conf", ".css", ".csv", ".dockerignore", ".example",
    ".gitignore", ".gitkeep", ".html", ".ini", ".jinja", ".jinja2",
    ".js", ".json", ".lock", ".md", ".mako", ".py", ".python-version",
    ".sh", ".sql", ".toml", ".ts", ".txt", ".yaml", ".yml",
}

_WINDOWS_USERS_PREFIX = b"\\" + b"Users" + b"\\"
_POSIX_HOME_PREFIX = b"/" + b"home" + b"/"
_MAC_USERS_PREFIX = b"/" + b"Users" + b"/"
_SRV_PREFIX = b"/" + b"srv" + b"/"
_OPT_PREFIX = b"/" + b"opt" + b"/"
_INTERNAL_SUFFIXES = b"(?:" + b"local|lan|internal|home\\.arpa" + b")"

CHECKS = {
    "private_ipv4": re.compile(
        rb"(?<![0-9])(?:10(?:\.[0-9]{1,3}){3}|192\.168(?:\.[0-9]{1,3}){2}|"
        rb"172\.(?:1[6-9]|2[0-9]|3[01])(?:\.[0-9]{1,3}){2})(?![0-9])"
    ),
    "private_key": re.compile(
        rb"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"
    ),
    "credential_url": re.compile(rb"https?://[^/\s:@]+:[^/\s@]+@"),
    "token_prefix": re.compile(
        rb"(?:github_pat_[A-Za-z0-9_]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|"
        rb"glpat-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}|xox[baprs]-[A-Za-z0-9-]{10,})"
    ),
    "private_path": re.compile(
        rb"(?:[A-Za-z]:" + re.escape(_WINDOWS_USERS_PREFIX) + rb"[^\\\r\n]+|"
        + re.escape(_POSIX_HOME_PREFIX) + rb"[^/\s]+|"
        + re.escape(_MAC_USERS_PREFIX) + rb"[^/\s]+)"
    ),
    "operational_path": re.compile(
        rb"(?:" + re.escape(_SRV_PREFIX) + rb"|" + re.escape(_OPT_PREFIX) + rb")"
    ),
    "internal_hostname": re.compile(
        rb"(?i)(?<![a-z0-9.-])(?:[a-z0-9-]+\.)+"
        + _INTERNAL_SUFFIXES + rb"(?::[0-9]+)?"
    ),
    "email_address": re.compile(
        rb"(?i)[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
        rb"(?!example\.(?:com|org|net)\b)"
        rb"(?![a-z0-9.-]+\.(?:test|invalid|example|localhost)\b)"
        rb"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
        rb"(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+"
    ),
}


class ProjectionError(RuntimeError):
    """An input or policy condition blocks the complete projection."""


def _object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProjectionError(f"cannot read JSON object: {path}") from exc
    if not isinstance(value, dict):
        raise ProjectionError(f"expected JSON object: {path}")
    return value


def load_policy(path: Path) -> dict[str, Any]:
    policy = _object(path)
    if policy.get("schema_version") != SCHEMA_VERSION:
        raise ProjectionError("unsupported policy schema_version")
    entries = policy.get("entries")
    checks = policy.get("checks")
    blocked_globs = policy.get("blocked_globs")
    if not isinstance(entries, list) or not entries:
        raise ProjectionError("policy entries must be a non-empty list")
    if not isinstance(checks, list) or not checks:
        raise ProjectionError("policy checks must be a non-empty list")
    if not isinstance(blocked_globs, list):
        raise ProjectionError("policy blocked_globs must be a list")
    unknown = sorted(set(checks) - set(CHECKS))
    if unknown:
        raise ProjectionError(f"unknown checks: {', '.join(unknown)}")
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"source", "target"}:
            raise ProjectionError("each entry must contain only source and target")
        _safe_relative(entry["source"])
        _safe_relative(entry["target"])
    for pattern in blocked_globs:
        if not isinstance(pattern, str) or not pattern:
            raise ProjectionError("blocked_globs must contain non-empty strings")
    return policy


def _safe_relative(value: Any) -> PurePosixPath:
    if not isinstance(value, str) or not value:
        raise ProjectionError("projection paths must be non-empty strings")
    path = PurePosixPath(value.replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts or "." in path.parts:
        raise ProjectionError(f"unsafe relative path: {value}")
    return path


def _within(root: Path, path: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except (OSError, ValueError):
        return False
    return True


def _git(source_root: Path, *arguments: str) -> bytes:
    try:
        result = subprocess.run(
            ["git", "-C", str(source_root), *arguments],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ProjectionError(f"local Git validation failed: {' '.join(arguments)}") from exc
    return result.stdout


def validate_source_checkout(source_root: Path, source_sha: str) -> None:
    """Require a clean checkout at exactly the declared source commit."""
    head = _git(source_root, "rev-parse", "HEAD").decode("ascii").strip()
    if head != source_sha:
        raise ProjectionError("source SHA does not match checkout HEAD")
    if _git(source_root, "status", "--porcelain", "--untracked-files=all"):
        raise ProjectionError("source checkout is not clean")


def _versionable_files(source_root: Path) -> set[PurePosixPath] | None:
    """List tracked and non-ignored new files, or None outside a Git checkout."""
    try:
        output = _git(source_root, "ls-files", "--cached", "--others", "--exclude-standard", "-z")
    except ProjectionError:
        return None
    return {
        PurePosixPath(item.decode("utf-8"))
        for item in output.split(b"\0")
        if item
    }


def _files_for_entry(
    source_root: Path,
    entry: dict[str, str],
    versionable: set[PurePosixPath] | None,
) -> Iterable[tuple[Path, PurePosixPath]]:
    source_rel = _safe_relative(entry["source"])
    target_rel = _safe_relative(entry["target"])
    source = source_root.joinpath(*source_rel.parts)
    if not source.exists():
        raise ProjectionError(f"allow-listed source does not exist: {source_rel}")
    if source.is_symlink():
        raise ProjectionError(f"symlink is not publishable: {source_rel}")
    if source.is_file():
        if versionable is not None and source_rel not in versionable:
            raise ProjectionError(f"allow-listed source is ignored by Git: {source_rel}")
        yield source, target_rel
        return
    if not source.is_dir():
        raise ProjectionError(f"unsupported source type: {source_rel}")
    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source)
        display = source_rel.joinpath(*relative.parts)
        if path.is_symlink():
            raise ProjectionError(f"symlink is not publishable: {display}")
        if path.is_file() and (versionable is None or display in versionable):
            yield path, target_rel.joinpath(*relative.parts)


def _glob_match(path: PurePosixPath, patterns: list[str]) -> bool:
    value = path.as_posix()
    name = path.name
    return any(fnmatch.fnmatchcase(value, pattern) or fnmatch.fnmatchcase(name, pattern) for pattern in patterns)


def _line_number(data: bytes, start: int) -> int:
    return data.count(b"\n", 0, start) + 1


def _inspect_candidate(
    files: dict[PurePosixPath, bytes],
    findings: list[dict[str, Any]],
    target: PurePosixPath,
    data: bytes,
    suffix: str,
    policy: dict[str, Any],
) -> None:
    if target in files:
        raise ProjectionError(f"duplicate public target: {target}")
    if _glob_match(target, policy["blocked_globs"]):
        findings.append({"check": "blocked_path", "path": target.as_posix()})
        return
    if b"\x00" in data or suffix.lower() not in TEXT_EXTENSIONS:
        findings.append({"check": "binary_or_unknown_type", "path": target.as_posix()})
        return
    for check_name in policy["checks"]:
        match = CHECKS[check_name].search(data)
        if match:
            findings.append({
                "check": check_name,
                "path": target.as_posix(),
                "line": _line_number(data, match.start()),
            })
    files[target] = data


def collect_projection(
    source_root: Path,
    policy: dict[str, Any],
) -> tuple[dict[PurePosixPath, bytes], list[dict[str, Any]]]:
    """Return the exact public tree and sanitized findings; any finding blocks it."""
    source_root = source_root.resolve()
    if not source_root.is_dir():
        raise ProjectionError("source must be a directory")
    files: dict[PurePosixPath, bytes] = {}
    findings: list[dict[str, Any]] = []
    candidate_count = 0
    versionable = _versionable_files(source_root)
    for entry in policy["entries"]:
        for source, target in _files_for_entry(source_root, entry, versionable):
            candidate_count += 1
            if not _within(source_root, source):
                raise ProjectionError(f"source escapes repository: {source}")
            data = source.read_bytes()
            _inspect_candidate(files, findings, target, data, source.suffix, policy)
    if candidate_count == 0:
        raise ProjectionError("policy selected no files")
    return files, findings


def _committed_tree(source_root: Path, source_sha: str) -> dict[PurePosixPath, tuple[str, str, str]]:
    tree: dict[PurePosixPath, tuple[str, str, str]] = {}
    output = _git(source_root, "ls-tree", "-r", "-z", "--full-tree", source_sha)
    for record in output.split(b"\0"):
        if not record:
            continue
        try:
            metadata, raw_path = record.split(b"\t", 1)
            mode, object_type, object_id = metadata.decode("ascii").split()
            path = _safe_relative(raw_path.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise ProjectionError("malformed or non-UTF-8 Git tree entry") from exc
        tree[path] = (mode, object_type, object_id)
    return tree


def collect_committed_projection(
    source_root: Path,
    source_sha: str,
    policy: dict[str, Any],
) -> tuple[dict[PurePosixPath, bytes], list[dict[str, Any]]]:
    """Build the public tree from immutable Git blobs, never checkout bytes."""
    tree = _committed_tree(source_root, source_sha)
    files: dict[PurePosixPath, bytes] = {}
    findings: list[dict[str, Any]] = []
    candidate_count = 0
    for entry in policy["entries"]:
        source = _safe_relative(entry["source"])
        target = _safe_relative(entry["target"])
        prefix = source.as_posix() + "/"
        selected = [
            path for path in tree
            if path == source or path.as_posix().startswith(prefix)
        ]
        if not selected:
            raise ProjectionError(f"allow-listed source does not exist in commit: {source}")
        for path in sorted(selected, key=PurePosixPath.as_posix):
            candidate_count += 1
            mode, object_type, object_id = tree[path]
            if mode == "120000":
                raise ProjectionError(f"symlink is not publishable: {path}")
            if object_type != "blob" or mode not in {"100644", "100755"}:
                raise ProjectionError(f"unsupported Git tree entry: {path}")
            relative = PurePosixPath() if path == source else path.relative_to(source)
            public_path = target if not relative.parts else target.joinpath(*relative.parts)
            data = _git(source_root, "cat-file", "blob", object_id)
            _inspect_candidate(files, findings, public_path, data, path.suffix, policy)
    if candidate_count == 0:
        raise ProjectionError("policy selected no files")
    return files, findings


def tree_digest(files: dict[PurePosixPath, bytes]) -> str:
    digest = hashlib.sha256()
    for path, data in sorted(files.items(), key=lambda item: item[0].as_posix()):
        encoded = path.as_posix().encode("utf-8")
        digest.update(len(encoded).to_bytes(4, "big"))
        digest.update(encoded)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest()


def write_projection(output: Path, files: dict[PurePosixPath, bytes]) -> None:
    """Create a new output tree; existing paths are never replaced or deleted."""
    if output.exists():
        raise ProjectionError(f"output already exists: {output}")
    output.mkdir(parents=True)
    for relative, data in sorted(files.items(), key=lambda item: item[0].as_posix()):
        target = output.joinpath(*relative.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)


def read_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schema_version": SCHEMA_VERSION, "observations": []}
    state = _object(path)
    if state.get("schema_version") != SCHEMA_VERSION or not isinstance(state.get("observations"), list):
        raise ProjectionError("invalid reconciliation state")
    return state


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def observe(state_path: Path, source_sha: str, public_tree: str) -> tuple[dict[str, Any], str]:
    state = read_state(state_path)
    last = state.get("last_publication")
    action = "no_change" if isinstance(last, dict) and last.get("public_tree_sha256") == public_tree else "publish"
    observations = [
        item for item in state["observations"]
        if isinstance(item, dict) and item.get("source_sha") != source_sha
    ]
    observations.append({"source_sha": source_sha, "public_tree_sha256": public_tree})
    state["observations"] = observations[-MAX_OBSERVATIONS:]
    state["last_observation"] = state["observations"][-1]
    atomic_write_json(state_path, state)
    return state, action


def confirm_publication(state_path: Path, source_sha: str, public_tree: str, public_commit: str) -> dict[str, Any]:
    state = read_state(state_path)
    expected = {"source_sha": source_sha, "public_tree_sha256": public_tree}
    if expected not in state["observations"]:
        raise ProjectionError("publication does not match an observed projection")
    state["last_publication"] = {**expected, "public_commit": public_commit}
    atomic_write_json(state_path, state)
    return state


def _source_sha(value: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{40}", value):
        raise argparse.ArgumentTypeError("source SHA must contain 40 lowercase hexadecimal characters")
    return value


def _digest(value: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{64}", value):
        raise argparse.ArgumentTypeError("tree digest must contain 64 lowercase hexadecimal characters")
    return value


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build", help="scan and build a new public tree")
    build.add_argument("--source", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)
    build.add_argument("--policy", type=Path, required=True)
    build.add_argument("--source-sha", type=_source_sha, required=True)
    build.add_argument("--state", type=Path)
    confirm = commands.add_parser("confirm", help="record a successful external publication")
    confirm.add_argument("--state", type=Path, required=True)
    confirm.add_argument("--source-sha", type=_source_sha, required=True)
    confirm.add_argument("--tree-digest", type=_digest, required=True)
    confirm.add_argument("--public-commit", type=_source_sha, required=True)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "confirm":
            confirm_publication(args.state, args.source_sha, args.tree_digest, args.public_commit)
            print(json.dumps({
                "status": "confirmed",
                "source_sha": args.source_sha,
                "public_tree_sha256": args.tree_digest,
            }, sort_keys=True))
            return 0
        source = args.source.resolve()
        output = args.output.resolve()
        if _within(source, output):
            raise ProjectionError("output must be outside the source checkout")
        if args.state is not None and _within(source, args.state.resolve()):
            raise ProjectionError("reconciliation state must be outside the source checkout")
        validate_source_checkout(source, args.source_sha)
        policy = load_policy(args.policy)
        files, findings = collect_committed_projection(source, args.source_sha, policy)
        digest = tree_digest(files)
        if findings:
            print(json.dumps({
                "status": "blocked",
                "source_sha": args.source_sha,
                "findings": findings,
            }, sort_keys=True))
            return 2
        write_projection(output, files)
        action = "publish"
        if args.state is not None:
            _, action = observe(args.state, args.source_sha, digest)
        print(json.dumps({
            "status": "ready", "action": action, "source_sha": args.source_sha,
            "public_tree_sha256": digest, "file_count": len(files),
        }, sort_keys=True))
        return 0
    except ProjectionError as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)}, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
