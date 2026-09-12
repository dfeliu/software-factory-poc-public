"""Replay immutable G2 events into a non-authoritative PostgreSQL read model."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from .events import EventStore


def project_event(connection: Any, event: dict[str, Any]) -> bool:
    event_id = event["event_id"]
    event_type = event["event_type"]
    occurred_at = event["occurred_at"]
    payload = event["payload"]
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO audit_events(event_id,event_type,occurred_at,payload) "
            "VALUES (%s,%s,%s,%s::jsonb) ON CONFLICT DO NOTHING RETURNING event_id",
            (event_id, event_type, occurred_at, json.dumps(payload)),
        )
        inserted = cursor.fetchone() is not None
        if not inserted:
            return False
        if event_type == "change_received":
            cursor.execute(
                "INSERT INTO change_runs(change_id,repository,objective_hash,phase,started_at,"
                "updated_at,payload) VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb) ON CONFLICT DO NOTHING",
                (
                    payload["change_id"],
                    payload["repository"],
                    payload["objective_hash"],
                    payload["phase"],
                    payload["started_at"],
                    occurred_at,
                    json.dumps(payload),
                ),
            )
        elif event_type == "attempt_started":
            cursor.execute(
                "INSERT INTO change_attempts(event_id,change_id,attempt,occurred_at,payload) "
                "VALUES (%s,%s,%s,%s,%s::jsonb) ON CONFLICT DO NOTHING",
                (
                    event_id,
                    payload["change_id"],
                    payload["attempt"],
                    occurred_at,
                    json.dumps(payload),
                ),
            )
        elif event_type == "review_recorded":
            cursor.execute(
                "INSERT INTO review_reports(event_id,change_id,head_sha,result,occurred_at,payload) "
                "VALUES (%s,%s,%s,%s,%s,%s::jsonb) ON CONFLICT DO NOTHING",
                (
                    event_id,
                    payload["change_id"],
                    payload["head_sha"],
                    payload["result"],
                    occurred_at,
                    json.dumps(payload),
                ),
            )
        elif event_type == "policy_decided":
            cursor.execute(
                "INSERT INTO policy_revisions(policy_id,policy_revision,policy_sha256,"
                "governance_profile,observed_at,payload) VALUES (%s,%s,%s,%s,%s,%s::jsonb) "
                "ON CONFLICT DO NOTHING",
                (
                    payload["policy_id"],
                    payload["policy_revision"],
                    payload["policy_sha256"],
                    payload["governance_profile"],
                    occurred_at,
                    json.dumps(payload),
                ),
            )
            cursor.execute(
                "INSERT INTO policy_decisions(decision_id,change_id,head_sha,decision,policy_id,"
                "policy_revision,occurred_at,payload) VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb) "
                "ON CONFLICT DO NOTHING",
                (
                    payload["decision_id"],
                    payload["change_id"],
                    payload["head_sha"],
                    payload["decision"],
                    payload["policy_id"],
                    payload["policy_revision"],
                    occurred_at,
                    json.dumps(payload),
                ),
            )
        elif event_type == "merge_completed":
            cursor.execute(
                "INSERT INTO merge_events(event_id,change_id,repository,pr_number,head_sha,"
                "occurred_at,payload) VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb) ON CONFLICT DO NOTHING",
                (
                    event_id,
                    payload["change_id"],
                    payload["repository"],
                    payload["pr_number"],
                    payload["head_sha"],
                    occurred_at,
                    json.dumps(payload),
                ),
            )
        elif event_type == "control_paused":
            cursor.execute(
                "INSERT INTO control_state(scope,repository,paused,reason_code,actor,updated_at) "
                "VALUES (%s,%s,true,%s,%s,%s) ON CONFLICT(scope,repository) DO UPDATE SET "
                "paused=true,reason_code=EXCLUDED.reason_code,actor=EXCLUDED.actor,updated_at=EXCLUDED.updated_at",
                (
                    payload["scope"],
                    payload.get("repository") or "",
                    payload["reason_code"],
                    payload["actor"],
                    payload["updated_at"],
                ),
            )
        phase = None
        if event_type == "attempt_started":
            phase = "BUILDING"
        elif event_type == "review_recorded":
            phase = {
                "pass": "CANDIDATE_VIABLE",
                "fail": "REWORKING",
                "needs_human": "NEEDS_ATTENTION",
            }.get(payload.get("result"))
        elif event_type == "pr_attached":
            phase = "VALIDATING_REMOTE"
        elif event_type == "policy_decided":
            phase = {
                "eligible": "ELIGIBLE",
                "blocked": "REWORKING",
                "needs_human": "NEEDS_ATTENTION",
            }.get(payload.get("decision"))
        elif event_type == "merge_completed":
            phase = "COMPLETED"
        elif event_type in {"merge_outcome_ambiguous", "budget_exhausted"}:
            phase = "NEEDS_ATTENTION"
        if phase is not None and payload.get("change_id"):
            cursor.execute(
                "UPDATE change_runs SET phase=%s,updated_at=%s,payload=payload || %s::jsonb "
                "WHERE change_id=%s",
                (phase, occurred_at, json.dumps(payload), payload["change_id"]),
            )
    return True


def project_all(connection: Any, store: EventStore) -> int:
    count = 0
    for event in store.iter_events():
        with connection.transaction():
            if project_event(connection, event):
                count += 1
                with connection.cursor() as cursor:
                    cursor.execute(
                        "INSERT INTO projection_cursors(projector,last_event_id) VALUES ('g2',%s) "
                        "ON CONFLICT(projector) DO UPDATE SET last_event_id=EXCLUDED.last_event_id,"
                        "updated_at=now()",
                        (event["event_id"],),
                    )
    return count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-root", required=True, type=Path)
    parser.add_argument("--migration", type=Path)
    args = parser.parse_args(argv)
    dsn = os.environ.get("G2_POSTGRES_DSN")
    if not dsn:
        parser.error("G2_POSTGRES_DSN is required")
    try:
        import psycopg
    except ImportError as exc:
        raise SystemExit(
            "psycopg is required only by the PostgreSQL projector"
        ) from exc
    migration = args.migration or Path(__file__).with_name("postgres") / "001_init.sql"
    with psycopg.connect(dsn) as connection:
        connection.execute(migration.read_text(encoding="utf-8"))
        count = project_all(connection, EventStore(args.evidence_root))
    print(json.dumps({"projected_events": count}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
