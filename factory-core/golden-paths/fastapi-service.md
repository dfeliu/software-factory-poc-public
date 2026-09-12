# Golden Path: fastapi-service

## Purpose and use cases

`fastapi-service` is the initial Golden Path for small and medium private HTTP API services with relational persistence. It is the common contract for the future service template and for the `incidents-api` benchmark.

It is intended for CRUD APIs, internal services and backends that need a reproducible local environment, deterministic validation and a reviewable deployment path. It is not a general-purpose application platform.

## Normative terms

- **MUST** and **MUST NOT** identify mandatory requirements for a generated project.
- **SHOULD** and **SHOULD NOT** identify recommended practices that may be varied with documented justification.
- **DEFERRED** identifies a decision intentionally not made by this Golden Path.

## Approved stack

The following stack is already established by `POC-PLAN.md` and is mandatory for a project following this Golden Path:

| Capability | Approved technology |
|---|---|
| Language | Python |
| HTTP API | FastAPI |
| Data validation | Pydantic |
| Data access | SQLAlchemy |
| Relational database | PostgreSQL |
| Testing | pytest |
| Linting and formatting | Ruff |
| Container image | Docker |
| Local service environment | Docker Compose |
| Initial CI platform | Forgejo Actions |
| Service diagnostics | Structured logging and health check |

Specific versions, dependency-management tooling, lock-file strategy, configuration library, logging library and PostgreSQL driver are DEFERRED.

## Expected project shape

A generated project MUST contain at least:

```text
application/
tests/
migrations/

Dockerfile
compose.yaml
pyproject.toml
README.md
.env.example
.gitignore

.forgejo/
└── workflows/
```

- `application/` MUST be an importable Python package and MUST expose one FastAPI application entry point.
- `tests/` MUST contain automated tests.
- `migrations/` MUST contain versioned database-schema changes once persistence is introduced.
- `.forgejo/workflows/` MUST be present when the template is implemented; its workflows are not defined or implemented in this phase.

The exact package layout, FastAPI entry-point path and internal module names are DEFERRED to the template phase. This Golden Path does not mandate `application/main.py` or any transversal internal layout.

## Configuration and secrets

### Mandatory requirements

- Configuration MUST be external to application source code and validated at startup.
- Missing or invalid mandatory configuration MUST fail explicitly without exposing sensitive values.
- `.env.example` MUST contain only documented, non-authenticating placeholders.
- Local secret files, including `.env`, MUST be excluded from Git.
- Secrets, credentials and administrative tokens MUST NOT appear in source code, tests, images, Compose files, logs, commands or documentation.

### Recommendations

- Projects SHOULD centralize configuration access at a clear application boundary.
- Runtime identities and later integrations SHOULD request only the privileges they need.

### Deferred decisions

- Configuration library and settings model.
- Secret manager, injection mechanism, rotation process and provider-specific access.
- Environment taxonomy and per-environment configuration policy.

## API and health check

### Mandatory requirements

- The service MUST expose an HTTP API built with FastAPI and validate its external data contracts with Pydantic.
- Externally visible API behaviour, status codes and validation failures MUST be documented and tested.
- The FastAPI OpenAPI contract MUST be available through the application.
- `GET /health` MUST be exposed without authentication and return a non-sensitive liveness result when the application process can serve requests.
- `/health` MUST be a basic liveness endpoint only. It MUST NOT perform readiness checks or deep dependency checks, including PostgreSQL connectivity.

### Recommendations

- Route handlers SHOULD remain small and delegate complex behaviour to clearly bounded application code.
- Requests SHOULD carry a correlation identifier when one is available.

### Deferred decisions

- Readiness endpoint and dependency-health semantics.
- API versioning, pagination, common error envelope, authentication and authorization.
- Functional resources and endpoints for `incidents-api`.

## Persistence

### Mandatory requirements

