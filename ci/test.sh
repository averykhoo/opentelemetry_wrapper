#!/usr/bin/env bash
# the CI test steps (DEC-56), kept here so the workflow file stays thin; run from the repo root
set -euo pipefail

python -m pip install --upgrade pip
python -m pip install -r requirements.txt pytest
# the versions under test: requirements.txt pins nothing yet (the strict pins come with OTW-13), so this is the latest
python -m pip list | grep -iE '^(opentelemetry|sqlalchemy|fastapi|starlette|pydantic|pytest)' || true

# pytest exits 5 when it collects no tests, which fails the job: a run that tests nothing must not look green
python -m pytest -q -p no:cacheprovider -ra tests
