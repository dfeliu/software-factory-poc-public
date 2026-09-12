+++
id = "S2"
title = "Filtres combinables d'incidències"
status = "ready-for-execution"
architecture = "F"
project = "incidents-api"
input_kind = "documented-functional-change"
repetitions = 5
observation_protocol = "fixed-repetitions"
+++

# S2 — Filtres combinables d'incidències

## Immutable starting state

Use the pinned incidents-api base commit and its existing schema/migration history in a fresh disposable Forgejo namespace. Seed the same versioned test dataset for every repetition: active and soft-deleted records covering each supported `status` and `priority`, with stable IDs and timestamps. The expected contract and fixture dataset are read-only inputs.

## Controlled input

Request optional, independently combinable `status` and `priority` filters for `GET /incidents`, preserving stable order and excluding records with non-null `deleted_at`. Require the smallest implementation, tests, documentation, and migration only if the model needs one.

## Terminal condition

One PR contains the change; all single-filter, combined-filter, empty-result, stable-order, and soft-delete cases pass against PostgreSQL; lint/security checks pass; and no merge occurs. A failure to reproduce the declared dataset or contract is a terminal setup failure, not a result.

## Expected evidence

Capture the pinned commit/dataset identifier, request matrix and responses, SQL/query evidence, unit/integration test logs, migration decision, PR/pipeline IDs, timestamps, and run-record fields. Record `deployment_success = N/A` because deployment is not attempted.

## Human-intervention counting

Count distinct human clarifications, rerun approvals, or manual recovery actions. Dataset loading and planned review are not interventions; manual code changes after the request are not allowed.

## Cleanup and isolation

Use a fresh database/schema, repository namespace, branch, and workspace per repetition. Preserve evidence, then remove only disposable data/artifacts. Do not modify the shared project, infrastructure, Proxmox, production, or mirror.
