#!/usr/bin/env bash
set -euo pipefail

readonly TRIVY_IMAGE="aquasec/trivy@sha256:62b1e65e8869bc4b4c6aa4fa2b21595256c7c2f6018a9d9ad61caf87187c1969"
readonly TARGET_IMAGE="incidents-api:security-scan"
readonly SECURITY_DIR="${CI_ARTIFACT_DIR:-.ci-artifacts}/security"
readonly DEPENDENCY_REPORT="$SECURITY_DIR/pip-audit.json"
readonly DEPENDENCY_EVIDENCE="$SECURITY_DIR/dependency-audit-evidence.json"
readonly IMAGE_REPORT="$SECURITY_DIR/trivy-image.json"
readonly IMAGE_EVIDENCE="$SECURITY_DIR/image-security-gate-evidence.json"
readonly NORMALIZED_FINDINGS="$SECURITY_DIR/normalized-findings.json"
readonly SUMMARY_EVIDENCE="$SECURITY_DIR/security-summary-evidence.json"

mkdir -p "$SECURITY_DIR"
trivy_bin="$(mktemp)"
trap 'rm -f "$trivy_bin"' EXIT

uv export --quiet --locked --all-groups --no-emit-project \
  --output-file "$SECURITY_DIR/requirements.txt"
set +e
uvx --from pip-audit==2.10.1 pip-audit \
  -r "$SECURITY_DIR/requirements.txt" --format json --output "$DEPENDENCY_REPORT"
dependency_exit=$?
set -e
dependency_outcome=failure
if [ "$dependency_exit" -eq 0 ]; then dependency_outcome=success; fi
python ci/security_gate.py evaluate-dependency-audit \
  --raw-report "$DEPENDENCY_REPORT" \
  --evidence-output "$DEPENDENCY_EVIDENCE" \
  --command-outcome "$dependency_outcome"

docker run --rm --entrypoint cat "$TRIVY_IMAGE" /usr/local/bin/trivy > "$trivy_bin"
chmod 0755 "$trivy_bin"
docker build --pull --no-cache --target runtime --tag "$TARGET_IMAGE" .
image_id="$(docker image inspect --format '{{.Id}}' "$TARGET_IMAGE")"
set +e
"$trivy_bin" image --scanners vuln --ignore-unfixed=false \
  --format json --output "$IMAGE_REPORT" "$TARGET_IMAGE"
trivy_exit=$?
set -e
trivy_outcome=failed
if [ "$trivy_exit" -eq 0 ]; then trivy_outcome=completed; fi
python ci/security_gate.py evaluate-trivy \
  --raw-report "$IMAGE_REPORT" \
  --normalized-output "$NORMALIZED_FINDINGS" \
  --evidence-output "$IMAGE_EVIDENCE" \
  --exceptions-dir ci/security-exceptions \
  --project incidents-api \
  --commit "${CI_COMMIT_SHA:-local}" \
  --image-digest "$image_id" \
  --runtime-context-tree "$(git rev-parse HEAD^{tree})" \
  --scanner-execution-status "$trivy_outcome"

printf '%s\n' "{\"schema_version\":1,\"controls\":[{\"id\":\"dependency-audit\",\"required\":true,\"evidence_path\":\"$DEPENDENCY_EVIDENCE\"},{\"id\":\"image-vulnerability-gate\",\"required\":true,\"evidence_path\":\"$IMAGE_EVIDENCE\"}]}" \
  > "$SECURITY_DIR/controls.json"
python ci/security_gate.py aggregate \
  --controls-config "$SECURITY_DIR/controls.json" \
  --evidence-output "$SUMMARY_EVIDENCE"
python ci/security_gate.py summary-aggregate --evidence "$SUMMARY_EVIDENCE"
python ci/security_gate.py assert-summary --evidence "$SUMMARY_EVIDENCE"
