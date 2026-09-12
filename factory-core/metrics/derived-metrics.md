# Derived metrics

## Outcome terms

The following terms are distinct and must not be treated as equivalents:

- **successful_run**: a finished run with `success = true`. It does not by itself imply that a pull request was accepted or that a change was deployed.
- **accepted_pr**: a pull request with `pr_accepted = true` under the later human-review process. It does not by itself imply a successful deployment.
- **deployed_change**: a change for which a deployment was attempted and `deployment_success = true`. It must not be inferred from `success` or `pr_accepted` alone.

## Security outcome terms

The following security terms are distinct and must not be treated as equivalents:

- **dependency_audit_passed**: the independent dependency-audit control result.
- **image_scanner_passed**: the raw image-scanner result. It does not consider vulnerability exceptions.
- **image_security_gate_passed**: the result of applying the image vulnerability gate policy to raw image findings and active applicable exceptions.
- **security_passed**: the aggregate result of all required applicable security controls. Initially it is `dependency_audit_passed AND image_security_gate_passed`; it is fail-closed for missing, invalid or unexecuted required evidence.
- **scanner_passed** and **security_gate_passed**: deprecated compatibility aliases for `image_scanner_passed` and `image_security_gate_passed`. They are not aggregate security results.
- **active_security_exception**: a versioned exception that is active, approved, unexpired, and applicable to the finding and scope under evaluation.

Raw findings remain visible even when `security_gate_passed` is true through an active exception.

## Derived metrics contract

| Metric | Minimum calculation or eligibility rule | Current limitation |
|---|---|---|
| `cost_per_successful_run` | Attributable reported cost divided by the number of eligible `successful_run` records. | Requires compatible currency treatment and complete cost capture. |
| `cost_per_feature` | Attributable reported cost divided by completed features. | The feature boundary and run-to-feature attribution are deferred to the benchmark protocol. |
| `cost_per_accepted_pr` | Attributable reported cost divided by eligible `accepted_pr` records. | Requires explicit attribution when more than one run contributes to a pull request. |
| `human_minutes_per_feature` | Attributable `human_minutes` divided by completed features. | The feature boundary and run-to-feature attribution are deferred to the benchmark protocol. |
| `success_rate` | Eligible finished `successful_run` records divided by all eligible finished runs. | Excludes in-progress and invalid records; eligibility criteria must be recorded by the benchmark protocol. |
| `first_attempt_success_rate` | Eligible `successful_run` records with `retries = 0` divided by eligible finished runs. | Depends on consistent retry accounting. |
| `automatic_recovery_rate` | Eligible `successful_run` records with `retries > 0` and `human_interventions = 0`, divided by eligible runs that required recovery. | This is an initial operational proxy; attempt-level recovery evidence may later refine it. |
| `automatic_merge_rate_g1` | G1 records with `merge_mode = automatic` divided by G1 records whose PR reached a merge decision. | Measures mechanical automation after human approval, not autonomous authorization. |
| `autonomous_merge_rate_g2` | Enforced G2 records merged from an `eligible` policy decision without pre-merge human intervention, divided by enforced G2 records reaching a merge decision. | Must be reported with escaped defects, regressions, rollbacks and audit failures. Shadow decisions are excluded. |
| `human_approval_rate` | G1 records with `human_approval_result = true` divided by G1 records whose PR was presented for approval. | Requires a recorded PR-review observation. |
| `policy_escalation_rate` | G2 decisions `needs_human` divided by all valid G2 policy decisions. | Report reason-code distribution; `blocked` automatic rework is not escalation. |
| `human_semantic_judgment_rate` | G2 changes escalated because deterministic evidence cannot establish functional meaning, divided by evaluated G2 changes. | Requires a stable reason code taxonomy. |
| `sampled_audit_failure_rate` | Failed HOTL audits divided by completed sampled audits of G2 automatic merges. | Pending audits are excluded and reported separately. |
| `escaped_defect_rate_g2` | G2 automatic merges with a confirmed escaped defect divided by observed G2 automatic merges. | Requires a declared observation window. |
| `post_merge_regression_rate_g2` | G2 automatic merges causing a post-merge regression divided by observed G2 automatic merges. | Requires deterministic regression evidence. |
| `rollback_rate_g2` | G2 automatic merges requiring rollback divided by observed G2 automatic merges. | A pause without rollback is not a rollback. |
| `unsafe_autonomous_merge_rate` | Automatic merges later found not to have had valid approval, checks, scope or head-commit evidence, divided by automatic merges. | Must be zero for accepted G1 evidence; determine it with S6G1 negative fixtures and audit. |
| `dependency_audit_pass_rate` | Eligible records with `dependency_audit_passed = true`, divided by applicable dependency-audit records. | Does not replace image or aggregate security outcomes. |
| `image_scanner_pass_rate` | Eligible records with `image_scanner_passed = true`, divided by records with a usable image scanner report. | Does not include exceptions or gate policy. |
| `image_security_gate_pass_rate` | Eligible records with `image_security_gate_passed = true`, divided by records evaluated by the image gate. | Must be reported alongside `image_scanner_pass_rate`. |
| `security_pass_rate` | Eligible records with `security_passed = true`, divided by records with all required applicable controls evaluated. | Fail-closed evidence failures are included as failures. |
| `average_image_security_findings_total` | Sum of `image_security_findings_total` divided by records with a usable image scanner report. | Counts only findings in the image scanner's configured scope. |
| `average_image_high_findings` | Sum of `image_security_findings_high` divided by records with a usable image scanner report. | Scanner scope and severity mapping must be retained. |
| `average_image_critical_findings` | Sum of `image_security_findings_critical` divided by records with a usable image scanner report. | Scanner scope and severity mapping must be retained. |
| `image_fixable_findings_rate` | Sum of `image_security_findings_fixable` divided by the sum of `image_security_findings_total`. | Requires complete remediation classification. |
| `image_unfixed_findings_rate` | Sum of `image_security_findings_unfixed` divided by the sum of `image_security_findings_total`. | Requires complete remediation classification. |
| `image_unknown_fix_status_findings_rate` | Sum of `image_security_findings_fix_status_unknown` divided by the sum of `image_security_findings_total`. | A high value signals insufficient remediation evidence rather than accepted risk. |
| `runs_with_active_image_security_exceptions_rate` | Records with `active_image_security_exceptions_count > 0`, divided by records evaluated by the image gate. | Must be reported with identifiers and expiry status available for audit. |

## Recording rules

- Do not replace missing or inapplicable raw values with zero when calculating a metric.
- Preserve the raw values and inclusion/exclusion criteria used for each reported comparison.
- Report results for successful runs, accepted pull requests and deployed changes separately whenever the metric concerns outcomes.
- Keep G0, G1, G2 shadow and G2 enforced populations separate. Never present a shadow decision as an autonomous merge.
- A scheduled HOTL audit is not a pre-merge human intervention. If the audit triggers correction, pause or rollback, record that action separately.
- Report `dependency_audit_pass_rate`, `image_scanner_pass_rate`, `image_security_gate_pass_rate` and `security_pass_rate` separately; none substitutes for another.
- Do not calculate fix-status rates when the applicable records lack a usable remediation classification.
- This document defines no target, threshold, weighting, cost-allocation method or storage technology.
