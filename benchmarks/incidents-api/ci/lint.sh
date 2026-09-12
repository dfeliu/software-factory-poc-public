#!/usr/bin/env bash
set -euo pipefail

uv sync --frozen --all-groups
uv run ruff check .
uv run ruff format --check .
