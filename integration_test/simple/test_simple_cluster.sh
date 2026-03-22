#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TEST_DIR="${ROOT_DIR}/integration_test/simple"
COMPOSE_FILE="${TEST_DIR}/docker-compose.yml"
PROJECT_NAME="xenage-simple-itest-${RANDOM}${RANDOM}"
ARTIFACTS_DIR="${TEST_DIR}/artifacts"
GUI_YAML="${ARTIFACTS_DIR}/gui-admin.yaml"
VENV_PY="${ROOT_DIR}/.venv/bin/python"

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
if [[ ! -x "${VENV_PY}" ]]; then
  echo "python venv is missing: ${VENV_PY}" >&2
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "docker daemon is not available" >&2
  exit 1
fi

echo "[simple-itest] building xenage:local image"
docker build -t xenage:local -f "${ROOT_DIR}/docker/xenage.Dockerfile" "${ROOT_DIR}" >/dev/null

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

sync_control_plane_once() {
  local service="$1"
  local node_id="$2"
  local data_dir="$3"
  local endpoint="$4"
  exec_service "${service}" "python - <<'PY'
import asyncio
from pathlib import Path

from xenage.nodes.control_plane import ControlPlaneNode

node = ControlPlaneNode('${node_id}', Path('${data_dir}'), ['${endpoint}'])
asyncio.run(node.sync_control_plane_events())
PY"
}

has_admin_user_on_service() {
  local service="$1"
  local node_id="$2"
  local data_dir="$3"
  local endpoint="$4"
  local expected_public_key="$5"
  exec_service "${service}" "EXPECTED_PUBLIC_KEY='${expected_public_key}' python - <<'PY'
import os
from pathlib import Path

from xenage.nodes.control_plane import ControlPlaneNode

expected = os.environ['EXPECTED_PUBLIC_KEY']
node = ControlPlaneNode('${node_id}', Path('${data_dir}'), ['${endpoint}'])
user = node.user_state_manager.find_user('admin')
if user is None:
    raise SystemExit(1)
if user.public_key != expected:
    raise SystemExit(1)
if not user.enabled:
    raise SystemExit(1)
raise SystemExit(0)
PY"
}

extract_token() {
  awk '/^[A-Za-z0-9_-]{20,}$/ {token=$0} END {print token}'
}

wait_until() {
  local attempts="$1"
  local sleep_seconds="$2"
  shift 2

  local n=1
  while [[ "${n}" -le "${attempts}" ]]; do
    if "$@" >/dev/null 2>&1; then
      return 0
    fi
    sleep "${sleep_seconds}"
    n=$((n + 1))
  done
  return 1
}

wait_http() {
  local service="$1"
  local url="$2"
  wait_until 30 1 exec_service "${service}" "python - <<'PY'
import urllib.request
urllib.request.urlopen('${url}', timeout=2).read()
PY"
}

echo "[simple-itest] starting 5 raw containers"
dc up -d --quiet-pull

echo "[simple-itest] cp-1 init"
exec_service control-plane-1 \
  'python -c "from xenage.cli import control_plane_main; control_plane_main()" --node-id cp-1 --data-dir /data/cp-1 --endpoint http://control-plane-1:8734 init --group-id demo >/tmp/cp1-init.json'

LEADER_PUBKEY="$(exec_service control-plane-1 'python - <<"PY"
import json
import sqlite3

conn = sqlite3.connect("/data/cp-1/xenage.db")
row = conn.execute("SELECT value FROM kv_store WHERE key=\"group_state\"").fetchone()
conn.close()
state = json.loads(row[0])
print(state["leader_pubkey"])
PY' | tail -n 1 | tr -d '\r\n')"

if [[ -z "${LEADER_PUBKEY}" ]]; then
  echo "[simple-itest] failed to resolve leader pubkey" >&2
  exit 1
fi

