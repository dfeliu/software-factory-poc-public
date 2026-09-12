#!/usr/bin/env bash
set -euo pipefail

cp .env.example .env
trap 'rm -f .env' EXIT
docker compose config --quiet
docker build --pull --target runtime --tag incidents-api:fixture-ci .
