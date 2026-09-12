# Forgejo Native benchmark protocol (F4 preparation)

This directory contains the reviewable scenario fixtures for architecture `F` (Forgejo Native). It is preparation only: no scenario, workflow, runner, Proxmox action, deployment, merge, or benchmark has been executed by creating these files.

The versioned current G0 population, cases and inclusion rules live in
`benchmarks/manifests/forgejo-native-f-v1.json`. Validate and expand that
contract with `benchmarks/forgejo_native_campaign.py`; S6G1 and S6G2 evidence
remain separate historical populations and are not silently pooled with F/G0.

## Execution contract

An operator must pin the following before each run and record the values in the report:

- Forgejo version and instance identifier; repository and immutable base commit;
- scenario fixture revision (the Git commit containing this directory);
- private runner identity/type, workflow file revision, and model/authentication/billing mode;
- an isolated repository namespace and test-only mirror target, with no production credentials;
- a fresh run directory named by `factory_run_id`, with logs and artifacts retained.

The base commit, fixture revision, input, workflow, and permission configuration are immutable for a run. A scenario may create only disposable branches, pull requests, test data, and test mirror output. The operator records any deviation as a failure; they do not repair the run in place.

Each run has one `factory_run_id`; retries remain attempts of that run. A repetition gets a distinct run ID. Evidence must be linked to the run ID and must contain timestamps, commit/PR identifiers, workflow/pipeline identifiers, and actor identity where applicable. Never put credentials or token values in evidence.

The terminal condition is evaluated exactly as written in each fixture. A successful run requires the declared terminal condition and all expected evidence. `false`, `0`, and `N/A` are distinct values. In particular, unavailable managed-ChatGPT token/cost fields are `N/A`, not zero; zero is valid only when the source reports a measured zero.

## Repetition plan

Run S1, S2, S3, S4, and S5A five times each, from the same pinned fixture and an isolated fresh run namespace. Do not pool state between repetitions. Record all five runs, including failures.

S5B and S7 are observation scenarios rather than a claim of statistical performance. Run a minimum of five controlled trials per declared interruption/concurrency case, and continue in complete blocks of five if outcomes are mixed or the recovery behavior is not yet characterized. Publish the number of planned, completed, excluded, and replacement trials with the reason for every exclusion. Do not stop early because an expected result appears once.

## Safety boundary

S5B interruption is limited to a disposable workflow run, test runner process, or test-only worker lease. S7 uses independent test branches/workspaces and a bounded queue. All fixtures prohibit destructive Proxmox operations, production deployment, direct main-branch push, and changes to infrastructure or protection settings during a benchmark. Only S6G1 may perform one automatic merge, exclusively in its disposable repository after its declared human approval and G1 verification; all other governance attempts remain observation-only and can be stopped by the operator.

## Validation

Run the metadata-only validator from the repository root:

```text
python3 benchmarks/validate_scenarios.py
```

This validates fixture structure and metadata only. It does not contact Forgejo, start a workflow, access Proxmox, deploy, merge, or create a result.
