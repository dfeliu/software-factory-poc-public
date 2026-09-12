#!/usr/bin/env python3
"""Normalize image-vulnerability findings and evaluate the ADR-004 gate.

The implementation uses only the Python standard library so that CI runtimes can
reuse it without coupling the gate policy to a provider or package manager.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
BLOCKING_SEVERITIES = {"HIGH", "CRITICAL"}
EXCEPTION_STATUSES = {"active", "expired", "superseded", "revoked"}
CONTROL_REASONS = {
    "passed",
    "control_failed",
    "vulnerabilities_found",
    "execution_failed",
    "evidence_missing",
    "evidence_invalid",
    "not_executed",
    "not_applicable",
    "configuration_invalid",
}


def utc_now() -> datetime:
    return datetime.now(UTC)


def parse_timestamp(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an ISO-8601 timestamp string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{field} is not a valid ISO-8601 timestamp") from error
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include a UTC offset")
    return parsed.astimezone(UTC)


def format_timestamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> tuple[Any, str]:
    raw = path.read_bytes()
    return json.loads(raw.decode("utf-8")), hashlib.sha256(raw).hexdigest()


def fix_status(vulnerability: dict[str, Any]) -> str:
    if "FixedVersion" not in vulnerability:
        return "fix_status_unknown"
    fixed_version = vulnerability["FixedVersion"]
    if fixed_version is None or fixed_version == "":
        return "unfixed"
    if isinstance(fixed_version, str):
        return "fixable"
    return "fix_status_unknown"


def normalize_trivy_report(report: Any, report_sha256: str) -> dict[str, Any]:
    if not isinstance(report, dict) or not isinstance(report.get("Results"), list):
        raise ValueError("Trivy report must contain a Results array")

    findings: list[dict[str, Any]] = []
    for result in report["Results"]:
        if not isinstance(result, dict):
            raise ValueError("Trivy Results entries must be objects")
        vulnerabilities = result.get("Vulnerabilities", [])
        if vulnerabilities is None:
            vulnerabilities = []
        if not isinstance(vulnerabilities, list):
            raise ValueError("Trivy Vulnerabilities must be an array when present")
        target = result.get("Target", "")
        if not isinstance(target, str):
            raise ValueError("Trivy Target must be a string")
        for vulnerability in vulnerabilities:
            if not isinstance(vulnerability, dict):
                raise ValueError("Trivy vulnerability entries must be objects")
            required = ("VulnerabilityID", "PkgName", "InstalledVersion", "Severity")
            if any(not isinstance(vulnerability.get(field), str) for field in required):
                raise ValueError(
                    "Trivy vulnerability entry lacks required string fields"
                )
            severity = vulnerability["Severity"].upper()
            fixed_version = vulnerability.get("FixedVersion")
            if fixed_version is not None and not isinstance(fixed_version, str):
                fixed_version = None
            source = {
                "id": vulnerability["VulnerabilityID"],
                "component": vulnerability["PkgName"],
                "installed_version": vulnerability["InstalledVersion"],
                "target": target,
                "severity": severity,
            }
            finding_key = hashlib.sha256(
                json.dumps(source, sort_keys=True, separators=(",", ":")).encode(
                    "utf-8"
                )
            ).hexdigest()
            findings.append(
                {
                    "finding_key": finding_key,
                    **source,
                    "fixed_version": fixed_version,
                    "fix_status": fix_status(vulnerability),
                }
            )

    return {
        "schema_version": SCHEMA_VERSION,
        "scanner": {"name": "trivy", "report_sha256": report_sha256},
        "findings": findings,
    }


def metrics_for(findings: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {
        "image_security_findings_total": len(findings),
        "image_security_findings_high": sum(
            item["severity"] == "HIGH" for item in findings
        ),
        "image_security_findings_critical": sum(
            item["severity"] == "CRITICAL" for item in findings
        ),
        "image_security_findings_fixable": sum(
            item["fix_status"] == "fixable" for item in findings
        ),
        "image_security_findings_unfixed": sum(
            item["fix_status"] == "unfixed" for item in findings
        ),
        "image_security_findings_fix_status_unknown": sum(
            item["fix_status"] == "fix_status_unknown" for item in findings
        ),
    }
    counts["image_scanner_passed"] = not any(
        item["severity"] in BLOCKING_SEVERITIES for item in findings
    )
    add_image_aliases(counts)
    return counts


def add_image_aliases(metrics: dict[str, Any]) -> None:
    """Keep the pre-6D.1 names as temporary, image-specific aliases."""
    aliases = {
        "scanner_passed": "image_scanner_passed",
        "security_gate_passed": "image_security_gate_passed",
        "security_findings_total": "image_security_findings_total",
        "security_findings_high": "image_security_findings_high",
        "security_findings_critical": "image_security_findings_critical",
        "security_findings_fixable": "image_security_findings_fixable",
        "security_findings_unfixed": "image_security_findings_unfixed",
        "security_findings_fix_status_unknown": "image_security_findings_fix_status_unknown",
        "active_security_exceptions": "active_image_security_exceptions",
        "active_security_exceptions_count": "active_image_security_exceptions_count",
    }
    for alias, canonical in aliases.items():
        if canonical in metrics:
            metrics[alias] = metrics[canonical]


def control_envelope(
    control_id: str,
    *,
    passed: bool | None,
    reason: str,
    execution_status: str,
    evidence_available: bool,
    evidence_valid: bool,
    evidence_sha256: str | None = None,
) -> dict[str, Any]:
    if reason not in CONTROL_REASONS:
        raise ValueError(f"unsupported control reason: {reason}")
    return {
        "schema_version": SCHEMA_VERSION,
        "id": control_id,
        "passed": passed,
        "reason": reason,
        "execution": {"status": execution_status},
        "evidence": {
            "available": evidence_available,
            "valid": evidence_valid,
            "sha256": evidence_sha256,
        },
    }


def require_string(record: dict[str, Any], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value


def validate_exception(
    record: Any, context: dict[str, str], evaluated_at: datetime
) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise ValueError("exception record must be an object")
    if record.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("exception schema_version must be 1")
    exception_id = require_string(record, "id")
    status = require_string(record, "status")
    if status not in EXCEPTION_STATUSES:
        raise ValueError("exception status is invalid")
    finding = record.get("finding")
    scope = record.get("scope")
    if not isinstance(finding, dict) or not isinstance(scope, dict):
        raise ValueError("exception finding and scope must be objects")
    for field in ("id", "component", "installed_version", "target"):
        require_string(finding, field)
    project = require_string(scope, "project")
    selectors = ("commit", "image_digest", "artifact_sha256", "runtime_context_tree")
    if not any(
        isinstance(scope.get(field), str) and scope[field] for field in selectors
    ):
        raise ValueError(
            "exception scope requires a commit, image_digest, artifact_sha256, "
            "or runtime_context_tree"
        )
    for field in selectors:
        value = scope.get(field)
        if value is not None and not isinstance(value, str):
            raise ValueError(f"exception scope.{field} must be a string when present")
    severity = require_string(record, "severity").upper()
    fix_status_value = require_string(record, "fix_status")
    for field in (
        "justification",
        "exposure_assessment",
        "owner",
        "approver",
        "removal_condition",
    ):
        require_string(record, field)
    controls = record.get("compensating_controls")
    if (
        not isinstance(controls, list)
        or not controls
        or not all(isinstance(control, str) and control.strip() for control in controls)
    ):
        raise ValueError("compensating_controls must be a non-empty string array")
    approved_at = parse_timestamp(record.get("approved_at"), "approved_at")
    review_at = parse_timestamp(record.get("review_at"), "review_at")
    expires_at = parse_timestamp(record.get("expires_at"), "expires_at")
    if approved_at > review_at or review_at > expires_at:
        raise ValueError(
            "exception timestamps must satisfy approved_at <= review_at <= expires_at"
        )
    extraordinary = record.get("extraordinary")
    if not isinstance(extraordinary, bool):
        raise ValueError("extraordinary must be boolean")

    if severity == "CRITICAL":
        if not extraordinary:
            raise ValueError("CRITICAL exception must be extraordinary")
        maximum = timedelta(days=7)
    elif severity == "HIGH":
        if extraordinary or fix_status_value not in {"unfixed", "upstream_fix_pending"}:
            raise ValueError(
                "ordinary HIGH exception must be unfixed or upstream_fix_pending "
                "and non-extraordinary"
            )
        maximum = timedelta(days=30)
    else:
        raise ValueError("exceptions are supported only for HIGH or CRITICAL findings")
    if review_at - approved_at > maximum or expires_at - approved_at > maximum:
        raise ValueError("exception review and expiry exceed the policy maximum")

    scope_matches = project == context["project"] and all(
        scope.get(field) is None or scope.get(field) == context.get(field)
        for field in selectors
    )
    is_active = (
        status == "active"
        and scope_matches
        and evaluated_at <= review_at
        and evaluated_at <= expires_at
    )
    return {
        "id": exception_id,
        "finding": finding,
        "severity": severity,
        "fix_status": fix_status_value,
        "extraordinary": extraordinary,
        "is_active": is_active,
    }


def load_exceptions(
    exceptions_dir: Path, context: dict[str, str], evaluated_at: datetime
) -> tuple[list[dict[str, Any]], list[str]]:
    if not exceptions_dir.exists():
        return [], []
    if not exceptions_dir.is_dir():
        return [], [f"{exceptions_dir}: exception path is not a directory"]
    exceptions: list[dict[str, Any]] = []
    errors: list[str] = []
    for path in sorted(exceptions_dir.glob("*.json")):
        try:
            record, _ = load_json(path)
            exceptions.append(validate_exception(record, context, evaluated_at))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
            errors.append(f"{path.name}: {error}")
    return exceptions, errors


def matching_exception(
    finding: dict[str, Any], exceptions: list[dict[str, Any]]
) -> str | None:
    for exception in exceptions:
        if not exception["is_active"]:
            continue
        if exception["finding"] != {
            "id": finding["id"],
            "component": finding["component"],
            "installed_version": finding["installed_version"],
            "target": finding["target"],
        }:
            continue
        if finding["severity"] == "CRITICAL":
            if exception["severity"] == "CRITICAL" and exception["extraordinary"]:
                return exception["id"]
        elif finding["severity"] == "HIGH" and exception["severity"] == "HIGH":
            if (
                finding["fix_status"] == "unfixed"
                and exception["fix_status"] == "unfixed"
            ):
                return exception["id"]
            if (
                finding["fix_status"] == "fix_status_unknown"
                and exception["fix_status"] == "upstream_fix_pending"
            ):
                return exception["id"]
    return None


def evaluate_gate(
    normalized: dict[str, Any] | None,
    context: dict[str, str],
    evaluated_at: datetime,
    scanner_execution_status: str,
    normalization_error: str | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    if normalization_error:
        errors.append(normalization_error)
    findings = normalized.get("findings", []) if normalized else []
    raw_report = {
        "available": normalized is not None,
        "report_sha256": normalized.get("scanner", {}).get("report_sha256")
        if normalized
        else None,
    }
    if normalized is None:
        metric_values: dict[str, Any] = {
            "image_security_findings_total": None,
            "image_security_findings_high": None,
            "image_security_findings_critical": None,
            "image_security_findings_fixable": None,
            "image_security_findings_unfixed": None,
            "image_security_findings_fix_status_unknown": None,
            "image_scanner_passed": False,
        }
        exceptions, exception_errors = [], []
    else:
        metric_values = metrics_for(findings)
        exceptions, exception_errors = load_exceptions(
            Path(context["exceptions_dir"]), context, evaluated_at
        )
    errors.extend(exception_errors)
    active_ids: list[str] = []
    blockers: list[dict[str, str]] = []

    if normalized is not None:
        for finding in findings:
            severity = finding["severity"]
            if severity not in BLOCKING_SEVERITIES:
                continue
            exception_id = matching_exception(finding, exceptions)
            if exception_id:
                active_ids.append(exception_id)
                continue
            if severity == "CRITICAL":
                rule = "critical_requires_extraordinary_exception"
            elif finding["fix_status"] == "fixable":
                rule = "high_fixable_blocks"
            elif finding["fix_status"] == "unfixed":
                rule = "high_unfixed_requires_exception"
            else:
                rule = "high_unknown_fix_status_blocks"
            blockers.append({"finding_key": finding["finding_key"], "rule": rule})

    active_ids = sorted(set(active_ids))
    scanner_completed = scanner_execution_status == "completed"
    gate_passed = (
        normalized is not None and scanner_completed and not errors and not blockers
    )
    metric_values.update(
        {
            "active_image_security_exceptions": active_ids,
            "active_image_security_exceptions_count": len(active_ids),
            "image_security_gate_passed": gate_passed,
        }
    )
    add_image_aliases(metric_values)
    reason = "passed" if gate_passed else "control_failed"
    if normalized is None:
        reason = "evidence_invalid" if normalization_error else "evidence_missing"
    elif not scanner_completed:
        reason = "execution_failed"
    elif errors:
        reason = "evidence_invalid"
    return {
        "schema_version": SCHEMA_VERSION,
        "evaluation_scope": "image-vulnerability-gate-only",
        "evaluated_at": format_timestamp(evaluated_at),
        "evaluation_context": {
            "project": context["project"],
            "commit": context["commit"],
            "image_digest": context.get("image_digest") or None,
            "runtime_context_tree": context.get("runtime_context_tree") or None,
        },
        "raw_report": raw_report,
        "scanner_execution": {"status": scanner_execution_status},
        "control": control_envelope(
            "image-vulnerability-gate",
            passed=gate_passed,
            reason=reason,
            execution_status=scanner_execution_status,
            evidence_available=normalized is not None,
            evidence_valid=normalized is not None and not normalization_error,
            evidence_sha256=raw_report["report_sha256"],
        ),
        "metrics": metric_values,
        "blockers": blockers,
        "exception_evaluation_errors": errors,
        "limitations": [
            "Dependency auditing is required independently and is outside this image-vulnerability evaluator.",
            "The aggregate security_passed outcome is evaluated separately from explicit control evidence.",
        ],
    }


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def dependency_audit_evidence(raw_path: Path, command_outcome: str) -> dict[str, Any]:
    """Evaluate pip-audit JSON without making it part of the image gate."""
    report: Any = None
    report_sha256: str | None = None
    error: str | None = None
    try:
        report, report_sha256 = load_json(raw_path)
        if not isinstance(report, dict):
            raise ValueError("pip-audit report must be a JSON object")
        dependencies = report.get("dependencies")
        fixes = report.get("fixes")
        if not isinstance(dependencies, list) or not isinstance(fixes, list):
            raise ValueError(
                "pip-audit report must contain dependencies and fixes arrays"
            )
        for dependency in dependencies:
            if not isinstance(dependency, dict):
                raise ValueError("pip-audit dependency entries must be objects")
            if not isinstance(dependency.get("name"), str) or not isinstance(
                dependency.get("version"), str
            ):
                raise ValueError(
                    "pip-audit dependency entries require name and version strings"
                )
            if not isinstance(dependency.get("vulns"), list):
                raise ValueError("pip-audit dependency entries require a vulns array")
            if not all(
                isinstance(vulnerability, dict) for vulnerability in dependency["vulns"]
            ):
                raise ValueError("pip-audit vulnerability entries must be objects")
    except FileNotFoundError:
        error = "evidence_missing"
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):  # fmt: skip
        error = "evidence_invalid"

    if command_outcome == "skipped":
        passed = False
        reason = "not_executed"
        execution = "not_executed"
    elif command_outcome == "unknown":
        passed = False
        reason = "execution_failed"
        execution = "failed"
    elif error:
        passed = False
        reason = error
        execution = "completed" if command_outcome == "success" else "failed"
    else:
        vulnerability_count = sum(
            len(dependency["vulns"]) for dependency in dependencies
        )
        passed = vulnerability_count == 0
        reason = "passed" if passed else "vulnerabilities_found"
        execution = "completed"
    return {
        "schema_version": SCHEMA_VERSION,
        "control": control_envelope(
            "dependency-audit",
            passed=passed,
            reason=reason,
            execution_status=execution,
            evidence_available=error != "evidence_missing",
            evidence_valid=error is None,
            evidence_sha256=report_sha256,
        ),
        "raw_report": {
            "available": error != "evidence_missing",
            "report_sha256": report_sha256,
        },
        "metrics": {"dependency_audit_passed": passed},
    }


def require_control_envelope(value: Any, control_id: str) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("control envelope schema_version must be 1")
    if value.get("id") != control_id:
        raise ValueError("control envelope id does not match configuration")
    if value.get("reason") not in CONTROL_REASONS:
        raise ValueError("control envelope reason is invalid")
    if (
        value.get("passed") is not True
        and value.get("passed") is not False
        and value.get("passed") is not None
    ):
        raise ValueError("control envelope passed is invalid")
    if not isinstance(value.get("execution"), dict) or not isinstance(
        value["execution"].get("status"), str
    ):
        raise ValueError("control envelope execution is invalid")
    if not isinstance(value.get("evidence"), dict) or not all(
        isinstance(value["evidence"].get(field), bool)
        for field in ("available", "valid")
    ):
        raise ValueError("control envelope evidence is invalid")
    return value


def aggregate_controls(config: Any) -> dict[str, Any]:
    """Aggregate only controls explicitly listed in a versioned configuration."""
    errors: list[str] = []
    controls: list[dict[str, Any]] = []
    if not isinstance(config, dict) or config.get("schema_version") != SCHEMA_VERSION:
        errors.append("configuration_invalid")
        configured: list[Any] = []
    else:
        configured = config.get("controls", [])
        if not isinstance(configured, list) or not configured:
            errors.append("configuration_invalid")
            configured = []

    seen: set[str] = set()
    for definition in configured:
        if not isinstance(definition, dict):
            errors.append("configuration_invalid")
            continue
        control_id = definition.get("id")
        required = definition.get("required")
        evidence_path = definition.get("evidence_path")
        if (
            not isinstance(control_id, str)
            or not control_id
            or control_id in seen
            or not isinstance(required, bool)
            or not isinstance(evidence_path, str)
            or not evidence_path
        ):
            errors.append("configuration_invalid")
            continue
        seen.add(control_id)
        result: dict[str, Any] = {"id": control_id, "required": required}
        try:
            evidence, _ = load_json(Path(evidence_path))
            envelope = require_control_envelope(evidence.get("control"), control_id)
            result["control"] = envelope
            result["metrics"] = evidence.get("metrics", {})
        except FileNotFoundError:
            result["control"] = control_envelope(
                control_id,
                passed=False,
                reason="evidence_missing",
                execution_status="not_executed",
                evidence_available=False,
                evidence_valid=False,
            )
        except (
            OSError,
            UnicodeDecodeError,
            json.JSONDecodeError,
            ValueError,
            AttributeError,
        ):
            result["control"] = control_envelope(
                control_id,
                passed=False,
                reason="evidence_invalid",
                execution_status="failed",
                evidence_available=True,
                evidence_valid=False,
            )
        controls.append(result)

    all_passed = not errors
    for result in controls:
        envelope = result["control"]
        if result["required"] and envelope["passed"] is not True:
            all_passed = False

    reasons = [error for error in errors]
    reasons.extend(
        result["control"]["reason"]
        for result in controls
        if result["required"] and result["control"]["passed"] is not True
    )
    priority = (
        "configuration_invalid",
        "evidence_invalid",
        "evidence_missing",
        "not_executed",
        "execution_failed",
        "control_failed",
    )
    aggregate_reason = (
        "passed"
        if all_passed
        else next((item for item in priority if item in reasons), "control_failed")
    )
    metric_values: dict[str, Any] = {"security_passed": all_passed}
    for result in controls:
        metrics = result.get("metrics", {})
        if isinstance(metrics, dict):
            for field in (
                "dependency_audit_passed",
                "image_scanner_passed",
                "image_security_gate_passed",
            ):
                if field in metrics:
                    metric_values[field] = metrics[field]
    return {
        "schema_version": SCHEMA_VERSION,
        "aggregation": {
            "required_controls_are_explicit": True,
            "reason": aggregate_reason,
        },
        "controls": controls,
        "metrics": metric_values,
    }


def evaluate_trivy_command(arguments: argparse.Namespace) -> int:
    raw_path = Path(arguments.raw_report)
    normalized_output = Path(arguments.normalized_output)
    evidence_output = Path(arguments.evidence_output)
    evaluated_at = (
        parse_timestamp(arguments.evaluated_at, "evaluated_at")
        if arguments.evaluated_at
        else utc_now()
    )
    context = {
        "project": arguments.project,
        "commit": arguments.commit,
        "image_digest": arguments.image_digest or "",
        "runtime_context_tree": arguments.runtime_context_tree or "",
        "artifact_sha256": "",
        "exceptions_dir": arguments.exceptions_dir,
    }
    normalized: dict[str, Any] | None = None
    normalization_error: str | None = None
    try:
        report, report_sha256 = load_json(raw_path)
        context["artifact_sha256"] = report_sha256
        normalized = normalize_trivy_report(report, report_sha256)
        write_json(normalized_output, normalized)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        normalization_error = f"normalization failed: {error}"
    evidence = evaluate_gate(
        normalized,
        context,
        evaluated_at,
        arguments.scanner_execution_status,
        normalization_error,
    )
    write_json(evidence_output, evidence)
    return 0


def evaluate_dependency_audit_command(arguments: argparse.Namespace) -> int:
    evidence = dependency_audit_evidence(
        Path(arguments.raw_report), arguments.command_outcome
    )
    write_json(Path(arguments.evidence_output), evidence)
    return 0


def aggregate_command(arguments: argparse.Namespace) -> int:
    try:
        config, _ = load_json(Path(arguments.controls_config))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):  # fmt: skip
        config = None
    write_json(Path(arguments.evidence_output), aggregate_controls(config))
    return 0


def assert_gate_command(arguments: argparse.Namespace) -> int:
    try:
        evidence, _ = load_json(Path(arguments.evidence))
        passed = evidence["metrics"]["security_gate_passed"]
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
    ) as error:
        print(
            f"security gate evidence is unavailable or invalid: {error}",
            file=sys.stderr,
        )
        return 1
    if passed is True:
        print("security_gate_passed=true")
        return 0
    print("security_gate_passed=false", file=sys.stderr)
    return 1


def assert_summary_command(arguments: argparse.Namespace) -> int:
    try:
        evidence, _ = load_json(Path(arguments.evidence))
        passed = evidence["metrics"]["security_passed"]
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
    ) as error:
        print(
            f"security summary evidence is unavailable or invalid: {error}",
            file=sys.stderr,
        )
        return 1
    if passed is True:
        print("security_passed=true")
        return 0
    print("security_passed=false", file=sys.stderr)
    return 1


def summary_command(arguments: argparse.Namespace) -> int:
    try:
        evidence, _ = load_json(Path(arguments.evidence))
        metrics = evidence["metrics"]
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
    ) as error:
        print(f"## Security gate\n\nEvidence unavailable: {error}")
        return 0
    print("## Image security gate")
    print()
    print(f"- Scanner execution: `{evidence['scanner_execution']['status']}`")
    for field in (
        "image_scanner_passed",
        "image_security_gate_passed",
        "image_security_findings_total",
        "image_security_findings_high",
        "image_security_findings_critical",
        "image_security_findings_fixable",
        "image_security_findings_unfixed",
        "image_security_findings_fix_status_unknown",
        "active_image_security_exceptions_count",
    ):
        print(f"- {field}: `{metrics.get(field)}`")
    print(
        f"- active_image_security_exceptions: `{metrics.get('active_image_security_exceptions')}`"
    )
    return 0


def summary_aggregate_command(arguments: argparse.Namespace) -> int:
    try:
        evidence, _ = load_json(Path(arguments.evidence))
        metrics = evidence["metrics"]
        controls = evidence["controls"]
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
    ) as error:
        print(f"## Security summary\n\nEvidence unavailable: {error}")
        return 0
    print("## Security summary")
    print()
    for field in (
        "dependency_audit_passed",
        "image_scanner_passed",
        "image_security_gate_passed",
        "security_passed",
    ):
        print(f"- {field}: `{metrics.get(field)}`")
    for control in controls:
        envelope = control["control"]
        print(f"- {control['id']}: `{envelope['passed']}` ({envelope['reason']})")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    evaluate = commands.add_parser("evaluate-trivy")
    evaluate.add_argument("--raw-report", required=True)
    evaluate.add_argument("--normalized-output", required=True)
    evaluate.add_argument("--evidence-output", required=True)
    evaluate.add_argument("--exceptions-dir", required=True)
    evaluate.add_argument("--project", required=True)
    evaluate.add_argument("--commit", required=True)
    evaluate.add_argument("--image-digest")
    evaluate.add_argument("--runtime-context-tree")
    evaluate.add_argument("--evaluated-at")
    evaluate.add_argument(
        "--scanner-execution-status",
        choices=("completed", "failed", "unknown"),
        required=True,
    )
    evaluate.set_defaults(handler=evaluate_trivy_command)
    dependency_audit = commands.add_parser("evaluate-dependency-audit")
    dependency_audit.add_argument("--raw-report", required=True)
    dependency_audit.add_argument("--evidence-output", required=True)
    dependency_audit.add_argument(
        "--command-outcome",
        choices=("success", "failure", "skipped", "unknown"),
        required=True,
    )
    dependency_audit.set_defaults(handler=evaluate_dependency_audit_command)
    aggregate = commands.add_parser("aggregate")
    aggregate.add_argument("--controls-config", required=True)
    aggregate.add_argument("--evidence-output", required=True)
    aggregate.set_defaults(handler=aggregate_command)
    assertion = commands.add_parser("assert-gate")
    assertion.add_argument("--evidence", required=True)
    assertion.set_defaults(handler=assert_gate_command)
    summary_assertion = commands.add_parser("assert-summary")
    summary_assertion.add_argument("--evidence", required=True)
    summary_assertion.set_defaults(handler=assert_summary_command)
    summary = commands.add_parser("summary")
    summary.add_argument("--evidence", required=True)
    summary.set_defaults(handler=summary_command)
    aggregate_summary = commands.add_parser("summary-aggregate")
    aggregate_summary.add_argument("--evidence", required=True)
    aggregate_summary.set_defaults(handler=summary_aggregate_command)
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    return arguments.handler(arguments)


if __name__ == "__main__":
    raise SystemExit(main())
