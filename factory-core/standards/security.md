# Security standard

## Purpose

This standard establishes baseline security expectations for all projects and factory work.

## Minimum requirements

- Apply minimum privilege to people, agents and runtime identities.
- Never commit, print or expose secrets, credentials or administrative tokens.
- Validate and constrain untrusted input at the relevant system boundary.
- Declare dependencies explicitly and review material dependency changes for security impact.
- Record security-relevant assumptions and unresolved risks in the proposed change.
- Require explicit human approval for production-affecting changes.
- A G1 merge, require human approval for the exact proposed commit and a separate fail-closed eligibility check; neither a Builder nor a Reviewer may hold merge authority.
- Retain raw security-scanner evidence when security validation is applicable; vulnerability findings must be evaluated under ADR-004 and `factory-core/policies/security-vulnerability-exceptions.md`.
- Treat `image_scanner_passed` as the raw image-scanner result and `image_security_gate_passed` as the ADR-004 image-vulnerability gate result. `security_passed` is the aggregate outcome of all required applicable security controls; it must not be inferred from an individual control or an unrecorded human approval.
- `scanner_passed` and `security_gate_passed` are deprecated compatibility aliases of the corresponding `image_*` fields only. They are not aggregate security outcomes.
- Never suppress raw findings through an exception; an exception may affect only the documented image-vulnerability gate decision, not `security_passed` by itself.

## Out of scope

This standard does not select authentication or authorization mechanisms, a secret manager, a scanner, scan scope, tool-specific scanner configuration, or provider permissions. The provider-agnostic vulnerability gate and exception rules are governed by ADR-004 and `factory-core/policies/security-vulnerability-exceptions.md`.
