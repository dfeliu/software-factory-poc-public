"""Deterministic G2 risk classification and merge eligibility."""

from __future__ import annotations

import fnmatch
import hashlib
import json
from datetime import timedelta
from pathlib import Path
from typing import Any

from .contracts import (
    content_hash,
    require_identifier,
    require_object,
    require_sha,
    utc_timestamp,
    validate_objective,
    validate_reviewer_report,
)


def load_active_policy(
    policy_path: Path, activation_path: Path
) -> tuple[dict[str, Any], dict[str, Any]]:
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    activation = json.loads(activation_path.read_text(encoding="utf-8"))
    if not isinstance(policy, dict) or not isinstance(activation, dict):
        raise ValueError("policy and activation manifest must be objects")
    _validate_policy(policy)
    _validate_activation(policy, activation)
    expected = activation.get("policy_sha256")
    observed = hashlib.sha256(policy_path.read_bytes()).hexdigest()
    if expected != observed:
        raise ValueError("active policy hash does not match policy file")
    return policy, activation


def _validate_activation(policy: dict[str, Any], activation: dict[str, Any]) -> None:
    activation_keys = {
        "schema_version",
        "policy_id",
        "policy_revision",
        "governance_profile",
        "policy_sha256",
        "mode",
    }
    if activation.keys() != activation_keys or activation.get("schema_version") != 1:
        raise ValueError(
            "activation manifest has missing, unknown or unsupported fields"
        )
    for key in ("policy_id", "policy_revision", "governance_profile"):
        if activation.get(key) != policy.get(key):
            raise ValueError(f"active policy {key} does not match")
    if activation.get("mode") not in {"shadow", "enforced"}:
        raise ValueError("activation mode must be shadow or enforced")
    policy_hash = activation.get("policy_sha256")
    if (
        not isinstance(policy_hash, str)
        or len(policy_hash) != 64
        or any(character not in "0123456789abcdef" for character in policy_hash)
    ):
        raise ValueError("policy_sha256 must be a lowercase SHA-256 value")


def _validate_policy(policy: dict[str, Any]) -> None:
    required = {
        "schema_version",
        "policy_id",
        "policy_revision",
        "governance_level",
        "governance_profile",
        "repository_patterns",
        "builder",
        "merge_actor",
        "base_branch",
        "allowed_paths",
        "added_only_paths",
        "denied_paths",
        "limits",
        "required_checks",
        "reviewer",
        "decision_ttl_seconds",
        "audit",
    }
    if policy.keys() != required:
        raise ValueError(f"policy keys differ: {sorted(policy.keys() ^ required)}")
    if policy["schema_version"] != 1 or policy["governance_level"] != "G2":
        raise ValueError("unsupported policy schema or governance level")
    for key in (
        "policy_id",
        "governance_profile",
        "builder",
        "merge_actor",
        "base_branch",
    ):
        require_identifier(policy[key], label=key)
    if type(policy["policy_revision"]) is not int or policy["policy_revision"] < 1:
        raise ValueError("policy_revision must be positive")
    if (
        type(policy["decision_ttl_seconds"]) is not int
        or policy["decision_ttl_seconds"] <= 0
    ):
        raise ValueError("decision_ttl_seconds must be positive")
    for key in (
        "repository_patterns",
        "allowed_paths",
        "added_only_paths",
        "denied_paths",
        "required_checks",
    ):
        if (
            not isinstance(policy[key], list)
            or not policy[key]
            or not all(isinstance(item, str) and item for item in policy[key])
        ):
            raise ValueError(f"{key} must be a non-empty string list")
    limits = require_object(policy["limits"], label="limits")
    if limits.keys() != {
        "max_files",
        "max_changed_lines",
        "max_attempts",
        "max_elapsed_seconds",
    }:
        raise ValueError("unexpected policy limits")
    if not all(type(value) is int and value > 0 for value in limits.values()):
        raise ValueError("policy limits must be positive integers")
    reviewer = require_object(policy["reviewer"], label="reviewer")
    if reviewer != {"required_result": "pass", "context_isolation": True}:
        raise ValueError("unsupported reviewer policy")
    audit = require_object(policy["audit"], label="audit")
    if audit.keys() != {"full_audit_first", "sample_modulus"} or not all(
        type(value) is int and value > 0 for value in audit.values()
    ):
        raise ValueError("invalid audit policy")


