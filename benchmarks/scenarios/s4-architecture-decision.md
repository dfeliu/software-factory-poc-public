+++
id = "S4"
title = "Decisió arquitectònica preseleccionada"
status = "ready-for-execution"
architecture = "F"
project = "incidents-api"
input_kind = "preselected-architecture-requirement"
repetitions = 5
observation_protocol = "fixed-repetitions"
+++

# S4 — Decisió arquitectònica preseleccionada

## Immutable starting state

Use the pinned Golden Path base commit and the pre-approved decision brief: PostgreSQL persistence remains synchronous and repository-local, with no new orchestration, vector database, Neo4j, or external runtime. The ADR template, factory-core standards, and existing ADR revisions are pinned read-only.

## Controlled input

Request an implementation of the incident persistence extension under that brief. The change must state the selected alternative, rejected alternatives, boundaries, failure modes, migration impact, and validation plan in an ADR, then implement only the selected synchronous design in the disposable branch.

## Terminal condition

One PR contains the ADR and implementation; the ADR is internally consistent with the code and stated constraints; required tests, lint, and security checks pass; and no out-of-scope technology or permission change is introduced. No merge occurs.

## Expected evidence

Capture the decision brief, ADR diff, implementation diff, standards/ADR references, validation logs, PR/pipeline IDs, and reviewer checklist. Record whether the decision is complete, coherent, and validated; record unavailable cost/token values as `N/A`.

## Human-intervention counting

Count distinct human clarifications, constraint changes, manual reruns, or recovery actions. A scheduled review of the ADR is not an intervention; approval or merge is not performed in this fixture.

## Cleanup and isolation

Retain the PR and evidence in the disposable test namespace until the review record is archived, then remove only disposable branches/workspaces/artifacts. Do not alter existing ADRs or infrastructure.
