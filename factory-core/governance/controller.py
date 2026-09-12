"""Durable G2 change lifecycle with one pull request per objective."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .contracts import (
    candidate_id as calculate_candidate_id,
    content_hash,
    patch_sha256,
    utc_timestamp,
    validate_builder_result,
    validate_candidate_binding,
    validate_candidate_review,
    validate_validation_result,
    validate_objective,
    validate_reviewer_report,
)
from .events import EventStore, atomic_json, now

TERMINAL = {"COMPLETED", "EXPIRED", "FAILED", "NEEDS_ATTENTION", "PAUSED"}


class ChangeController:
    def __init__(self, root: Path, objective: dict[str, Any] | None = None) -> None:
        self.root = Path(root)
        self.store = EventStore(self.root)
        self.objective_path = self.root / "objective.json"
        self.state_path = self.root / "state.json"
        if objective is not None:
            objective = validate_objective(objective)
            atomic_json(self.objective_path, objective, replace=False)
            started_at = now()
            state = {
                "schema_version": 1,
                "change_id": objective["change_id"],
                "objective_hash": content_hash(objective),
                "phase": "RECEIVED",
                "started_at": started_at,
                "updated_at": started_at,
                "attempt_count": 0,
                "pr": None,
                "head_sha": None,
                "review_head_sha": None,
                "decision_id": None,
                "candidate_id": None,
                "candidate_patch_sha256": None,
                "candidate_binding_ref": None,
                "agentic_routing_policy": None,
            }
            atomic_json(self.state_path, state, replace=False)
            self.store.append(
                "change_received",
                {
                    "change_id": objective["change_id"],
                    "repository": objective["repository"],
                    "objective_hash": state["objective_hash"],
                    "phase": state["phase"],
                    "started_at": started_at,
                },
            )
        if not self.objective_path.is_file() or not self.state_path.is_file():
            raise FileNotFoundError("change objective and state are required")

    @property
    def objective(self) -> dict[str, Any]:
        return json.loads(self.objective_path.read_text(encoding="utf-8"))

    @property
    def state(self) -> dict[str, Any]:
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def _write_state(self, state: dict[str, Any]) -> dict[str, Any]:
        state["updated_at"] = now()
        atomic_json(self.state_path, state, replace=True)
        return state

    def _within_budget(self, state: dict[str, Any]) -> bool:
        budget = self.objective["budgets"]
        elapsed = (
            datetime.now(timezone.utc) - utc_timestamp(state["started_at"])
        ).total_seconds()
        return (
            state["attempt_count"] < budget["max_attempts"]
            and elapsed < budget["max_elapsed_seconds"]
        )

    def bind_agentic_routing_policy(self, identity: dict[str, Any]) -> dict[str, Any]:
        """Freeze one already validated routing identity before the first attempt."""
        if set(identity) != {"policy_id", "version", "policy_sha256"}:
            raise ValueError("agentic routing identity has unexpected fields")
        if not isinstance(identity["policy_id"], str) or not identity["policy_id"]:
            raise ValueError("agentic routing policy_id is required")
        if type(identity["version"]) is not int or identity["version"] < 1:
            raise ValueError("agentic routing version is invalid")
        if not isinstance(identity["policy_sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", identity["policy_sha256"]):
            raise ValueError("agentic routing hash is invalid")
        state = self.state
        existing = state.get("agentic_routing_policy")
        if existing is not None and existing != identity:
            raise ValueError("agentic routing policy cannot change during a change")
        if existing is None:
            self.store.append("agentic_routing_bound", {"change_id": state["change_id"], **identity})
            state["agentic_routing_policy"] = identity
            self._write_state(state)
        return self.state

    def begin_attempt(self, *, head_sha: str | None = None) -> dict[str, Any]:
        state = self.state
        if state["phase"] in TERMINAL:
            raise ValueError("terminal change cannot start another attempt")
        if not self._within_budget(state):
            state["phase"] = "NEEDS_ATTENTION"
            self.store.append(
                "budget_exhausted",
                {
                    "change_id": state["change_id"],
                    "attempt_count": state["attempt_count"],
                },
            )
            return self._write_state(state)
        state["attempt_count"] += 1
        state["phase"] = "BUILDING"
        if head_sha is not None and head_sha != state.get("head_sha"):
            state["head_sha"] = head_sha
            state["review_head_sha"] = None
            state["decision_id"] = None
        self.store.append(
            "attempt_started",
            {
                "change_id": state["change_id"],
                "attempt": state["attempt_count"],
                "head_sha": state.get("head_sha"),
            },
        )
        return self._write_state(state)

    def record_review(self, report: dict[str, Any]) -> dict[str, Any]:
        report = validate_reviewer_report(report)
        state = self.state
        if (
            report["change_id"] != state["change_id"]
            or report["attempt"] != state["attempt_count"]
        ):
            raise ValueError("review does not belong to current attempt")
        if report["objective_hash"] != state["objective_hash"]:
            raise ValueError("review objective hash mismatch")
        self.store.append("review_recorded", report, event_id=content_hash(report))
        state["review_head_sha"] = report["head_sha"]
        if state.get("head_sha") is None:
            state["head_sha"] = report["head_sha"]
        state["phase"] = (
            "CANDIDATE_VIABLE"
            if report["result"] == "pass"
            else (
                "NEEDS_ATTENTION" if report["result"] == "needs_human" else "REWORKING"
            )
        )
        return self._write_state(state)

    def record_builder_result(self, result: dict[str, Any]) -> dict[str, Any]:
        result = validate_builder_result(result)
        state = self.state
        if state["phase"] != "BUILDING":
            raise ValueError("builder result requires BUILDING phase")
        self.store.append("builder_result_recorded", {"change_id": state["change_id"], **result})
        state["phase"] = {
            "candidate_ready": "CANDIDATE_PENDING",
            "needs_human": "NEEDS_ATTENTION",
            "failed": "REWORKING",
        }[result["status"]]
        return self._write_state(state)

    def record_candidate(self, *, candidate_id: str, patch: str) -> dict[str, Any]:
        state = self.state
        if state["phase"] != "CANDIDATE_PENDING":
            raise ValueError("candidate requires CANDIDATE_PENDING phase")
        if calculate_candidate_id(self.objective["base_sha"], patch) != candidate_id:
            raise ValueError("candidate identity does not match exact patch")
        state["candidate_id"] = candidate_id
        state["candidate_patch_sha256"] = patch_sha256(patch)
        self.store.append("candidate_recorded", {
            "change_id": state["change_id"], "attempt": state["attempt_count"],
            "candidate_id": candidate_id, "patch_sha256": state["candidate_patch_sha256"],
        }, event_id=f"{state['change_id']}-candidate-{candidate_id}")
        state["phase"] = "VALIDATING_LOCAL"
        return self._write_state(state)

    def record_validation_result(self, result: dict[str, Any]) -> dict[str, Any]:
        result = validate_validation_result(result)
        state = self.state
        if state["phase"] != "VALIDATING_LOCAL":
            raise ValueError("validation result requires VALIDATING_LOCAL phase")
        if (result["change_id"] != state["change_id"] or result["attempt"] != state["attempt_count"]
                or result["candidate_id"] != state["candidate_id"]):
            raise ValueError("validation result does not match active candidate")
        self.store.append("validation_recorded", result, event_id=content_hash(result))
        state["phase"] = {"pass": "REVIEWING_CANDIDATE", "fail": "REWORKING", "needs_human": "NEEDS_ATTENTION"}[result["result"]]
        return self._write_state(state)

    def record_candidate_review(self, review: dict[str, Any]) -> dict[str, Any]:
        review = validate_candidate_review(review)
        state = self.state
        if state["phase"] != "REVIEWING_CANDIDATE":
            raise ValueError("candidate review requires REVIEWING_CANDIDATE phase")
        if (review["change_id"] != state["change_id"] or review["attempt"] != state["attempt_count"]
                or review["objective_hash"] != state["objective_hash"]
                or review["candidate_id"] != state["candidate_id"]):
            raise ValueError("candidate review does not match active candidate")
        self.store.append("candidate_review_recorded", review, event_id=content_hash(review))
        state["phase"] = {"pass": "CANDIDATE_VIABLE", "fail": "REWORKING", "needs_human": "NEEDS_ATTENTION"}[review["result"]]
        return self._write_state(state)

    def record_candidate_binding(self, binding: dict[str, Any]) -> dict[str, Any]:
        binding = validate_candidate_binding(binding)
        state = self.state
        if state["phase"] != "CANDIDATE_VIABLE":
            raise ValueError("candidate binding requires CANDIDATE_VIABLE phase")
        if (binding["change_id"] != state["change_id"] or binding["candidate_id"] != state["candidate_id"]
                or binding["base_sha"] != self.objective["base_sha"]
                or binding["patch_sha256"] != state["candidate_patch_sha256"]):
            raise ValueError("candidate binding does not match active candidate")
        reference = content_hash(binding)
        self.store.append("candidate_bound", binding, event_id=reference)
        state["candidate_binding_ref"] = reference
        state["head_sha"] = binding["head_sha"]
        state["phase"] = "CANDIDATE_BOUND"
        return self._write_state(state)

    def attach_pr(self, *, number: int, url: str, head_sha: str) -> dict[str, Any]:
        state = self.state
        existing = state.get("pr")
        candidate = {"number": number, "url": url}
        if existing is not None and existing != candidate:
            raise ValueError("one change_id cannot create a second pull request")
        state["pr"] = candidate
        if head_sha != state.get("head_sha"):
            state["review_head_sha"] = None
            state["decision_id"] = None
        state["head_sha"] = head_sha
        state["phase"] = "VALIDATING_REMOTE"
        self.store.append(
            "pr_attached",
            {
                "change_id": state["change_id"],
                "pr_number": number,
                "pr_url": url,
                "head_sha": head_sha,
            },
            event_id=f"{state['change_id']}-pr-{head_sha}",
        )
        return self._write_state(state)

    def record_decision(self, decision: dict[str, Any]) -> dict[str, Any]:
        state = self.state
        if (
            decision.get("change_id") != state["change_id"]
            or decision.get("head_sha") != state["head_sha"]
        ):
            raise ValueError("decision does not match current change head")
        self.store.append("policy_decided", decision, event_id=decision["decision_id"])
        state["decision_id"] = decision["decision_id"]
        state["phase"] = {
            "eligible": "ELIGIBLE",
            "blocked": "REWORKING",
            "needs_human": "NEEDS_ATTENTION",
        }[decision["decision"]]
        return self._write_state(state)

    def mark_completed(self) -> dict[str, Any]:
        """Close the durable lifecycle after the trusted executor confirms merge."""
        state = self.state
        if state["phase"] not in {"ELIGIBLE", "MERGING", "COMPLETED"}:
            raise ValueError("only an eligible or merging change can complete")
        state["phase"] = "COMPLETED"
        return self._write_state(state)

    def mark_expired(self, decision: dict[str, Any]) -> dict[str, Any]:
        """Close an eligible decision whose immutable TTL has elapsed."""
        state = self.state
        if state["phase"] != "ELIGIBLE" or decision.get("decision_id") != state.get("decision_id"):
            raise ValueError("only the active eligible decision can expire")
        self.store.append(
            "decision_expired",
            {"change_id": state["change_id"], "decision_id": state["decision_id"], "expires_at": decision["expires_at"]},
            event_id=f"expired-{state['decision_id']}",
        )
        state["phase"] = "EXPIRED"
        return self._write_state(state)