echo "[simple-itest] starting cp-1 service"
start_service_bg control-plane-1 \
  'python -c "from xenage.cli import control_plane_main; control_plane_main()" --node-id cp-1 --data-dir /data/cp-1 --endpoint http://control-plane-1:8734 serve --host 0.0.0.0 --port 8734 --bootstrap-out /shared/cp2.token --bootstrap-out /shared/cp3.token --bootstrap-out /shared/rt1.token --bootstrap-out /shared/rt2.token'

wait_http control-plane-1 http://127.0.0.1:8734/v1/heartbeat

echo "[simple-itest] issuing bootstrap tokens"
wait_until 20 1 exec_service control-plane-1 'test -s /shared/cp2.token && test -s /shared/cp3.token && test -s /shared/rt1.token && test -s /shared/rt2.token'
CP2_TOKEN="$(exec_service control-plane-1 'cat /shared/cp2.token' | extract_token | tr -d '\r\n')"
CP3_TOKEN="$(exec_service control-plane-1 'cat /shared/cp3.token' | extract_token | tr -d '\r\n')"
RT1_TOKEN="$(exec_service control-plane-1 'cat /shared/rt1.token' | extract_token | tr -d '\r\n')"
RT2_TOKEN="$(exec_service control-plane-1 'cat /shared/rt2.token' | extract_token | tr -d '\r\n')"
if [[ -z "${CP2_TOKEN}" || -z "${CP3_TOKEN}" || -z "${RT1_TOKEN}" || -z "${RT2_TOKEN}" ]]; then
  echo "[simple-itest] failed to extract one or more bootstrap tokens" >&2
  exit 1
fi

echo "[simple-itest] joining control planes"
exec_service control-plane-2 \
  "python -c \"from xenage.cli import control_plane_main; control_plane_main()\" --node-id cp-2 --data-dir /data/cp-2 --endpoint http://control-plane-2:8736 connect --leader-host http://control-plane-1:8734 --leader-pubkey '${LEADER_PUBKEY}' --bootstrap-token '${CP2_TOKEN}' >/tmp/cp2-connect.json"
exec_service control-plane-3 \
  "python -c \"from xenage.cli import control_plane_main; control_plane_main()\" --node-id cp-3 --data-dir /data/cp-3 --endpoint http://control-plane-3:8737 connect --leader-host http://control-plane-1:8734 --leader-pubkey '${LEADER_PUBKEY}' --bootstrap-token '${CP3_TOKEN}' >/tmp/cp3-connect.json"

echo "[simple-itest] joining runtimes"
exec_service runtime-1 \
  "python -c \"from xenage.cli import runtime_main; runtime_main()\" --node-id rt-1 --data-dir /data/rt-1 connect --leader-host http://control-plane-1:8734 --leader-pubkey '${LEADER_PUBKEY}' --bootstrap-token '${RT1_TOKEN}' >/tmp/rt1-connect.json"
exec_service runtime-2 \
  "python -c \"from xenage.cli import runtime_main; runtime_main()\" --node-id rt-2 --data-dir /data/rt-2 connect --leader-host http://control-plane-1:8734 --leader-pubkey '${LEADER_PUBKEY}' --bootstrap-token '${RT2_TOKEN}' >/tmp/rt2-connect.json"

echo "[simple-itest] starting cp-2/cp-3/runtime services"
start_service_bg control-plane-2 \
  'python -c "from xenage.cli import control_plane_main; control_plane_main()" --node-id cp-2 --data-dir /data/cp-2 --endpoint http://control-plane-2:8736 serve --host 0.0.0.0 --port 8736'
start_service_bg control-plane-3 \
  'python -c "from xenage.cli import control_plane_main; control_plane_main()" --node-id cp-3 --data-dir /data/cp-3 --endpoint http://control-plane-3:8737 serve --host 0.0.0.0 --port 8737'
start_service_bg runtime-1 \
  'python -c "from xenage.cli import runtime_main; runtime_main()" --node-id rt-1 --data-dir /data/rt-1 serve'
start_service_bg runtime-2 \
  'python -c "from xenage.cli import runtime_main; runtime_main()" --node-id rt-2 --data-dir /data/rt-2 serve'

