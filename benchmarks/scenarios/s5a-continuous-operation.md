+++
id = "S5A"
title = "Operació contínua"
status = "ready-for-execution"
architecture = "F"
project = "incidents-api"
input_kind = "bounded-change-sequence"
repetitions = 5
observation_protocol = "fixed-repetitions"
+++

# S5A — Operació contínua

## Immutable starting state

Start every repetition from the same pinned clean commit, workflow revision, factory-core revision, and empty disposable namespace. Use the fixed ordered change sequence `C1` health-response documentation, `C2` incident response-schema refinement, and `C3` test-only edge-case coverage. The sequence, order, and acceptance criteria are immutable.

## Controlled input

Submit C1, C2, and C3 as three separate small requests against the same disposable project, waiting for the preceding request's terminal condition before submitting the next. Each request must be independently reviewable and must not modify permissions, infrastructure, production configuration, or protected main.

## Terminal condition

All three changes have separate PRs with successful required CI, no duplicate or lost change, and a clean disposable workspace after the sequence. The run ends at the first failed change, unrecoverable state, timeout, or safety violation.

## Expected evidence

Capture per-change and aggregate timestamps, commits, PR/pipeline IDs, test/lint/security logs, retries, recovery time, human actions, and evidence of no duplicate PR/change. Report per-iteration duration and the aggregate success/valid-change outcome.

## Human-intervention counting

Count distinct human actions per change and in aggregate; a planned review/observation is not counted. Any manual conflict resolution or rerun approval is counted and described.

## Cleanup and isolation

Use one isolated namespace per repetition and preserve its complete evidence. Remove only disposable branches, PRs, workspaces, and containers after capture; never merge or touch shared/prod state.
