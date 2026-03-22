#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMPOSE_FILE="${ROOT_DIR}/tests/integration/docker-compose.5nodes.yml"
PROJECT_NAME="xenage-itest-${RANDOM}${RANDOM}"
ARTIFACTS_DIR="${ROOT_DIR}/tests/integration/artifacts"
GUI_YAML="${ARTIFACTS_DIR}/gui-admin.yaml"

mkdir -p "${ARTIFACTS_DIR}"

cleanup() {
  docker-compose -f "${COMPOSE_FILE}" -p "${PROJECT_NAME}" down -v --remove-orphans >/dev/null 2>&1 || true
}
trap cleanup EXIT

require_bin() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "missing required binary: $1" >&2
    exit 1
  fi
}

require_bin docker
require_bin docker-compose

if ! docker image inspect xenage:local >/dev/null 2>&1; then
  echo "[itest] xenage:local not found, building image"
  docker build -t xenage:local -f "${ROOT_DIR}/docker/xenage.Dockerfile" "${ROOT_DIR}"
fi

dc() {
  docker-compose -f "${COMPOSE_FILE}" -p "${PROJECT_NAME}" "$@"
}

exec_service() {
  local service="$1"
  shift
  dc exec -T "${service}" sh -lc "$*"
}

start_service_bg() {
  local service="$1"
  shift
  dc exec -T -d "${service}" sh -lc "$*"
}

echo "[itest] starting 5 raw containers"
dc up -d --quiet-pull

echo "[itest] cp-1 init"
exec_service control-plane-1 \
  'python -c "from xenage.cli import control_plane_main; control_plane_main()" --node-id cp-1 --data-dir /data/cp-1 --endpoint http://control-plane-1:8734 init --group-id demo >/tmp/cp1-init.json'