wait_http control-plane-2 http://127.0.0.1:8736/v1/heartbeat
wait_http control-plane-3 http://127.0.0.1:8737/v1/heartbeat

echo "[simple-itest] waiting for full cluster state sync"
wait_until 40 1 exec_service control-plane-1 'python - <<"PY"
import json
import sqlite3

conn = sqlite3.connect("/data/cp-1/xenage.db")
row = conn.execute("SELECT value FROM kv_store WHERE key=\"group_state\"").fetchone()
conn.close()
state = json.loads(row[0])
assert len(state["control_planes"]) == 3
assert len(state["runtimes"]) == 2
PY'

echo "[simple-itest] creating GUI bootstrap token + admin user"
GUI_BOOTSTRAP_TOKEN="$(exec_service control-plane-1 'python -c "from xenage.cli import control_plane_main; control_plane_main()" --node-id cp-1 --data-dir /data/cp-1 --endpoint http://control-plane-1:8734 gui-bootstrap-token' | extract_token | tr -d '\r\n')"
if [[ -z "${GUI_BOOTSTRAP_TOKEN}" ]]; then
  echo "[simple-itest] failed to extract gui bootstrap token" >&2
  exit 1
fi
exec_service control-plane-1 \
  "python -c \"from xenage.cli import control_plane_main; control_plane_main()\" --node-id cp-1 --data-dir /data/cp-1 --endpoint http://control-plane-1:8734 gui-bootstrap-user --leader-url http://control-plane-1:8734 --bootstrap-token '${GUI_BOOTSTRAP_TOKEN}' --control-plane-url http://127.0.0.1:8734 --control-plane-url http://127.0.0.1:18734 --control-plane-url http://127.0.0.1:28734 --user-id admin --out /shared/gui-admin.yaml >/tmp/gui-bootstrap-user.txt"
exec_service control-plane-1 'cat /shared/gui-admin.yaml' > "${GUI_YAML}"
GUI_PUBLIC_KEY="$(awk '/^[[:space:]]+publicKey:/ {print $2; exit}' "${GUI_YAML}" | tr -d '\r\n')"
if [[ -z "${GUI_PUBLIC_KEY}" ]]; then
  echo "[simple-itest] failed to resolve GUI public key from ${GUI_YAML}" >&2
  exit 1
fi

echo "[simple-itest] waiting for admin replication to cp-2/cp-3"
sync_control_plane_once control-plane-2 cp-2 /data/cp-2 http://control-plane-2:8736
sync_control_plane_once control-plane-3 cp-3 /data/cp-3 http://control-plane-3:8737
wait_until 30 1 has_admin_user_on_service control-plane-2 cp-2 /data/cp-2 http://control-plane-2:8736 "${GUI_PUBLIC_KEY}"
wait_until 30 1 has_admin_user_on_service control-plane-3 cp-3 /data/cp-3 http://control-plane-3:8737 "${GUI_PUBLIC_KEY}"

echo "[simple-itest] checking initial cluster layout + CLI + GUI connectivity"
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
print("OK: initial state has 3 control-planes + 2 runtimes")
PY'

PYTHONPATH="${ROOT_DIR}:${ROOT_DIR}/src" \
  "${VENV_PY}" -c 'from xenage.cli import xenage_cli_main; xenage_cli_main()' \
  --config "${GUI_YAML}" get nodes > "${ARTIFACTS_DIR}/cli-nodes-before.txt"

PYTHONPATH="${ROOT_DIR}:${ROOT_DIR}/src" \
  "${VENV_PY}" - <<PY
from xenage.network.cli_client import ControlPlaneClient

client = ControlPlaneClient.from_yaml("${GUI_YAML}")
snapshot = client.fetch_cluster_snapshot()
assert len(snapshot.nodes) >= 5, snapshot
print("OK: GUI client can fetch snapshot")
PY

echo "[simple-itest] simulating leader failure (stop control-plane-1 container)"
dc stop control-plane-1 >/dev/null

