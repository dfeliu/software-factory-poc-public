#!/usr/bin/env bash
set -euo pipefail

cp .env.example .env
cleanup() {
  docker compose --profile test down --volumes --remove-orphans
  rm -f .env
}
trap cleanup EXIT
docker build --target test --tag incidents-api:test .
docker run --rm --env-file .env incidents-api:test pytest -m "not integration"
docker compose --profile test run --rm test
