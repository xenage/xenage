from __future__ import annotations

import json
import shutil
import subprocess
import time
from collections.abc import Callable
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
COMPOSE_FILE = ROOT / "tests" / "integration" / "compose" / "ha" / "docker-compose.yml"


def compose_cmd(project: str, args: list[str]) -> list[str]:
    return ["docker", "compose", "-p", project, "-f", str(COMPOSE_FILE), *args]


def run_compose(project: str, args: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        compose_cmd(project, args),
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if check and result.returncode != 0:
        raise subprocess.CalledProcessError(
            returncode=result.returncode,
            cmd=compose_cmd(project, args),
            output=result.stdout,
            stderr=result.stderr,
        )
    return result


def service_running(project: str, service: str) -> bool:
    result = run_compose(project, ["ps", "--status", "running", "--services"], check=False)
    if result.returncode != 0:
        return False
    return service in {line.strip() for line in result.stdout.splitlines() if line.strip()}


def read_group_state(project: str, service: str, path: str) -> dict[str, object] | None:
    if not service_running(project, service):
        return None
    result = run_compose(project, ["exec", "-T", service, "cat", path], check=False)
    if result.returncode != 0:
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return None


def collect_diagnostics(project: str) -> str:
    ps_result = run_compose(project, ["ps"], check=False)
    logs_result = run_compose(project, ["logs", "--tail", "80"], check=False)
    return (
        f"\n--- compose ps ---\n{ps_result.stdout}\n"
        f"\n--- compose logs (tail 80) ---\n{logs_result.stdout}\n{logs_result.stderr}\n"
    )


def wait_until(predicate: Callable[[], bool], timeout_seconds: int, message: str, project: str) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if predicate():
            return
        time.sleep(0.75)
    raise AssertionError(f"{message}{collect_diagnostics(project)}")


def wait_for_ready_cluster(project: str) -> None:
    def predicate() -> bool:
        cp1_state = read_group_state(project, "control-plane-1", "/data/cp-1/group_state.json")
        cp2_state = read_group_state(project, "control-plane-2", "/data/cp-2/group_state.json")
        cp3_state = read_group_state(project, "control-plane-3", "/data/cp-3/group_state.json")
        rt1_state = read_group_state(project, "runtime-1", "/data/rt-1/group_state.json")
        rt2_state = read_group_state(project, "runtime-2", "/data/rt-2/group_state.json")
        states = [cp1_state, cp2_state, cp3_state, rt1_state, rt2_state]
        non_null_states: list[dict[str, object]] = [state for state in states if state is not None]
        if len(non_null_states) < 3:
            return False
        max_control_planes = max(len(state.get("control_planes", [])) for state in non_null_states)
        max_runtimes = max(len(state.get("runtimes", [])) for state in non_null_states)
        return (
            max_control_planes >= 3
            and max_runtimes >= 2
            and all(state.get("group_id") == non_null_states[0].get("group_id") for state in non_null_states)
        )

    wait_until(predicate, timeout_seconds=90, message="cluster did not reach the ready state", project=project)


def wait_for_gui_connection_ready(project: str) -> None:
    def predicate() -> bool:
        leader_state = read_group_state(project, "control-plane-1", "/data/cp-1/group_state.json")
        if leader_state is None:
            return False
        return (
            leader_state.get("group_id") == "demo"
            and len(leader_state.get("control_planes", [])) >= 1
            and len(leader_state.get("runtimes", [])) >= 1
        )

    wait_until(
        predicate,
        timeout_seconds=120,
        message="cluster did not reach the GUI connection ready state",
        project=project,
    )


def ensure_down(project: str) -> None:
    run_compose(project, ["down", "-v", "--remove-orphans"], check=False)


def running_control_plane_target(project: str) -> tuple[str, str, str, str]:
    candidates = [
        ("control-plane-1", "cp-1", "/data/cp-1", "http://control-plane-1:8734"),
        ("control-plane-2", "cp-2", "/data/cp-2", "http://control-plane-2:8734"),
        ("control-plane-3", "cp-3", "/data/cp-3", "http://control-plane-3:8734"),
    ]
    for service, node_id, data_dir, url in candidates:
        state = read_group_state(project, service, f"{data_dir}/group_state.json")
        if state is not None and state.get("leader_node_id") == node_id:
            return service, node_id, data_dir, url
    for service, node_id, data_dir, url in candidates:
        if service_running(project, service):
            return service, node_id, data_dir, url
    raise AssertionError(f"no control-plane service is running{collect_diagnostics(project)}")


def run_on_control_plane(
    project: str,
    command_builder: Callable[[str, str, str, str], list[str]],
) -> subprocess.CompletedProcess[str]:
    primary = running_control_plane_target(project)
    candidates = [primary]
    for candidate in [
        ("control-plane-1", "cp-1", "/data/cp-1", "http://control-plane-1:8734"),
        ("control-plane-2", "cp-2", "/data/cp-2", "http://control-plane-2:8734"),
        ("control-plane-3", "cp-3", "/data/cp-3", "http://control-plane-3:8734"),
    ]:
        if candidate not in candidates and service_running(project, candidate[0]):
            candidates.append(candidate)

    failures: list[str] = []
    for service, node_id, data_dir, control_plane_url in candidates:
        result = run_compose(project, command_builder(service, node_id, data_dir, control_plane_url), check=False)
        if result.returncode == 0:
            return result
        failures.append(f"{service}: {result.stderr.strip() or result.stdout.strip()}")
    raise AssertionError("failed to execute command on control-plane nodes: " + " | ".join(failures))


@pytest.fixture(scope="session", autouse=True)
def build_compose_images() -> None:
    if shutil.which("docker") is None:
        return
    result = subprocess.run(
        ["docker", "build", "-f", "docker/xenage.Dockerfile", "-t", "xenage:local", "."],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise subprocess.CalledProcessError(
            returncode=result.returncode,
            cmd=result.args,
            output=result.stdout,
            stderr=result.stderr,
        )


@pytest.mark.skipif(shutil.which("docker") is None, reason="docker is not installed")
def test_compose_ha_bootstrap_and_join() -> None:
    project = "xenage-it-bootstrap"
    ensure_down(project)
    try:
        run_compose(project, ["up", "-d", "--no-build"])
        wait_for_ready_cluster(project)
        leader_state = read_group_state(project, "control-plane-1", "/data/cp-1/group_state.json")
        assert leader_state is not None
        assert leader_state["group_id"] == "demo"
        assert len(leader_state["control_planes"]) >= 1
        assert len(leader_state["runtimes"]) >= 0
    finally:
        ensure_down(project)


@pytest.mark.skipif(shutil.which("docker") is None, reason="docker is not installed")
def test_compose_ha_failover_when_leader_down() -> None:
    project = "xenage-it-failover"
    ensure_down(project)
    try:
        run_compose(project, ["up", "-d", "--no-build"])
        wait_for_ready_cluster(project)
        run_compose(project, ["stop", "control-plane-1"])

        def failover_happened() -> bool:
            state = read_group_state(project, "control-plane-2", "/data/cp-2/group_state.json")
            if state is None:
                return False
            return state.get("leader_node_id") == "cp-2" and int(state.get("leader_epoch", 0)) >= 2

        wait_until(
            failover_happened,
            timeout_seconds=70,
            message="control-plane failover did not happen",
            project=project,
        )

        def cp3_converged_to_new_leader() -> bool:
            state = read_group_state(project, "control-plane-3", "/data/cp-3/group_state.json")
            if state is None:
                return False
            return state.get("leader_node_id") == "cp-2" and int(state.get("leader_epoch", 0)) >= 2

        wait_until(
            cp3_converged_to_new_leader,
            timeout_seconds=70,
            message="control-plane-3 did not converge to failover leader",
            project=project,
        )
        cp3_state = read_group_state(project, "control-plane-3", "/data/cp-3/group_state.json")
        assert cp3_state is not None
        assert cp3_state["group_id"] == "demo"
        assert cp3_state["leader_node_id"] == "cp-2"
    finally:
        ensure_down(project)


@pytest.mark.skipif(shutil.which("docker") is None, reason="docker is not installed")
def test_compose_ha_all_control_planes_restart_and_recover_state() -> None:
    project = "xenage-it-restart"
    ensure_down(project)
    try:
        run_compose(project, ["up", "-d", "--no-build"])
        wait_for_ready_cluster(project)
        run_compose(project, ["stop", "control-plane-1", "control-plane-2", "control-plane-3"])
        run_compose(project, ["start", "control-plane-1", "control-plane-2", "control-plane-3"])

        def recovered() -> bool:
            cp1_state = read_group_state(project, "control-plane-1", "/data/cp-1/group_state.json")
            cp2_state = read_group_state(project, "control-plane-2", "/data/cp-2/group_state.json")
            cp3_state = read_group_state(project, "control-plane-3", "/data/cp-3/group_state.json")
            if cp1_state is None or cp2_state is None or cp3_state is None:
                return False
            max_control_planes = max(
                len(cp1_state.get("control_planes", [])),
                len(cp2_state.get("control_planes", [])),
                len(cp3_state.get("control_planes", [])),
            )
            max_runtimes = max(
                len(cp1_state.get("runtimes", [])),
                len(cp2_state.get("runtimes", [])),
                len(cp3_state.get("runtimes", [])),
            )
            return (
                max_control_planes >= 3
                and max_runtimes >= 2
                and cp2_state.get("group_id") == cp1_state.get("group_id")
                and cp3_state.get("group_id") == cp1_state.get("group_id")
                and int(cp2_state.get("leader_epoch", 0)) >= 1
                and int(cp3_state.get("leader_epoch", 0)) >= 1
                and len(cp2_state.get("control_planes", [])) >= 1
                and len(cp3_state.get("control_planes", [])) >= 1
            )

        wait_until(
            recovered,
            timeout_seconds=90,
            message="control-plane nodes did not recover from restart",
            project=project,
        )
    finally:
        ensure_down(project)


@pytest.mark.skipif(shutil.which("docker") is None, reason="docker is not installed")
def test_compose_gui_signed_connection_snapshot() -> None:
    project = "xenage-it-gui"
    ensure_down(project)
    try:
        run_compose(project, ["up", "-d", "--no-build"])
        wait_for_gui_connection_ready(project)
        service, node_id, data_dir, control_plane_url = running_control_plane_target(project)
        run_compose(
            project,
            [
                "exec",
                "-T",
                service,
                "xenage-control-plane",
                "--config",
                "/config/xenage.toml",
                "--node-id",
                node_id,
                "--data-dir",
                data_dir,
                "--endpoint",
                control_plane_url,
                "gui-user-config",
                "--control-plane-url",
                control_plane_url,
                "--user-id",
                "admin",
                "--out",
                "/shared/gui-admin.yaml",
            ],
        )
        snapshot_command = (
            "import json; "
            "from structures.resources.membership import GuiConnectionConfig; "
            "from xenage.network.gui_client import GuiSignedClient; "
            "cfg = GuiSignedClient.from_yaml('{}').config; "
            "state = json.loads(open('{}/group_state.json', encoding='utf-8').read()); "
            "leader = state['leader_node_id']; "
            "leader_url = next(item['url'] for item in state['endpoints'] if item['node_id'] == leader); "
            "urls = [leader_url, *[url for url in cfg.control_plane_urls if url != leader_url]]; "
            "client = GuiSignedClient(GuiConnectionConfig(cluster_name=cfg.cluster_name, control_plane_urls=urls, user_id=cfg.user_id, public_key=cfg.public_key, private_key=cfg.private_key, role=cfg.role)); "
            "print(client.fetch_cluster_snapshot().dump_json())"
        ).format("/shared/gui-admin.yaml", data_dir)
        result = run_compose(
            project,
            [
                "exec",
                "-T",
                service,
                "python",
                "-c",
                snapshot_command,
            ],
        )
        payload = json.loads(result.stdout)
        assert payload["group_id"] == "demo"
        assert len(payload["nodes"]) >= 3
        assert any(item["key"] == "leader_node_id" for item in payload["group_config"])
        assert any(event["action"] == "gui.cluster.snapshot.read" for event in payload["event_log"])
    finally:
        ensure_down(project)
