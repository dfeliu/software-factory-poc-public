+++
id = "S7"
title = "Concurrència i cues"
status = "ready-for-execution"
architecture = "F"
project = "incidents-api"
input_kind = "bounded-independent-requests"
repetitions = 5
observation_protocol = "minimum-five-trials-per-load-case; extend-in-blocks-of-five-if-collisions-or-mixed-outcomes"
+++

# S7 — Concurrència i cues

## Immutable starting state

Start each trial from the same pinned base commit and workflow revision, with two independent disposable branches/workspaces (`A` and `B`), unique correlation IDs, bounded test-only runner capacity, and a declared queue/concurrency limit. No request may target protected main directly.

## Controlled input

Submit two independent, non-overlapping S1-compatible requests simultaneously, then repeat the trial with the declared queue limit and the same inputs. Do not add a third request, retry manually, resolve conflicts, merge, deploy, or modify infrastructure during the observation.

## Terminal condition

Both requests reach separate valid PRs, or the configured queue/rejection behavior reaches a documented terminal outcome within the timeout. Success requires no cross-branch contamination, lost request, duplicate PR, unbounded resource use, or unsafe bypass.

## Expected evidence

Capture submission/order timestamps, correlation/workflow/pipeline/PR IDs, branch and workspace mapping, queue wait, execution duration, resource observations, collisions, retries, recovery, and final isolation checks. Report per-request and trial-level outcomes; do not infer success from one request completing.

## Human-intervention counting

Count distinct human actions needed to resolve an unexpected collision, stuck queue, or failed recovery. Scheduled observation and evidence review are not interventions. Manual conflict resolution is prohibited and, if required, is a failed safety outcome.

## Cleanup and isolation

Use disposable branches, workspaces, containers, and test-only runner capacity. Preserve logs before cleaning those artifacts. Do not use destructive Proxmox actions, production deployment, automatic merge, shared state, or real mirror targets.
