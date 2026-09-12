+++
id = "S1"
title = "Golden Path net"
status = "ready-for-execution"
architecture = "F"
project = "incidents-api"
input_kind = "short-api-specification"
repetitions = 5
observation_protocol = "fixed-repetitions"
+++

# S1 — Golden Path net

## Immutable starting state

Use the pinned clean Golden Path base commit for `incidents-api`, an empty disposable Forgejo repository namespace, the approved factory-core revision, and the pre-created F workflow/permissions configuration. The specification below and this fixture revision are inputs, not editable run state.

## Controlled input

Ask the factory to produce the documented containerized FastAPI Golden Path for:

- `GET /health` returning the service health contract;
- `GET /incidents` returning the documented empty collection;
- `POST /incidents` validating the documented incident fields;
- Dockerfile, compose file, tests, lint, healthcheck, minimal documentation, and Forgejo pipeline adapter.

The Forgejo pipeline adapter is part of the requested artifact and must remain
self-contained for the disposable F4 runner:

- all its jobs use the F4 runner label `ubuntu-latest`;
- before every test command that loads application configuration and before
  every `docker compose` command, it creates `.env` from `.env.example` inside
  the ephemeral CI workspace; and
- it removes that generated `.env` in an `always`/cleanup step. The example
  values are test-only placeholders, never a production credential or a
  repository secret.

No additional requirements, network services, credentials, or production targets are permitted.

## Terminal condition

The factory opens one PR from its disposable branch; required CI completes successfully; the repository contains the requested artifacts; and a human reviewer can inspect the PR without merging it. The run ends on success or on the first terminal failure/timeout.

## Expected evidence

Capture the base/final commit, prompt/specification, PR and pipeline IDs, CI logs, test/lint/security evidence, artifact manifest, timestamps, actor identities, and the run record fields mapped by `benchmarks/reports/forgejo-native.md`. Record `pr_accepted = N/A` because no acceptance is performed.

## Human-intervention counting

Count each distinct human action required to unblock or complete the run, including clarification, rerun approval, credential/configuration repair, or manual recovery. Do not count scheduled observation or the final evidence review. A human merge is prohibited.

## Cleanup and isolation

Delete or expire only disposable branches, PRs, workspaces, containers, and test artifacts after evidence capture. Preserve logs and the run record. Do not touch shared infrastructure, protected main, production, or a real mirror.
