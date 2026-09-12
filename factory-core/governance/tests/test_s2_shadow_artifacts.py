from __future__ import annotations

import builtins
import copy
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from agentic.g2_shadow import normalize_s2_artifacts  # noqa: E402
from governance.contracts import candidate_id, content_hash, patch_sha256  # noqa: E402
from governance.policy import evaluate_shadow, load_active_policy  # noqa: E402


class S2ShadowArtifactTests(unittest.TestCase):
    def setUp(self) -> None:
        policy_root = ROOT / "policies" / "enforcement"
        self.policy, self.activation = load_active_policy(
            policy_root / "g2-disposable-v1.json", policy_root / "active.json"
        )
        self.base = "a" * 40
        self.head = "b" * 40
        self.patch = "+candidate\n"
        self.candidate = candidate_id(self.base, self.patch)
        self.objective = {
            "schema_version": 1,
            "change_id": "s2-r01-filters",
            "repository": "dfeliu/s2-qualification-20260904-r01",
            "base_sha": self.base,
            "goal": "S2 optional incident filters",
            "acceptance_criteria": ["filters combine"],
            "allowed_paths": ["application/api/incidents.py"],
            "budgets": {"max_attempts": 3, "max_elapsed_seconds": 2700},
            "risk_profile": "G0-s2-v1",
        }

    def write_artifacts(self, directory: Path) -> None:
        reviewed_at = "2026-09-04T10:01:00Z"
        finished_at = "2026-09-04T10:02:00Z"
        artifacts = {
            "objective.json": self.objective,
            "validation.json": {
                "schema_version": 1,
                "stage": "deterministic_validation",
                "attempt": 2,
                "result": "pass",
                "exit_code": 0,
                "diagnostic": "S2 validation passed",
            },
            "reviewer.json": {
                "review": {
                    "schema_version": 1,
                    "change_id": self.objective["change_id"],
                    "attempt": 2,
                    "objective_hash": content_hash(self.objective),
                    "candidate_id": self.candidate,
                    "model": "gpt-5.6-luna",
                    "prompt_version": "agentic-reviewer-v1",
                    "result": "pass",
                    "findings": [],
                    "evidence_refs": ["candidate.patch"],
                    "reviewed_at": reviewed_at,
                },
                "invocation": {
                    "requested_model": "gpt-5.6-luna",
                    "effective_model": "gpt-5.6-luna",
                    "effort": "medium",
                    "fallback_reason": None,
                    "thread_id": "thread-reviewer-r01",
                },
            },
            "publish.json": {
                "repository": self.objective["repository"],
                "branch": "codex/s2-r01",
                "commit": self.head,
                "pr_url": "https://forgejo.invalid/dfeliu/s2-qualification-20260904-r01/pulls/7",
                "reviewer_requested": "dfeliu",
            },
            "summary.json": {
                "run_id": "r01",
                "repository": self.objective["repository"],
                "candidate_id": self.candidate,
                "attempt": 2,
                "started_at": "2026-09-04T10:00:00Z",
                "finished_at": finished_at,
                "duration_seconds": 120,
                "models_efforts": "unavailable: retained in builder.json and reviewer.json invocation evidence",
                "consumption": "unavailable: SDK does not report consumption in this contract",
                "validation": "pass",
                "reviewer": "pass",
                "binding_verified": True,
                "branch": "codex/s2-r01",
                "head_sha": self.head,
                "pr_url": "https://forgejo.invalid/dfeliu/s2-qualification-20260904-r01/pulls/7",
            },
        }
        for name, value in artifacts.items():
            (directory / name).write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
        (directory / "candidate.patch").write_text(self.patch, encoding="utf-8", newline="\n")
        (directory / "remote.patch").write_text(self.patch, encoding="utf-8", newline="\n")

    def normalize(self, directory: Path) -> dict[str, object]:
        pr = {
            "pr_number": 7,
            "author": "factory-agent",
            "base_branch": "main",
            "base_sha": self.base,
            "head_sha": self.head,
            "draft": False,
            "mergeable": True,
            "external_state": "clear",
            "attempt": 2,
            "elapsed_seconds": 120,
        }
        files = [{
            "path": "application/api/incidents.py",
            "status": "modified",
            "additions": 1,
            "deletions": 0,
            "binary": False,
            "symlink": False,
            "mode_changed": False,
        }]
        checks = {name: "success" for name in self.policy["required_checks"]}
        imported: list[str] = []
        real_import = builtins.__import__

        def guarded_import(name: str, *args: object, **kwargs: object) -> object:
            imported.append(name)
            if name == "openai_codex" or name.startswith("agentic.sdk"):
                raise AssertionError("S2 shadow normalization imported the SDK")
            return real_import(name, *args, **kwargs)

        with (
            mock.patch("builtins.__import__", side_effect=guarded_import),
            mock.patch.object(socket, "create_connection", side_effect=AssertionError("network call")),
            mock.patch.object(subprocess, "run", side_effect=AssertionError("process or merge call")),
        ):
            result = normalize_s2_artifacts(
                directory,
                pr=pr,
                files=files,
                checks=checks,
                policy_source_commit="c" * 40,
                evaluated_at="2026-09-04T10:03:00Z",
            )
        self.assertFalse(any(name == "openai_codex" or name.startswith("agentic.sdk") for name in imported))
        return result

    def test_real_s2_artifacts_produce_bound_shadow_needs_human(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            self.write_artifacts(directory)
            normalized = self.normalize(directory)

        binding = normalized["binding"]
        report = normalized["reviewer_report"]
        validation = normalized["validation"]
        bundle = normalized["bundle"]
        self.assertEqual(bundle["change_id"], self.objective["change_id"])
        self.assertEqual(binding["candidate_id"], self.candidate)
        self.assertEqual(validation["candidate_id"], self.candidate)
        self.assertEqual(report["candidate_id"], self.candidate)
        self.assertEqual(bundle["attempt"], 2)
        self.assertEqual(binding["base_sha"], self.base)
        self.assertEqual(binding["patch_sha256"], patch_sha256(self.patch))
        self.assertEqual(binding["head_sha"], self.head)
        self.assertEqual(report["head_sha"], self.head)
        self.assertEqual(report["candidate_binding_ref"], content_hash(binding))

        activation_before = copy.deepcopy(self.activation)
        decision = evaluate_shadow(self.policy, self.activation, bundle)
        self.assertEqual(decision["decision"], "needs_human")
        self.assertEqual(decision["enforcement_mode"], "shadow")
        self.assertEqual(self.activation, activation_before)

    def test_remote_patch_mismatch_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            self.write_artifacts(directory)
            (directory / "remote.patch").write_text("+other\n", encoding="utf-8", newline="\n")
            with self.assertRaisesRegex(ValueError, "remote patch differs"):
                self.normalize(directory)


if __name__ == "__main__":
    unittest.main()