echo "[itest] reading leader pubkey"
LEADER_PUBKEY="$(exec_service control-plane-1 'python -c "import json, sqlite3; db=sqlite3.connect(\"/data/cp-1/xenage.db\"); row=db.execute(\"SELECT value FROM kv_store WHERE key=\\\"group_state\\\"\").fetchone(); db.close(); print(json.loads(row[0])[\"leader_pubkey\"])"' | tr -d '\r\n')"
if [[ -z "${LEADER_PUBKEY}" ]]; then
  echo "[itest] failed to resolve leader pubkey" >&2
  exit 1
fi

echo "[itest] starting cp-1 serve"
start_service_bg control-plane-1 \
  'python -c "from xenage.cli import control_plane_main; control_plane_main()" --node-id cp-1 --data-dir /data/cp-1 --endpoint http://control-plane-1:8734 serve --host 0.0.0.0 --port 8734'

sleep 2

echo "[itest] issuing bootstrap tokens"
CP2_TOKEN="$(exec_service control-plane-1 'python -c "from xenage.cli import control_plane_main; control_plane_main()" --node-id cp-1 --data-dir /data/cp-1 --endpoint http://control-plane-1:8734 token create' | tr -d '\r\n')"
CP3_TOKEN="$(exec_service control-plane-1 'python -c "from xenage.cli import control_plane_main; control_plane_main()" --node-id cp-1 --data-dir /data/cp-1 --endpoint http://control-plane-1:8734 token create' | tr -d '\r\n')"
RT1_TOKEN="$(exec_service control-plane-1 'python -c "from xenage.cli import control_plane_main; control_plane_main()" --node-id cp-1 --data-dir /data/cp-1 --endpoint http://control-plane-1:8734 token create' | tr -d '\r\n')"
RT2_TOKEN="$(exec_service control-plane-1 'python -c "from xenage.cli import control_plane_main; control_plane_main()" --node-id cp-1 --data-dir /data/cp-1 --endpoint http://control-plane-1:8734 token create' | tr -d '\r\n')"

echo "[itest] joining control planes"
exec_service control-plane-2 \
  "python -c \"from xenage.cli import control_plane_main; control_plane_main()\" --node-id cp-2 --data-dir /data/cp-2 --endpoint http://control-plane-2:8736 connect --leader-host http://control-plane-1:8734 --leader-pubkey ${LEADER_PUBKEY} --bootstrap-token ${CP2_TOKEN} >/tmp/cp2-connect.json"
exec_service control-plane-3 \
  "python -c \"from xenage.cli import control_plane_main; control_plane_main()\" --node-id cp-3 --data-dir /data/cp-3 --endpoint http://control-plane-3:8737 connect --leader-host http://control-plane-1:8734 --leader-pubkey ${LEADER_PUBKEY} --bootstrap-token ${CP3_TOKEN} >/tmp/cp3-connect.json"

echo "[itest] joining runtimes"
exec_service runtime-1 \
  "python -c \"from xenage.cli import runtime_main; runtime_main()\" --node-id rt-1 --data-dir /data/rt-1 connect --leader-host http://control-plane-1:8734 --leader-pubkey ${LEADER_PUBKEY} --bootstrap-token ${RT1_TOKEN} >/tmp/rt1-connect.json"
exec_service runtime-2 \
  "python -c \"from xenage.cli import runtime_main; runtime_main()\" --node-id rt-2 --data-dir /data/rt-2 connect --leader-host http://control-plane-1:8734 --leader-pubkey ${LEADER_PUBKEY} --bootstrap-token ${RT2_TOKEN} >/tmp/rt2-connect.json"

echo "[itest] starting cp-2/cp-3/runtime services"
start_service_bg control-plane-2 \
  'python -c "from xenage.cli import control_plane_main; control_plane_main()" --node-id cp-2 --data-dir /data/cp-2 --endpoint http://control-plane-2:8736 serve --host 0.0.0.0 --port 8736'
start_service_bg control-plane-3 \
  'python -c "from xenage.cli import control_plane_main; control_plane_main()" --node-id cp-3 --data-dir /data/cp-3 --endpoint http://control-plane-3:8737 serve --host 0.0.0.0 --port 8737'
start_service_bg runtime-1 \
  'python -c "from xenage.cli import runtime_main; runtime_main()" --node-id rt-1 --data-dir /data/rt-1 serve'
start_service_bg runtime-2 \
  'python -c "from xenage.cli import runtime_main; runtime_main()" --node-id rt-2 --data-dir /data/rt-2 serve'

echo "[itest] creating GUI bootstrap token + admin user"
GUI_BOOTSTRAP_TOKEN="$(exec_service control-plane-1 'python -c "from xenage.cli import control_plane_main; control_plane_main()" --node-id cp-1 --data-dir /data/cp-1 --endpoint http://control-plane-1:8734 gui-bootstrap-token' | tr -d '\r\n')"
exec_service control-plane-1 \
  "python -c \"from xenage.cli import control_plane_main; control_plane_main()\" --node-id cp-1 --data-dir /data/cp-1 --endpoint http://control-plane-1:8734 gui-bootstrap-user --leader-url http://control-plane-1:8734 --bootstrap-token ${GUI_BOOTSTRAP_TOKEN} --control-plane-url http://127.0.0.1:8734 --control-plane-url http://127.0.0.1:18734 --control-plane-url http://127.0.0.1:28734 --user-id admin --out /shared/gui-admin.yaml >/tmp/gui-bootstrap-user.txt"
exec_service control-plane-1 'cat /shared/gui-admin.yaml' > "${GUI_YAML}"

echo "[itest] asserting cluster state and GUI config"
exec_service control-plane-1 'python - <<"PY"
import json
import sqlite3

conn = sqlite3.connect("/data/cp-1/xenage.db")
row = conn.execute("SELECT value FROM kv_store WHERE key=\"group_state\"").fetchone()
conn.close()
state = json.loads(row[0])

assert state["leader_node_id"] == "cp-1", state
assert len(state["control_planes"]) == 3, state
assert len(state["runtimes"]) == 2, state
print("OK: cluster has 3 control-planes and 2 runtimes")
PY'

if ! grep -q '^kind: ClusterConnection$' "${GUI_YAML}"; then
  echo "[itest] gui yaml kind is invalid" >&2
  exit 1
fi
if ! grep -q '^    id: admin$' "${GUI_YAML}"; then
  echo "[itest] gui yaml user id is invalid" >&2
  exit 1
fi
if ! grep -q '^    role: admin$' "${GUI_YAML}"; then
  echo "[itest] gui yaml role is invalid" >&2
  exit 1
fi

echo "[itest] success"
echo "[itest] gui config saved to ${GUI_YAML}"
