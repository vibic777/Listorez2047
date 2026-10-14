#!/usr/bin/env bash
# Remove build/test junk. Does not delete source, .venv, or user config.
# Usage (from repo root):  bash scripts/clean.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
echo "Cleaning $ROOT"

rm -rf build dist .pytest_cache .mypy_cache .ruff_cache htmlcov .tox .nox logs
find . -type d -name '__pycache__' -not -path './.venv/*' -not -path './venv/*' -prune -exec rm -rf {} +
find . -type f \( -name '*.pyc' -o -name '*.pyo' -o -name '.coverage' \) \
  -not -path './.venv/*' -not -path './venv/*' -delete
rm -rf src/*.egg-info *.egg-info
rm -f ./*.spec

echo "Clean done."