def _matches(path: str, patterns: list[str]) -> bool:
    normalized = path.replace("\\", "/")
    return any(fnmatch.fnmatchcase(normalized, pattern) for pattern in patterns)


def _decision(
    base: dict[str, Any], decision: str, reason_codes: list[str]
) -> dict[str, Any]:
    value = {**base, "decision": decision, "reason_codes": sorted(set(reason_codes))}
    value["decision_id"] = content_hash(value)
    return value


def evaluate(
    policy: dict[str, Any], activation: dict[str, Any], bundle: Any
) -> dict[str, Any]:
    """Evaluate an immutable PR bundle. Unknown or inconsistent data never becomes eligible."""
    _validate_policy(policy)
    _validate_activation(policy, activation)
    bundle = require_object(bundle, label="evaluation bundle")
    required = {
        "schema_version",
        "change_id",
        "repository",
        "pr_number",
        "author",
        "base_branch",
        "base_sha",
        "head_sha",
        "draft",
        "mergeable",
        "files",
        "checks",
        "reviewer_report",
        "objective",
        "external_state",
        "attempt",
        "elapsed_seconds",
        "policy_source_commit",
        "evaluated_at",
    }
    optional = {"dispatch_id"}
    if (
        required - bundle.keys()
        or bundle.keys() - required - optional
        or bundle.get("schema_version") != 1
    ):
        raise ValueError("evaluation bundle has missing, unknown or unsupported fields")
    objective = validate_objective(bundle["objective"])
    report = validate_reviewer_report(bundle["reviewer_report"])
    require_identifier(bundle["change_id"], label="change_id")
    if "dispatch_id" in bundle:
        require_identifier(bundle["dispatch_id"], label="dispatch_id")
    if type(bundle["pr_number"]) is not int or bundle["pr_number"] < 1:
        raise ValueError("pr_number must be positive")
    base_sha = require_sha(bundle["base_sha"], label="base_sha")
    head_sha = require_sha(bundle["head_sha"], label="head_sha")
    policy_source_commit = require_sha(
        bundle["policy_source_commit"], label="policy_source_commit"
    )
    evaluated_at = utc_timestamp(bundle["evaluated_at"])
    expires_at = evaluated_at + timedelta(seconds=policy["decision_ttl_seconds"])
    base = {
        "schema_version": 1,
        "change_id": bundle["change_id"],
        "repository": bundle["repository"],
        "pr_number": bundle["pr_number"],
        "base_sha": base_sha,
        "head_sha": head_sha,
        "policy_id": policy["policy_id"],
        "policy_revision": policy["policy_revision"],
        "policy_sha256": activation["policy_sha256"],
        "policy_source_commit": policy_source_commit,
        "governance_level": "G2",
        "governance_profile": policy["governance_profile"],
        "merge_actor": policy["merge_actor"],
        "enforcement_mode": activation["mode"],
        "risk_class": "low",
        "risk_class_source": "deterministic-policy",
        "risk_signals": [],
        "evaluation_bundle_hash": content_hash(bundle),
        "objective_hash": content_hash(objective),
        "review_report_hash": content_hash(report),
        "required_checks": list(policy["required_checks"]),
        "review_result": report["result"],
        "attempt": bundle["attempt"],
        "elapsed_seconds": bundle["elapsed_seconds"],
        "evaluated_at": bundle["evaluated_at"],
        "expires_at": expires_at.isoformat().replace("+00:00", "Z"),
    }
    if "dispatch_id" in bundle:
        base["dispatch_id"] = bundle["dispatch_id"]
    reasons: list[str] = []
    human: list[str] = []
    if (
        bundle["change_id"] != objective["change_id"]
        or report["change_id"] != bundle["change_id"]
    ):
        human.append("change_identity_mismatch")
    if (
        objective["repository"] != bundle["repository"]
        or objective["base_sha"] != base_sha
    ):
        human.append("objective_scope_mismatch")
    if objective["risk_profile"] != policy["governance_profile"]:
        human.append("risk_profile_mismatch")
    if report["objective_hash"] != content_hash(objective):
        human.append("review_objective_mismatch")
    if report["attempt"] != bundle["attempt"]:
        reasons.append("review_attempt_mismatch")
    if report["head_sha"] != head_sha:
        reasons.append("review_head_mismatch")
    if utc_timestamp(report["reviewed_at"]) > evaluated_at:
        human.append("review_timestamp_invalid")
    if not any(
        fnmatch.fnmatchcase(bundle["repository"], pattern)
        for pattern in policy["repository_patterns"]
    ):
        human.append("repository_not_allowed")
    if (
        bundle["author"] != policy["builder"]
        or bundle["base_branch"] != policy["base_branch"]
    ):
        human.append("identity_or_base_not_allowed")
    if bundle["draft"] is not False or bundle["mergeable"] is not True:
        reasons.append("pr_not_ready")
    if bundle["external_state"] != "clear":
        human.append("external_state_ambiguous")
    if report["result"] == "needs_human":
        human.append("reviewer_needs_human")
    elif report["result"] != "pass":
        reasons.append("reviewer_failed")

    files = bundle["files"]
    if not isinstance(files, list) or not files:
        reasons.append("no_changed_files")
        files = []
    allowed = list(policy["allowed_paths"])
    objective_allowed = list(objective["allowed_paths"])
    changed_lines = 0
    for item in files:
        if not isinstance(item, dict) or item.keys() != {
            "path",
            "status",
            "additions",
            "deletions",
            "binary",
            "symlink",
            "mode_changed",
        }:
            human.append("invalid_file_evidence")
            continue
        path = item["path"]
        if not isinstance(path, str) or path.startswith(("/", "../")) or "/../" in path:
            human.append("unsafe_path")
            continue
        if _matches(path, policy["denied_paths"]):
            human.append("denied_path")
        if not _matches(path, allowed) or not _matches(path, objective_allowed):
            human.append("path_not_allowlisted")
        if item["status"] not in {"added", "modified"}:
            human.append("destructive_file_change")
        if _matches(path, policy["added_only_paths"]) and item["status"] != "added":
            human.append("protected_path_requires_addition")
        if (
            item["binary"] is not False
            or item["symlink"] is not False
            or item["mode_changed"] is not False
        ):
            human.append("unsafe_file_type")
        if (
            type(item["additions"]) is not int
            or type(item["deletions"]) is not int
            or item["additions"] < 0
            or item["deletions"] < 0
        ):
            human.append("invalid_diff_size")
        else:
            changed_lines += item["additions"] + item["deletions"]
    effective_max_files = policy["limits"]["max_files"]
    effective_attempts = min(
        policy["limits"]["max_attempts"], objective["budgets"]["max_attempts"]
    )
    effective_elapsed = min(
        policy["limits"]["max_elapsed_seconds"],
        objective["budgets"]["max_elapsed_seconds"],
    )
    base["effective_limits"] = {
        "max_files": effective_max_files,
        "max_changed_lines": policy["limits"]["max_changed_lines"],
        "max_attempts": effective_attempts,
        "max_elapsed_seconds": effective_elapsed,
    }
    if (
        len(files) > effective_max_files
        or changed_lines > policy["limits"]["max_changed_lines"]
    ):
        human.append("diff_limit_exceeded")
    if (
        type(bundle["attempt"]) is not int
        or bundle["attempt"] < 1
        or type(bundle["elapsed_seconds"]) is not int
        or bundle["elapsed_seconds"] < 0
    ):
        human.append("invalid_budget_evidence")
    elif (
        bundle["attempt"] > effective_attempts
        or bundle["elapsed_seconds"] > effective_elapsed
    ):
        human.append("budget_exhausted")
    checks = bundle["checks"]
    if not isinstance(checks, dict) or any(
        checks.get(name) != "success" for name in policy["required_checks"]
    ):
        reasons.append("required_checks_failed_or_missing")
    base["risk_signals"] = sorted(set(human + reasons))
    if human:
        base["risk_class"] = "unknown"
        return _decision(base, "needs_human", human + reasons)
    if reasons:
        return _decision(base, "blocked", reasons)
    return _decision(base, "eligible", ["all_low_risk_controls_passed"])


def evaluate_shadow(
    policy: dict[str, Any], activation: dict[str, Any], bundle: Any
) -> dict[str, Any]:
    """Evaluate existing evidence without enabling an executor or changing activation."""
    shadow_activation = {**activation, "mode": "shadow"}
    return evaluate(policy, shadow_activation, bundle)
