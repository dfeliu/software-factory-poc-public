"""Small provider-neutral boundary between orchestration and execution."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True)
class RunRequest:
    """Immutable inputs shared by Forgejo Native F and Cloudflare D1."""

    run_id: str
    scenario: str
    project: str
    base_commit: str
    governance_level: str = "G0"
    max_attempts: int = 3

    def __post_init__(self) -> None:
        if not _ID_RE.fullmatch(self.run_id):
            raise ValueError("run_id must be a safe 1-128 character identifier")
        if not _ID_RE.fullmatch(self.scenario):
            raise ValueError("scenario must be a safe identifier")
        if not _ID_RE.fullmatch(self.project):
            raise ValueError("project must be a safe identifier")
        if not _SHA_RE.fullmatch(self.base_commit):
            raise ValueError("base_commit must be a lowercase 40-character SHA")
        if self.governance_level != "G0":
            raise ValueError(
                "the local D1 prototype is restricted to active G0 governance"
            )
        if not 1 <= self.max_attempts <= 3:
            raise ValueError("max_attempts must be between 1 and 3")


@dataclass(frozen=True)
class RunnerResult:
    """Sanitized result returned at the private-runner boundary."""

    success: bool
    recoverable: bool = False
    external_effect_ambiguous: bool = False
    failure_category: str | None = None
    tests_passed: bool | str = "N/A"
    lint_passed: bool | str = "N/A"
    dependency_audit_passed: bool | str = "N/A"
    image_scanner_passed: bool | str = "N/A"
    image_security_gate_passed: bool | str = "N/A"
    security_passed: bool | str = "N/A"

    def __post_init__(self) -> None:
        if self.success and (
            self.recoverable or self.external_effect_ambiguous or self.failure_category
        ):
            raise ValueError("a successful runner result cannot carry failure state")
        if self.external_effect_ambiguous and self.recoverable:
            raise ValueError(
                "an ambiguous external effect must never be retried automatically"
            )
        if not self.success and not self.failure_category:
            raise ValueError(
                "an unsuccessful runner result needs a safe failure category"
            )


class RunnerPort(Protocol):
    """Execution plane kept outside the orchestration implementation."""

    def execute(
        self, request: RunRequest, *, attempt: int, idempotency_key: str
    ) -> RunnerResult: ...


@dataclass(frozen=True)
class WorkflowOutcome:
    run_id: str
    phase: str
    attempts: int
    idempotency_key: str
    run_record: dict[str, object]
    replayed: bool = False
