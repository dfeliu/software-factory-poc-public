"""Strict, dependency-free validation for G2 governance documents."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any

IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
SHA = re.compile(r"^[0-9a-f]{40}([0-9a-f]{24})?$")
REPOSITORY = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}/[A-Za-z0-9][A-Za-z0-9._-]{0,99}$"
)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def content_hash(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def candidate_id(base_sha: str, patch: str) -> str:
    """Return the immutable identity of the exact local candidate patch."""
    require_sha(base_sha, label="base_sha")
    if not isinstance(patch, str):
        raise ValueError("patch must be UTF-8 text")
    return hashlib.sha256(base_sha.encode("ascii") + patch.encode("utf-8")).hexdigest()


def patch_sha256(patch: str) -> str:
    if not isinstance(patch, str):
        raise ValueError("patch must be UTF-8 text")
    return hashlib.sha256(patch.encode("utf-8")).hexdigest()


def utc_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValueError("timestamp must be an ISO-8601 value") from exc
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include a timezone")
    return parsed.astimezone(timezone.utc)


def require_object(value: Any, *, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def require_keys(
    value: dict[str, Any], *, required: set[str], optional: set[str], label: str
) -> None:
    missing = required - value.keys()
    unknown = value.keys() - required - optional
    if missing:
        raise ValueError(f"{label} missing keys: {sorted(missing)}")
    if unknown:
        raise ValueError(f"{label} has unknown keys: {sorted(unknown)}")


def require_identifier(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise ValueError(f"{label} is not a valid identifier")
    return value


def require_sha(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not SHA.fullmatch(value):
        raise ValueError(f"{label} must be a lowercase Git SHA")
    return value


def validate_objective(value: Any) -> dict[str, Any]:
    value = require_object(value, label="objective")
    required = {
        "schema_version",
        "change_id",
        "repository",
        "base_sha",
        "goal",
        "acceptance_criteria",
        "allowed_paths",
        "budgets",
        "risk_profile",
    }
    require_keys(value, required=required, optional=set(), label="objective")
    if value["schema_version"] != 1:
        raise ValueError("unsupported objective schema_version")
    require_identifier(value["change_id"], label="change_id")
    require_sha(value["base_sha"], label="base_sha")
    if not isinstance(value["repository"], str) or not REPOSITORY.fullmatch(
        value["repository"]
    ):
        raise ValueError("repository must be owner/name")
    if not isinstance(value["goal"], str) or not value["goal"].strip():
        raise ValueError("goal must be non-empty")
    for key in ("acceptance_criteria", "allowed_paths"):
        if (
            not isinstance(value[key], list)
            or not value[key]
            or not all(isinstance(item, str) and item for item in value[key])
        ):
            raise ValueError(f"{key} must be a non-empty string list")
    budgets = require_object(value["budgets"], label="budgets")
    require_keys(
        budgets,
        required={"max_attempts", "max_elapsed_seconds"},
        optional=set(),
        label="budgets",
    )
    if (
        type(budgets["max_attempts"]) is not int
        or not 1 <= budgets["max_attempts"] <= 10
    ):
        raise ValueError("max_attempts must be between 1 and 10")
    if (
        type(budgets["max_elapsed_seconds"]) is not int
        or budgets["max_elapsed_seconds"] <= 0
    ):
        raise ValueError("max_elapsed_seconds must be positive")
    require_identifier(value["risk_profile"], label="risk_profile")
    return value


def validate_reviewer_report(value: Any) -> dict[str, Any]:
    value = require_object(value, label="reviewer_report")
    required = {
        "schema_version",
        "change_id",
        "attempt",
        "head_sha",
        "objective_hash",
        "model",
        "prompt_version",
        "result",
        "findings",
        "evidence_refs",
        "reviewed_at",
    }
    if value.get("schema_version") == 2:
        required |= {"candidate_id", "candidate_binding_ref"}
    require_keys(value, required=required, optional=set(), label="reviewer_report")
    if value["schema_version"] not in {1, 2}:
        raise ValueError("unsupported reviewer schema_version")
    require_identifier(value["change_id"], label="change_id")
    require_sha(value["head_sha"], label="head_sha")
    require_sha(value["objective_hash"], label="objective_hash")
    if type(value["attempt"]) is not int or value["attempt"] < 1:
        raise ValueError("attempt must be positive")
    if value["result"] not in {"pass", "needs_human", "fail"}:
        raise ValueError("invalid reviewer result")
    if not isinstance(value["findings"], list) or not isinstance(
        value["evidence_refs"], list
    ):
        raise ValueError("reviewer findings and evidence_refs must be lists")
    if not all(
        isinstance(reference, str) and 0 < len(reference) <= 256
        for reference in value["evidence_refs"]
    ):
        raise ValueError("reviewer evidence_refs must be bounded strings")
    for finding in value["findings"]:
        finding = require_object(finding, label="reviewer finding")
        require_keys(
            finding,
            required={"code", "severity", "path", "evidence_ref"},
            optional=set(),
            label="reviewer finding",
        )
        require_identifier(finding["code"], label="reviewer finding code")
        if finding["severity"] not in {"low", "medium", "high"}:
            raise ValueError("reviewer finding severity is invalid")
        if finding["path"] is not None and (
            not isinstance(finding["path"], str)
            or not finding["path"]
            or len(finding["path"]) > 256
        ):
            raise ValueError("reviewer finding path is invalid")
        if (
            not isinstance(finding["evidence_ref"], str)
            or not finding["evidence_ref"]
            or len(finding["evidence_ref"]) > 256
        ):
            raise ValueError("reviewer finding evidence_ref is invalid")
    for key in ("model", "prompt_version"):
        require_identifier(value[key], label=key)
    if value["schema_version"] == 2:
        _require_digest(value["candidate_id"], label="candidate_id")
        require_identifier(value["candidate_binding_ref"], label="candidate_binding_ref")
    utc_timestamp(value["reviewed_at"])
    return value


def _require_digest(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")
    return value


def validate_builder_result(value: Any) -> dict[str, Any]:
    value = require_object(value, label="builder_result")
    require_keys(
        value,
        required={"schema_version", "status", "summary", "reason_code"},
        optional=set(),
        label="builder_result",
    )
    if value["schema_version"] != 1:
        raise ValueError("unsupported builder result schema_version")
    if value["status"] not in {"candidate_ready", "needs_human", "failed"}:
        raise ValueError("invalid builder result status")
    if not isinstance(value["summary"], str) or not value["summary"].strip():
        raise ValueError("builder result summary must be non-empty")
    if value["status"] == "candidate_ready":
        if value["reason_code"] is not None:
            raise ValueError("candidate_ready cannot include a reason_code")
    else:
        require_identifier(value["reason_code"], label="reason_code")
    return value


def validate_candidate_review(value: Any) -> dict[str, Any]:
    value = require_object(value, label="candidate_review")
    require_keys(
        value,
        required={
            "schema_version", "change_id", "attempt", "objective_hash", "candidate_id",
            "model", "prompt_version", "result", "findings", "evidence_refs", "reviewed_at",
        },
        optional=set(),
        label="candidate_review",
    )
    if value["schema_version"] != 1:
        raise ValueError("unsupported candidate review schema_version")
    require_identifier(value["change_id"], label="change_id")
    if type(value["attempt"]) is not int or value["attempt"] < 1:
        raise ValueError("attempt must be positive")
    require_sha(value["objective_hash"], label="objective_hash")
    _require_digest(value["candidate_id"], label="candidate_id")
    if value["result"] not in {"pass", "needs_human", "fail"}:
        raise ValueError("invalid candidate review result")
    if not isinstance(value["findings"], list) or not isinstance(value["evidence_refs"], list):
        raise ValueError("candidate review findings and evidence_refs must be lists")
    if not all(isinstance(ref, str) and 0 < len(ref) <= 256 for ref in value["evidence_refs"]):
        raise ValueError("candidate review evidence_refs must be bounded strings")
    _validate_findings(value["findings"], label="candidate review")
    for key in ("model", "prompt_version"):
        require_identifier(value[key], label=key)
    utc_timestamp(value["reviewed_at"])
    return value


def validate_validation_result(value: Any) -> dict[str, Any]:
    value = require_object(value, label="validation_result")
    require_keys(
        value,
        required={"schema_version", "change_id", "attempt", "candidate_id", "result", "evidence_refs", "validated_at"},
        optional=set(),
        label="validation_result",
    )
    if value["schema_version"] != 1:
        raise ValueError("unsupported validation result schema_version")
    require_identifier(value["change_id"], label="change_id")
    if type(value["attempt"]) is not int or value["attempt"] < 1:
        raise ValueError("attempt must be positive")
    _require_digest(value["candidate_id"], label="candidate_id")
    if value["result"] not in {"pass", "fail", "needs_human"}:
        raise ValueError("invalid validation result")
    if not isinstance(value["evidence_refs"], list) or not all(
        isinstance(ref, str) and 0 < len(ref) <= 256 for ref in value["evidence_refs"]
    ):
        raise ValueError("validation evidence_refs must be bounded strings")
    utc_timestamp(value["validated_at"])
    return value


def _validate_findings(findings: list[Any], *, label: str) -> None:
    for finding in findings:
        finding = require_object(finding, label=f"{label} finding")
        require_keys(
            finding,
            required={"code", "severity", "path", "evidence_ref"},
            optional=set(),
            label=f"{label} finding",
        )
        require_identifier(finding["code"], label=f"{label} finding code")
        if finding["severity"] not in {"low", "medium", "high"}:
            raise ValueError(f"{label} finding severity is invalid")
        if finding["path"] is not None and (
            not isinstance(finding["path"], str) or not finding["path"] or len(finding["path"]) > 256
        ):
            raise ValueError(f"{label} finding path is invalid")
        if not isinstance(finding["evidence_ref"], str) or not finding["evidence_ref"] or len(finding["evidence_ref"]) > 256:
            raise ValueError(f"{label} finding evidence_ref is invalid")


def validate_candidate_binding(value: Any) -> dict[str, Any]:
    value = require_object(value, label="candidate_binding")
    require_keys(
        value,
        required={
            "schema_version", "change_id", "candidate_id", "base_sha", "patch_sha256",
            "head_sha", "verification_result", "evidence_refs", "verified_at",
        },
        optional=set(),
        label="candidate_binding",
    )
    if value["schema_version"] != 1:
        raise ValueError("unsupported candidate binding schema_version")
    require_identifier(value["change_id"], label="change_id")
    _require_digest(value["candidate_id"], label="candidate_id")
    _require_digest(value["patch_sha256"], label="patch_sha256")
    require_sha(value["base_sha"], label="base_sha")
    require_sha(value["head_sha"], label="head_sha")
    if value["verification_result"] != "matched":
        raise ValueError("candidate binding must be an exact match")
    if not isinstance(value["evidence_refs"], list) or not all(
        isinstance(ref, str) and 0 < len(ref) <= 256 for ref in value["evidence_refs"]
    ):
        raise ValueError("candidate binding evidence_refs must be bounded strings")
    utc_timestamp(value["verified_at"])
    return value
