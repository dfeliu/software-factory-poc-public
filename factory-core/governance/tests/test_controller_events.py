from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from governance.contracts import content_hash  # noqa: E402
from governance.controller import ChangeController  # noqa: E402
from governance.events import EventStore  # noqa: E402

HEAD = "b" * 40
BASE = "a" * 40


def objective() -> dict:
    return {
        "schema_version": 1,
        "change_id": "change-1",
        "repository": "dfeliu/g2-qualification-r1",
        "base_sha": BASE,
        "goal": "Fix regression",
        "acceptance_criteria": ["tests pass"],
        "allowed_paths": ["application/api/incidents.py", "tests/integration/**"],
        "budgets": {"max_attempts": 3, "max_elapsed_seconds": 2700},
        "risk_profile": "G2-disposable-v1",
    }


def report(obj: dict, head: str = HEAD) -> dict:
    return {
        "schema_version": 1,
        "change_id": "change-1",
        "attempt": 1,
        "head_sha": head,
        "objective_hash": content_hash(obj),
        "model": "test-model",
        "prompt_version": "reviewer-v1",
        "result": "pass",
        "findings": [],
        "evidence_refs": [],
        "reviewed_at": "2026-08-31T10:00:00Z",
    }


class ControllerEventTests(unittest.TestCase):
    def test_review_head_does_not_replace_a_newer_current_head(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            controller = ChangeController(Path(directory), objective())
            current_head = "c" * 40
            controller.begin_attempt(head_sha=current_head)
            controller.record_review(report(objective(), head=HEAD))
            self.assertEqual(controller.state["review_head_sha"], HEAD)
            self.assertEqual(controller.state["head_sha"], current_head)

    def test_one_change_keeps_one_pull_request_and_invalidates_changed_head(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            controller = ChangeController(Path(directory), objective())
            controller.begin_attempt()
            controller.record_review(report(objective()))
            controller.attach_pr(number=7, url="http://forgejo/pulls/7", head_sha=HEAD)
            controller.attach_pr(
                number=7, url="http://forgejo/pulls/7", head_sha="c" * 40
            )
            self.assertIsNone(controller.state["review_head_sha"])
            with self.assertRaisesRegex(ValueError, "second pull request"):
                controller.attach_pr(
                    number=8, url="http://forgejo/pulls/8", head_sha=HEAD
                )

    def test_event_files_are_immutable_and_replayable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = EventStore(Path(directory))
            store.append(
                "attempt_started",
                {"change_id": "change-1", "attempt": 1},
                event_id="event-1",
            )
            if os.name != "nt":
                self.assertEqual(
                    (store.events / "event-1.json").stat().st_mode & 0o777, 0o640
                )
            with self.assertRaises(FileExistsError):
                store.append(
                    "attempt_started",
                    {"change_id": "change-1", "attempt": 2},
                    event_id="event-1",
                )
            self.assertEqual(
                [event["event_id"] for event in store.iter_events()], ["event-1"]
            )

    def test_eligible_decision_can_expire_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            controller = ChangeController(Path(directory), objective())
            controller.begin_attempt(head_sha=HEAD)
            controller.attach_pr(number=7, url="http://forgejo/pulls/7", head_sha=HEAD)
            decision = {
                "change_id": "change-1",
                "head_sha": HEAD,
                "decision_id": "decision-1",
                "decision": "eligible",
                "expires_at": "2026-09-01T00:00:00Z",
            }
            controller.record_decision(decision)
            controller.mark_expired(decision)
            self.assertEqual(controller.state["phase"], "EXPIRED")
            self.assertEqual(
                [event["event_type"] for event in controller.store.iter_events()][-1],
                "decision_expired",
            )

    def test_concurrent_event_creation_never_overwrites(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = EventStore(Path(directory))

            def append(attempt: int) -> str:
                try:
                    store.append(
                        "attempt_started",
                        {"change_id": "change-1", "attempt": attempt},
                        event_id="same-event",
                    )
                    return "created"
                except FileExistsError:
                    return "exists"

            with ThreadPoolExecutor(max_workers=2) as pool:
                outcomes = list(pool.map(append, (1, 2)))
            self.assertEqual(sorted(outcomes), ["created", "exists"])
            self.assertEqual(len(list(store.iter_events())), 1)

    def test_evidence_rejects_secret_fields(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            self.assertRaisesRegex(ValueError, "sensitive"),
        ):
            EventStore(Path(directory)).append("bad", {"token": "must-not-persist"})

    def test_repository_and_global_pause_are_restrict_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = EventStore(Path(directory))
            self.assertFalse(store.paused("dfeliu/repo"))
            store.set_pause(
                scope="repository",
                repository="dfeliu/repo",
                reason_code="regression",
                actor="operator",
            )
            self.assertTrue(store.paused("dfeliu/repo"))
            self.assertFalse(store.paused("dfeliu/other"))
            store.set_pause(
                scope="global",
                repository=None,
                reason_code="governance_integrity",
                actor="operator",
            )
            self.assertTrue(store.paused("dfeliu/other"))
            with self.assertRaisesRegex(ValueError, "cannot name"):
                store.set_pause(
                    scope="global",
                    repository="dfeliu/repo",
                    reason_code="invalid",
                    actor="operator",
                )

    def test_state_contains_no_raw_objective_text(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            controller = ChangeController(Path(directory), objective())
            state = json.loads(controller.state_path.read_text(encoding="utf-8"))
            self.assertNotIn("goal", state)
