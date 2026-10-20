#!/usr/bin/env bash
# the CI test steps (DEC-56), kept here so the workflow file stays thin; run from the repo root
#   ci/test.sh        (or `ci/test.sh all`) every extra installed (requirements.txt), the whole suite
#   ci/test.sh core   the package installed with no extras, alone: it imports and runs `@otel` (AC-20, tests/test_install_core.py)
set -euo pipefail

mode="${1:-all}"

python -m pip install --upgrade pip

case "$mode" in
  all)
    python -m pip install -r requirements.txt
    # the versions under test: the strict OTel pins (DEC-57) bound the OpenTelemetry ones, the rest is the latest
    python -m pip list | grep -iE '^(opentelemetry|sqlalchemy|fastapi|starlette|pydantic|pytest|hyperscan)' || true

    target=tests
    ;;
  core)
    # a regular (non-editable) install, and pytest to run the trial: tests/test_install_core.py runs ci/smoke_core.py
    # in a subprocess from an empty directory with no PYTHONPATH, so only the installed package can be imported
    python -m pip install .
    python -m pip install pytest
    # since 1.0.0 none of sqlalchemy, fastapi, starlette, grpcio or psutil is core: the listing shows any that slipped in
    python -m pip list | grep -iE '^(opentelemetry|sqlalchemy|fastapi|starlette|pydantic|pytest|hyperscan|grpcio|psutil)' || true
    target=tests/test_install_core.py
    ;;
  *)
    echo "usage: ci/test.sh [all|core]" >&2
    exit 2
    ;;
esac

# OTW_INSTALL_TRIAL=all|core (AC-20, tests/test_install_core.py): `all` turns a missing extra into a failure, `core` runs
# the no-extras install trial. pytest exits 5 when it collects no tests, which fails the job: a run that tests nothing
# must not look green
OTW_INSTALL_TRIAL="$mode" python -m pytest -q -p no:cacheprovider -ra "$target"
