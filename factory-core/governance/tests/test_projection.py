from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from governance.projection import project_event  # noqa: E402


class FakeCursor:
    def __init__(self, connection):
        self.connection = connection
        self.inserted = False

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, sql, params):
        self.connection.calls.append((" ".join(sql.split()), params))
        if sql.startswith("INSERT INTO audit_events"):
            event_id = params[0]
            self.inserted = event_id not in self.connection.seen
            self.connection.seen.add(event_id)

    def fetchone(self):
        return ("inserted",) if self.inserted else None


class FakeConnection:
    def __init__(self):
        self.calls = []
        self.seen = set()

    def cursor(self):
        return FakeCursor(self)


class ProjectionTests(unittest.TestCase):
    def test_projection_is_idempotent_and_keeps_generic_audit_event(self) -> None:
        event = {
            "event_id": "event-1",
            "event_type": "attempt_started",
            "occurred_at": "2026-08-31T10:00:00Z",
            "payload": {"change_id": "change-1", "attempt": 1},
        }
        connection = FakeConnection()
        self.assertTrue(project_event(connection, event))
        first_call_count = len(connection.calls)
        self.assertFalse(project_event(connection, event))
        self.assertEqual(len(connection.calls), first_call_count + 1)
        self.assertIn("INSERT INTO change_attempts", connection.calls[1][0])
        self.assertIn("UPDATE change_runs SET phase", connection.calls[2][0])
        self.assertEqual(connection.calls[2][1][0], "BUILDING")

    def test_migration_contains_all_required_read_model_tables(self) -> None:
        sql = (ROOT / "governance" / "postgres" / "001_init.sql").read_text(
            encoding="utf-8"
        )
        for table in (
            "policy_revisions",
            "change_runs",
            "change_attempts",
            "review_reports",
            "policy_decisions",
            "merge_events",
            "audit_events",
            "projection_cursors",
            "control_state",
        ):
            self.assertIn(f"CREATE TABLE IF NOT EXISTS {table}", sql)
