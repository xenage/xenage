#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INTEGRATION_SCRIPT="${ROOT_DIR}/integration_test/simple/test_simple_cluster.sh"

if [[ ! -x "${INTEGRATION_SCRIPT}" ]]; then
  echo "integration script is missing or not executable: ${INTEGRATION_SCRIPT}" >&2
  exit 1
fi

if [[ -x "${ROOT_DIR}/.venv/bin/pytest" ]]; then
  PYTEST_CMD=("${ROOT_DIR}/.venv/bin/pytest")
else
  PYTEST_CMD=("pytest")
fi

echo "[tests] starting pytest"
"${PYTEST_CMD[@]}" &
PYTEST_PID=$!

echo "[tests] starting integration test"
"${INTEGRATION_SCRIPT}" &
INTEGRATION_PID=$!

set +e
wait "${PYTEST_PID}"
PYTEST_EXIT=$?
wait "${INTEGRATION_PID}"
INTEGRATION_EXIT=$?
set -e

echo "[tests] pytest exit code: ${PYTEST_EXIT}"
echo "[tests] integration exit code: ${INTEGRATION_EXIT}"

if [[ "${PYTEST_EXIT}" -ne 0 || "${INTEGRATION_EXIT}" -ne 0 ]]; then
  exit 1
fi

echo "[tests] all checks passed"
