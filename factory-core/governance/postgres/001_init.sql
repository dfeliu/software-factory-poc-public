BEGIN;

CREATE TABLE IF NOT EXISTS policy_revisions (
    policy_id text NOT NULL,
    policy_revision integer NOT NULL CHECK (policy_revision > 0),
    policy_sha256 text NOT NULL CHECK (policy_sha256 ~ '^[0-9a-f]{64}$'),
    governance_profile text NOT NULL,
    observed_at timestamptz NOT NULL,
    payload jsonb NOT NULL,
    PRIMARY KEY (policy_id, policy_revision, policy_sha256)
);

CREATE TABLE IF NOT EXISTS change_runs (
    change_id text PRIMARY KEY,
    repository text,
    objective_hash text,
    phase text,
    started_at timestamptz,
    updated_at timestamptz,
    payload jsonb NOT NULL
);

CREATE TABLE IF NOT EXISTS change_attempts (
    event_id text PRIMARY KEY,
    change_id text NOT NULL,
    attempt integer NOT NULL CHECK (attempt > 0),
    occurred_at timestamptz NOT NULL,
    payload jsonb NOT NULL
);

CREATE TABLE IF NOT EXISTS review_reports (
    event_id text PRIMARY KEY,
    change_id text NOT NULL,
    head_sha text NOT NULL,
    result text NOT NULL,
    occurred_at timestamptz NOT NULL,
    payload jsonb NOT NULL
);

CREATE TABLE IF NOT EXISTS policy_decisions (
    decision_id text PRIMARY KEY,
    change_id text NOT NULL,
    head_sha text NOT NULL,
    decision text NOT NULL,
    policy_id text NOT NULL,
    policy_revision integer NOT NULL,
    occurred_at timestamptz NOT NULL,
    payload jsonb NOT NULL
);

CREATE TABLE IF NOT EXISTS merge_events (
    event_id text PRIMARY KEY,
    change_id text NOT NULL,
    repository text NOT NULL,
    pr_number integer NOT NULL,
    head_sha text NOT NULL,
    occurred_at timestamptz NOT NULL,
    payload jsonb NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_events (
    event_id text PRIMARY KEY,
    event_type text NOT NULL,
    occurred_at timestamptz NOT NULL,
    payload jsonb NOT NULL
);

CREATE TABLE IF NOT EXISTS projection_cursors (
    projector text PRIMARY KEY,
    last_event_id text,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS control_state (
    scope text NOT NULL,
    repository text NOT NULL DEFAULT '',
    paused boolean NOT NULL,
    reason_code text NOT NULL,
    actor text NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (scope, repository)
);

COMMIT;
