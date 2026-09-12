"""Immutable, explicitly addressed G2 dispatch manifests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .contracts import REPOSITORY, require_identifier, require_keys, require_object, require_sha, utc_timestamp
from .events import atomic_json


REQUIRED = {
    "schema_version",
    "dispatch_id",
    "change_id",
    "repository",
    "pr_number",
    "head_sha",
    "policy_source_commit",
    "policy_id",
    "policy_revision",
    "policy_sha256",
    "enforcement_mode",
    "requested_at",
}


def validate_dispatch(value: Any) -> dict[str, Any]:
    """Validate the complete, allow-listed dispatch contract."""
    value = require_object(value, label="dispatch")
    require_keys(value, required=REQUIRED, optional={"review_head_sha"}, label="dispatch")
    if value["schema_version"] != 2:
        raise ValueError("unsupported dispatch schema_version")
    require_identifier(value["dispatch_id"], label="dispatch_id")
    require_identifier(value["change_id"], label="change_id")
    if not isinstance(value["repository"], str) or not REPOSITORY.fullmatch(value["repository"]):
        raise ValueError("dispatch repository must be owner/name")
    if type(value["pr_number"]) is not int or value["pr_number"] <= 0:
        raise ValueError("dispatch pr_number must be positive")
    require_sha(value["head_sha"], label="dispatch head_sha")
    if "review_head_sha" in value:
        require_sha(value["review_head_sha"], label="dispatch review_head_sha")
    require_sha(value["policy_source_commit"], label="dispatch policy_source_commit")
    require_identifier(value["policy_id"], label="dispatch policy_id")
    if type(value["policy_revision"]) is not int or value["policy_revision"] <= 0:
        raise ValueError("dispatch policy_revision must be positive")
    policy_sha256 = value["policy_sha256"]
    if (
        not isinstance(policy_sha256, str)
        or len(policy_sha256) != 64
        or any(character not in "0123456789abcdef" for character in policy_sha256)
    ):
        raise ValueError("dispatch policy_sha256 must be a lowercase SHA-256 value")
    if value["enforcement_mode"] not in {"shadow", "enforced"}:
        raise ValueError("dispatch enforcement_mode must be shadow or enforced")
    utc_timestamp(value["requested_at"])
    return value


def dispatch_path(root: Path, change_id: str, dispatch_id: str) -> Path:
    """Resolve a safe, explicit manifest path without directory traversal."""
    return (
        Path(root)
        / require_identifier(change_id, label="change_id")
        / f"{require_identifier(dispatch_id, label='dispatch_id')}.json"
    )


def write_dispatch(root: Path, value: Any) -> Path:
    """Append one immutable dispatch; callers own directory permissions."""
    dispatch = validate_dispatch(value)
    path = dispatch_path(root, dispatch["change_id"], dispatch["dispatch_id"])
    atomic_json(path, dispatch, replace=False)
    return path


def load_dispatch(root: Path, change_id: str, dispatch_id: str) -> dict[str, Any]:
    """Load one manifest and reject an identity/path mismatch."""
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise RuntimeError("dispatch root is not provisioned")
    resolved_root = root.resolve(strict=True)
    change_directory = root / require_identifier(change_id, label="change_id")
    if change_directory.is_symlink() or not change_directory.is_dir():
        raise RuntimeError("dispatch change directory is not provisioned")
    resolved_change = change_directory.resolve(strict=True)
    if resolved_change.parent != resolved_root:
        raise RuntimeError("dispatch change directory escapes the dispatch root")
    path = dispatch_path(root, change_id, dispatch_id)
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("dispatch manifest is unavailable")
    resolved_path = path.resolve(strict=True)
    if resolved_path.parent != resolved_change:
        raise RuntimeError("dispatch manifest escapes its change directory")
    try:
        value = json.loads(resolved_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("dispatch manifest is unavailable") from exc
    dispatch = validate_dispatch(value)
    if dispatch["change_id"] != change_id or dispatch["dispatch_id"] != dispatch_id:
        raise RuntimeError("dispatch manifest identity does not match its path")
    return dispatch
