from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from governance.contracts import content_hash  # noqa: E402
from governance.policy import evaluate, evaluate_shadow, load_active_policy  # noqa: E402
from agentic.g2_shadow import bundle_from_s2_evidence  # noqa: E402

POLICY_PATH = ROOT / "policies" / "enforcement" / "g2-disposable-v1.json"
ACTIVE_PATH = ROOT / "policies" / "enforcement" / "active.json"
HEAD = "b" * 40
BASE = "a" * 40


def objective() -> dict:
    return {
        "schema_version": 1,
        "change_id": "change-1",
        "repository": "software-factory/g2-qualification-r1",
        "base_sha": BASE,
        "goal": "Fix the documented soft-delete regression",
        "acceptance_criteria": ["PostgreSQL regression test passes"],
        "allowed_paths": ["application/api/incidents.py", "tests/integration/**"],
        "budgets": {"max_attempts": 3, "max_elapsed_seconds": 2700},
        "risk_profile": "G2-disposable-v1",
    }


def bundle(policy: dict) -> dict:
    obj = objective()
    report = {
        "schema_version": 1,
        "change_id": "change-1",
        "attempt": 1,
        "head_sha": HEAD,
        "objective_hash": content_hash(obj),
        "model": "test-model",
        "prompt_version": "reviewer-v1",
        "result": "pass",
        "findings": [],
        "evidence_refs": ["ci:test"],
        "reviewed_at": "2026-08-31T10:00:00Z",
    }
    return {
        "schema_version": 1,
        "change_id": "change-1",
        "repository": "software-factory/g2-qualification-r1",
        "pr_number": 7,
        "author": "factory-agent",
        "base_branch": "main",
        "base_sha": BASE,
        "head_sha": HEAD,
        "draft": False,
        "mergeable": True,
        "files": [
            {
                "path": "application/api/incidents.py",
                "status": "modified",
                "additions": 3,
                "deletions": 1,
                "binary": False,
                "symlink": False,
                "mode_changed": False,
            },
            {
                "path": "tests/integration/test_incidents_api.py",
                "status": "added",
                "additions": 8,
                "deletions": 0,
                "binary": False,
                "symlink": False,
                "mode_changed": False,
            },
        ],
        "checks": {name: "success" for name in policy["required_checks"]},
        "reviewer_report": report,
        "objective": obj,
        "external_state": "clear",
        "attempt": 1,
        "elapsed_seconds": 60,
        "policy_source_commit": "d" * 40,
        "evaluated_at": "2026-08-31T10:01:00Z",
    }


