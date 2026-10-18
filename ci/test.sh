#!/usr/bin/env bash
# the CI test steps (DEC-56), kept here so the workflow file stays thin; run from the repo root
#   ci/test.sh        (or `ci/test.sh all`) every extra installed (requirements.txt), the whole suite
#   ci/test.sh core   the package installed with no extras, alone: it imports and runs `@otel` (AC-20)
set -euo pipefail

mode="${1:-all}"

python -m pip install --upgrade pip

case "$mode" in
  all)
    python -m pip install -r requirements.txt
    # the versions under test: the strict OTel pins (DEC-57) bound the OpenTelemetry ones, the rest is the latest
    python -m pip list | grep -iE '^(opentelemetry|sqlalchemy|fastapi|starlette|pydantic|pytest|hyperscan)' || true

    # pytest exits 5 when it collects no tests, which fails the job: a run that tests nothing must not look green
    python -m pytest -q -p no:cacheprovider -ra tests
    ;;
  core)
    # a regular (non-editable) install, then run from outside the checkout so only the installed package can be imported
    python -m pip install .
    python -m pip list | grep -iE '^(opentelemetry|sqlalchemy|fastapi|starlette|pydantic|pytest|hyperscan|grpcio)' || true
    smoke="$PWD/ci/smoke_core.py"
    cd "$(mktemp -d)"
    python "$smoke"
    ;;
  *)
    echo "usage: ci/test.sh [all|core]" >&2
    exit 2
    ;;
esac
