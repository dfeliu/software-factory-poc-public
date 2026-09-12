+++
id = "S5B"
title = "Resiliència de la factory"
status = "ready-for-execution"
architecture = "F"
project = "incidents-api"
input_kind = "controlled-interruption"
repetitions = 5
observation_protocol = "minimum-five-trials-per-interruption-case; extend-in-blocks-of-five-if-mixed"
+++

# S5B — Resiliència de la factory

## Immutable starting state

Start each trial from a pinned clean commit with one disposable namespace, one unique run ID, and the pre-created F workflow. Select exactly one interruption case before the trial: cancel the disposable workflow after its first durable checkpoint, stop the disposable agent process, or make the test runner lease unavailable. The operator must not alter Forgejo data, permissions, infrastructure configuration, Proxmox, production, or the protected branch.

## Controlled input

Submit the fixed S1 change, inject the selected interruption once at the declared checkpoint, then restore only the disposable execution capacity. Allow the configured retry/recovery behavior to proceed. No manual code edit, duplicate submission, merge, or deployment is allowed.

## Terminal condition

The run reaches a valid PR with at most the declared recovery attempts, or reaches a documented terminal failure after the retry limit/timeout. A successful recovery must preserve state, avoid duplicate commits/PRs, and produce one auditable run lineage.

## Expected evidence

Capture checkpoint and interruption timestamps, attempt/workflow IDs, persisted state, retry decisions, recovery duration, final commit/PR count, logs, and run record. Classify recovery as automatic only when `human_interventions = 0`; unavailable managed-ChatGPT token/cost fields remain `N/A`.

## Human-intervention counting

Count each human action that changes execution or state. Merely injecting the predeclared interruption and observing recovery is not an intervention; an unplanned manual restart or repair is.

## Cleanup and isolation

Use disposable runner/workspace leases and test-only branches. Revoke/expire only trial artifacts after evidence capture. No destructive Proxmox operation, production deployment, automatic merge, or infrastructure reconfiguration is permitted.