- PostgreSQL MUST be the relational database and SQLAlchemy MUST be the data-access technology.
- Database credentials MUST come from external configuration.
- Transaction boundaries, session lifecycle and failure handling MUST be explicit in the implemented project.
- Tests that depend on PostgreSQL semantics MUST use an isolated PostgreSQL instance; they MUST NOT silently substitute SQLite.

### Recommendations

- Persistence details SHOULD remain separated from externally visible API handling.
- Database interactions SHOULD be designed to make error diagnosis and testing straightforward.

### Deferred decisions

- Synchronous or asynchronous SQLAlchemy execution and the PostgreSQL driver.
- Connection-pool settings and the detailed transaction policy.
- Repository, Unit of Work, layered or vertical-slice internal architecture.

## Migrations

### Mandatory requirements

- Every database-schema change MUST be versioned, reviewable and reproducible.
- A schema change MUST be validated against PostgreSQL before it is accepted.
- Destructive schema changes MUST be identified explicitly and MUST NOT be applied automatically by an agent.
- Application-model changes MUST NOT be treated as an automatic schema migration.

### Recommendations

- Schema changes SHOULD be designed for compatibility with an orderly deployment and rollback where feasible.

### Deferred decisions

- Migration tool and generated-file conventions.
- Rollback policy.
- Whether migrations run before application startup, in CI, or through a later deployment workflow.

## Testing

### Mandatory requirements

- pytest MUST be used for automated testing.
- Tests MUST be deterministic, runnable from the README and isolated from production data, credentials and unmanaged external services.
- Tests MUST cover `/health`, API behaviour, validation failures, relevant error paths and persistence behaviour.
- A reproducible defect MUST receive a regression test when corrected.
- A proposed change MUST report whether tests passed, failed or were not run/not applicable.

### Recommendations

- Unit and integration tests SHOULD be separated when doing so improves clarity.
- Persistence integration tests SHOULD use an isolated PostgreSQL service.

### Deferred decisions

- Coverage threshold, pytest plugins, fixture design and test parallelism.
- Exact test-database lifecycle and CI execution strategy.

## Linting and formatting

### Mandatory requirements

- Ruff MUST provide linting and formatting checks.
- The project MUST version its Ruff configuration in `pyproject.toml`.
- A proposed change MUST pass the configured lint and formatting checks before review.

### Deferred decisions

- Ruff version, rule set, exclusions and local hook integration.

## Logging and observability

### Mandatory requirements

- The service MUST emit structured, contextual logs suitable for diagnosing behaviour and failures.
- Logs MUST include a timestamp, severity and an identifiable event or message.
- Logs MUST NOT expose secrets, credentials or unnecessary personal data.
- The service MUST preserve enough request or execution context to relate reported failures to a relevant change when such context is available.
- Known diagnostic gaps and assumptions MUST be documented.

### Recommendations

- JSON output and request correlation SHOULD be used if they can be introduced without provider coupling.
- Startup, shutdown and unexpected failures SHOULD be recorded explicitly.

### Deferred decisions

- Logging library, collection backend, retention, dashboards, alerts, tracing and monitoring provider.

## Security

### Mandatory requirements

- Untrusted input MUST be validated at the relevant application boundary.
- Dependencies MUST be declared explicitly and material dependency changes reviewed for security impact.
- The container runtime process MUST not require administrative privileges.
- External error responses MUST avoid traces and sensitive implementation details.
- Security findings, assumptions and unresolved risks MUST accompany a proposed change when relevant.
- Security validation MUST retain raw scanner evidence and evaluate the vulnerability gate according to ADR-004 and `factory-core/policies/security-vulnerability-exceptions.md`.
- Raw findings MUST NOT be suppressed by an exception. A project MUST record `image_scanner_passed` for the raw image-scanner result, `image_security_gate_passed` for the ADR-004 image-vulnerability gate, and `security_passed` for the aggregate result of all required applicable security controls.
- `scanner_passed` and `security_gate_passed` MAY be emitted only as documented, deprecated compatibility aliases of the corresponding `image_*` fields; they MUST NOT be interpreted as aggregate security outcomes.