get_leader_from_service() {
  local service="$1"
  local db_path="$2"
  exec_service "${service}" 'python - <<"PY"
import json
import sqlite3
conn = sqlite3.connect("'"${db_path}"'")
row = conn.execute("SELECT value FROM kv_store WHERE key=\"group_state\"").fetchone()
conn.close()
state = json.loads(row[0])
print(state["leader_node_id"])
PY' 2>/dev/null
}

wait_for_new_leader() {
  local attempts=30
  local i=1
  while [[ "${i}" -le "${attempts}" ]]; do
    local leader_cp2 leader_cp3
    leader_cp2="$(get_leader_from_service control-plane-2 /data/cp-2/xenage.db | tr -d '\r\n' || true)"
    leader_cp3="$(get_leader_from_service control-plane-3 /data/cp-3/xenage.db | tr -d '\r\n' || true)"

    if [[ -n "${leader_cp2}" && "${leader_cp2}" != "cp-1" && "${leader_cp2}" == "${leader_cp3}" ]]; then
      echo "${leader_cp2}"
      return 0
    fi

    sleep 1
    i=$((i + 1))
  done
  return 1
}

NEW_LEADER="$(wait_for_new_leader || true)"
if [[ -z "${NEW_LEADER}" ]]; then
  echo "[simple-itest] failed to observe leader failover" >&2
  exit 1
fi

if [[ "${NEW_LEADER}" != "cp-2" && "${NEW_LEADER}" != "cp-3" ]]; then
  echo "[simple-itest] unexpected new leader: ${NEW_LEADER}" >&2
  exit 1
fi

echo "[simple-itest] new leader is ${NEW_LEADER}"

echo "[simple-itest] verifying CLI/GUI still work after failover"
PYTHONPATH="${ROOT_DIR}:${ROOT_DIR}/src" \
  "${VENV_PY}" -c 'from xenage.cli import xenage_cli_main; xenage_cli_main()' \
  --config "${GUI_YAML}" get nodes > "${ARTIFACTS_DIR}/cli-nodes-after.txt"

PYTHONPATH="${ROOT_DIR}:${ROOT_DIR}/src" \
  "${VENV_PY}" - <<PY
from xenage.network.cli_client import ControlPlaneClient

client = ControlPlaneClient.from_yaml("${GUI_YAML}")
state = client.fetch_current_state()
assert state.leader_node_id in {"cp-2", "cp-3"}, state
assert state.leader_node_id != "cp-1", state
print("OK: GUI client can fetch state after failover")
PY

echo "[simple-itest] verifying admin user is present on new leader"
NEW_LEADER_SERVICE="control-plane-2"
if [[ "${NEW_LEADER}" == "cp-3" ]]; then
  NEW_LEADER_SERVICE="control-plane-3"
fi

exec_service "${NEW_LEADER_SERVICE}" "python - <<'PY'
import re
from pathlib import Path

from xenage.nodes.control_plane import ControlPlaneNode

cfg = open('/shared/gui-admin.yaml', encoding='utf-8').read()
match = re.search(r'^\\s*publicKey:\\s*(\\S+)\\s*$', cfg, re.MULTILINE)
if not match:
    raise SystemExit('publicKey not found in gui-admin.yaml')
expected_public_key = match.group(1)

node_id = 'cp-2'
data_dir = '/data/cp-2'
endpoint = 'http://control-plane-2:8736'
if '${NEW_LEADER_SERVICE}' == 'control-plane-3':
    node_id = 'cp-3'
    data_dir = '/data/cp-3'
    endpoint = 'http://control-plane-3:8737'

node = ControlPlaneNode(node_id, Path(data_dir), [endpoint])
admin = node.user_state_manager.find_user('admin')
if admin is None:
    raise SystemExit('admin user missing on new leader')
if admin.public_key != expected_public_key:
    raise SystemExit('admin publicKey mismatch on new leader')
if not admin.enabled:
    raise SystemExit('admin account is disabled on new leader')

print('OK: new leader keeps correct admin user')
PY"

echo "[simple-itest] SUCCESS"
echo "[simple-itest] GUI config saved: ${GUI_YAML}"
