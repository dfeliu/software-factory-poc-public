"""Immutable event evidence and restrict-only operational controls."""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .contracts import REPOSITORY, content_hash, require_identifier, require_object

SENSITIVE_KEYS = {"token", "password", "secret", "authorization", "cookie", "prompt"}
CONTROL_STORE_MARKER = ".g2-control-store-v1"


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def _assert_non_secret(value: Any, path: str = "event") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in SENSITIVE_KEYS:
                raise ValueError(
                    f"sensitive field is forbidden in evidence: {path}.{key}"
                )
            _assert_non_secret(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _assert_non_secret(item, f"{path}[{index}]")


def atomic_json(path: Path, value: dict[str, Any], *, replace: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not replace:
        raise FileExistsError(f"immutable evidence already exists: {path.name}")
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        if replace:
            os.replace(temporary, path)
        else:
            try:
                os.link(temporary, path)
            except FileExistsError as exc:
                raise FileExistsError(
                    f"immutable evidence already exists: {path.name}"
                ) from exc
            os.unlink(temporary)
        # The observer is the only writer.  Its dedicated evidence group gives
        # the separate executor read-only access to this durable decision.
        os.chmod(path, 0o640)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class EventStore:
    """Store one file per event so a projection can replay it idempotently."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.events = self.root / "events"
        self.controls = self.root / "controls"

    def append(
        self,
        event_type: str,
        payload: Any,
        *,
        event_id: str | None = None,
        occurred_at: str | None = None,
    ) -> dict[str, Any]:
        payload = require_object(payload, label="event payload")
        _assert_non_secret(payload)
        occurred_at = occurred_at or now()
        body = {
            "schema_version": 1,
            "event_type": event_type,
            "occurred_at": occurred_at,
            "payload": payload,
        }
        event_id = event_id or content_hash(body)
        event = {**body, "event_id": event_id}
        atomic_json(self.events / f"{event_id}.json", event, replace=False)
        return event

    def iter_events(self) -> Iterable[dict[str, Any]]:
        if not self.events.is_dir():
            return
        values = []
        for path in self.events.glob("*.json"):
            value = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(value, dict):
                values.append(value)
        yield from sorted(
            values,
            key=lambda item: (item.get("occurred_at", ""), item.get("event_id", "")),
        )

    def set_pause(
        self, *, scope: str, repository: str | None, reason_code: str, actor: str
    ) -> dict[str, Any]:
        if scope not in {"global", "repository"}:
            raise ValueError("pause scope must be global or repository")
        if scope == "repository" and not repository:
            raise ValueError("repository pause requires repository")
        if scope == "global" and repository is not None:
            raise ValueError("global pause cannot name a repository")
        if repository is not None and not REPOSITORY.fullmatch(repository):
            raise ValueError("pause repository must be owner/name")
        require_identifier(reason_code, label="reason_code")
        require_identifier(actor, label="actor")
        value = {
            "schema_version": 1,
            "paused": True,
            "scope": scope,
            "repository": repository,
            "reason_code": reason_code,
            "actor": actor,
            "updated_at": now(),
        }
        name = (
            "global.json"
            if scope == "global"
            else f"repository-{content_hash(repository)[:16]}.json"
        )
        atomic_json(self.controls / name, value, replace=True)
        self.append("control_paused", value)
        return value

    def paused(self, repository: str) -> bool:
        if (self.controls / "global.json").is_file():
            return True
        name = f"repository-{content_hash(repository)[:16]}.json"
        return (self.controls / name).is_file()


def require_control_store(root: Path) -> EventStore:
    """Open one pre-provisioned operator control store or fail closed."""
    root = Path(root)
    controls = root / "controls"
    events = root / "events"
    marker = root / CONTROL_STORE_MARKER
    required_directories = (
        (root, "root directory"),
        (controls, "controls directory"),
        (events, "events directory"),
    )
    for path, kind in required_directories:
        if path.is_symlink() or not path.is_dir():
            raise RuntimeError(f"G2 control store {kind} is not provisioned: {path}")
    if marker.is_symlink() or not marker.is_file():
        raise RuntimeError(f"G2 control store marker is not provisioned: {marker}")
    for path in (root, controls, events):
        if not os.access(path, os.R_OK | os.X_OK):
            raise RuntimeError(f"G2 control store is not readable: {path}")
    if not os.access(marker, os.R_OK):
        raise RuntimeError(f"G2 control store marker is not readable: {marker}")
    return EventStore(root)