### Recommendations

- Images SHOULD minimize their runtime dependency and privilege surface.
- Dependency and image scans SHOULD be designed to produce reviewable evidence.

### Deferred decisions

- Authentication and authorization model.
- Security scanner selection, scan scope, tool-specific scanner configuration, image base, and environment-specific hardening.

## Minimum documentation

The generated project README MUST document:

- purpose and named owner;
- prerequisites;
- configuration and environment variables;
- local execution;
- tests, linting and formatting;
- database migrations;
- Docker and Compose usage;
- health-check usage;
- API documentation access; and
- known limitations and operational considerations.

Catalog metadata, provider-specific runbooks and a fixed README template are DEFERRED.

## Containerization

### Mandatory requirements

- The project MUST provide a reproducible `Dockerfile`.
- The project MUST provide `compose.yaml` for local use with the service and PostgreSQL.
- Configuration MUST be injected at runtime, not baked into the image.
- Images and Compose files MUST NOT contain authenticating secrets.
- The service container MUST expose the basic liveness health check.

### Recommendations

- Images SHOULD use a minimal runtime footprint and separate build-only dependencies when practical.

### Deferred decisions

- Base image, build stages, application server process, registry, production topology, resources and scaling.

## Expected CI contract

When CI is implemented, it MUST provide independent, reproducible checks for:

- tests;
- Ruff linting and formatting;
- security validation; and
- container build.

It MUST retain raw security evidence and control-evaluation evidence sufficient to record `tests_passed`, `lint_passed`, `dependency_audit_passed`, `image_scanner_passed`, `image_security_gate_passed`, and aggregate `security_passed` under the Factory Core metrics contract. Deprecated compatibility aliases do not replace these canonical fields. Agents MUST NOT bypass checks or merge changes.

Workflow YAML, Forgejo Actions events, permissions, caches, job layout,
artifacts and any Cloudflare CI variant are DEFERRED to later phases.

## Production Ready scorecard

`Production Ready` is a technical project scorecard. It does not authorize a merge or deployment, and a human approval is not a permanent property of this scorecard.

A project meets the technical scorecard only when it has:

- a complete README and named owner;
- automated tests and passing recorded test evidence;
- configured and passing CI evidence;
- an operational basic liveness `GET /health` endpoint;
- a valid Dockerfile;
- versioned, reproducible migrations when the project uses persistence;
- structured logging and a defined monitoring integration in its deployed environment;
- retained raw security evidence and `security_passed = true`, with any applicable image-vulnerability exception documented and evaluated under ADR-004 and the security vulnerability exceptions policy; and
- no known secrets committed to Git.

Merge and deployment remain separate human-controlled actions governed by the pull-request and deployment policies. A project can meet this scorecard without being merged or deployed; a deployment still requires the appropriate human approval.

## Explicit limits

This Golden Path does not decide or implement:

- the `incidents-api` benchmark application;
- a FastAPI template or application code;
- Dockerfile, Compose, CI workflow or runtime infrastructure;
- Forgejo, GitHub mirror, Cloudflare, Proxmox or deployment configuration;
- a secret manager, monitoring backend or production environment;
- Neo4j, Vector DB, RAG, Obsidian, n8n, Telegram, Kubernetes or multi-agent swarms.

## Deferred architecture decisions and ADR status

The following decisions remain DEFERRED and require an ADR before they become mandatory across the Golden Path or are embodied in the template:

1. synchronous versus asynchronous SQLAlchemy execution, including PostgreSQL driver;
2. migration tool and migration-execution strategy; and
3. mandatory internal application architecture and package layout.

No ADR is created in this phase. The approved stack, liveness-only `/health` contract and technical meaning of `Production Ready` are documented requirements of this Golden Path, not new provider or runtime architecture decisions.