class G2PolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.policy, cls.activation = load_active_policy(POLICY_PATH, ACTIVE_PATH)

    def test_safe_bounded_change_is_eligible_in_active_mode(self) -> None:
        result = evaluate(self.policy, self.activation, bundle(self.policy))
        self.assertEqual(result["decision"], "eligible")
        self.assertEqual(result["enforcement_mode"], self.activation["mode"])
        self.assertEqual(result["risk_class_source"], "deterministic-policy")
        self.assertEqual(result["merge_actor"], "forgejo-automerge")

    def test_explicit_dispatch_identity_is_bound_into_decision_hash(self) -> None:
        value = bundle(self.policy)
        value["dispatch_id"] = "dispatch-1"
        first = evaluate(self.policy, self.activation, value)
        self.assertEqual(first["dispatch_id"], "dispatch-1")
        value["dispatch_id"] = "dispatch-2"
        second = evaluate(self.policy, self.activation, value)
        self.assertNotEqual(first["decision_id"], second["decision_id"])

    def test_sensitive_workflow_escalates_even_if_reviewer_passes(self) -> None:
        value = bundle(self.policy)
        value["files"] = [
            {
                "path": ".forgejo/workflows/ci.yml",
                "status": "modified",
                "additions": 1,
                "deletions": 1,
                "binary": False,
                "symlink": False,
                "mode_changed": False,
            }
        ]
        value["objective"]["allowed_paths"] = ["**"]
        value["reviewer_report"]["objective_hash"] = content_hash(value["objective"])
        result = evaluate(self.policy, self.activation, value)
        self.assertEqual(result["decision"], "needs_human")
        self.assertIn("denied_path", result["reason_codes"])

    def test_builder_risk_claim_cannot_expand_policy(self) -> None:
        value = bundle(self.policy)
        value["files"][0]["path"] = "application/db/models.py"
        value["objective"]["allowed_paths"] = ["application/db/models.py"]
        value["objective"]["risk_profile"] = "low"
        value["reviewer_report"]["objective_hash"] = content_hash(value["objective"])
        result = evaluate(self.policy, self.activation, value)
        self.assertEqual(result["decision"], "needs_human")

    def test_reviewer_pass_never_overrides_failed_ci(self) -> None:
        value = bundle(self.policy)
        value["checks"][self.policy["required_checks"][0]] = "failure"
        result = evaluate(self.policy, self.activation, value)
        self.assertEqual(result["decision"], "blocked")

    def test_new_head_invalidates_old_review(self) -> None:
        value = bundle(self.policy)
        value["head_sha"] = "c" * 40
        result = evaluate(self.policy, self.activation, value)
        self.assertEqual(result["decision"], "blocked")
        self.assertIn("review_head_mismatch", result["reason_codes"])

    def test_diff_limits_escalate(self) -> None:
        value = bundle(self.policy)
        value["files"][0]["additions"] = 201
        self.assertEqual(
            evaluate(self.policy, self.activation, value)["decision"], "needs_human"
        )

    def test_existing_test_cannot_be_weakened(self) -> None:
        value = bundle(self.policy)
        value["files"][1]["status"] = "modified"
        result = evaluate(self.policy, self.activation, value)
        self.assertEqual(result["decision"], "needs_human")
        self.assertIn("protected_path_requires_addition", result["reason_codes"])

    def test_exhausted_objective_budget_escalates(self) -> None:
        value = bundle(self.policy)
        value["attempt"] = 4
        result = evaluate(self.policy, self.activation, value)
        self.assertEqual(result["decision"], "needs_human")
        self.assertIn("budget_exhausted", result["reason_codes"])

    def test_policy_file_hash_is_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            policy_path = Path(directory) / "policy.json"
            active_path = Path(directory) / "active.json"
            policy_path.write_text(
                POLICY_PATH.read_text(encoding="utf-8") + "\n", encoding="utf-8"
            )
            active_path.write_text(
                ACTIVE_PATH.read_text(encoding="utf-8"), encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "hash"):
                load_active_policy(policy_path, active_path)

    def test_decision_is_reproducible(self) -> None:
        first = evaluate(self.policy, self.activation, bundle(self.policy))
        second = evaluate(
            self.policy, self.activation, copy.deepcopy(bundle(self.policy))
        )
        self.assertEqual(first, second)
        self.assertEqual(
            json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True)
        )

    def test_shadow_evaluation_never_uses_the_active_enforcement_mode(self) -> None:
        result = evaluate_shadow(self.policy, self.activation, bundle(self.policy))
        self.assertEqual(result["decision"], "eligible")
        self.assertEqual(result["enforcement_mode"], "shadow")
        self.assertEqual(self.activation["mode"], "enforced")

    def test_shadow_bundle_uses_existing_evidence_without_sdk_or_merge(self) -> None:
        value = bundle(self.policy)
        binding = {"schema_version": 1, "change_id": "change-1", "candidate_id": "c" * 64,
                   "base_sha": BASE, "patch_sha256": "d" * 64, "head_sha": HEAD,
                   "verification_result": "matched", "evidence_refs": ["remote:diff"], "verified_at": "2026-08-31T10:00:00Z"}
        validation = {"schema_version": 1, "change_id": "change-1", "attempt": 1,
                      "candidate_id": "c" * 64, "result": "pass", "evidence_refs": ["ci:test"], "validated_at": "2026-08-31T10:00:00Z"}
        pr = {key: value[key] for key in ("pr_number", "author", "base_branch", "base_sha", "head_sha", "draft", "mergeable", "external_state", "attempt", "elapsed_seconds")}
        built = bundle_from_s2_evidence(objective=value["objective"], validation=validation,
            reviewer_report=value["reviewer_report"], binding=binding, pr=pr, files=value["files"],
            checks=value["checks"], policy_source_commit=value["policy_source_commit"], evaluated_at=value["evaluated_at"])
        self.assertEqual(evaluate_shadow(self.policy, self.activation, built)["enforcement_mode"], "shadow")
        broken = dict(pr); broken["head_sha"] = "e" * 40
        with self.assertRaisesRegex(ValueError, "binding"):
            bundle_from_s2_evidence(objective=value["objective"], validation=validation, reviewer_report=value["reviewer_report"], binding=binding, pr=broken, files=value["files"], checks=value["checks"], policy_source_commit=value["policy_source_commit"], evaluated_at=value["evaluated_at"])
        bad_validation = dict(validation); bad_validation["candidate_id"] = "e" * 64
        with self.assertRaisesRegex(ValueError, "candidate"):
            bundle_from_s2_evidence(objective=value["objective"], validation=bad_validation, reviewer_report=value["reviewer_report"], binding=binding, pr=pr, files=value["files"], checks=value["checks"], policy_source_commit=value["policy_source_commit"], evaluated_at=value["evaluated_at"])
        bad_pr = dict(pr); bad_pr["attempt"] = 2
        with self.assertRaisesRegex(ValueError, "attempt"):
            bundle_from_s2_evidence(objective=value["objective"], validation=validation, reviewer_report=value["reviewer_report"], binding=binding, pr=bad_pr, files=value["files"], checks=value["checks"], policy_source_commit=value["policy_source_commit"], evaluated_at=value["evaluated_at"])
