from __future__ import annotations

import asyncio
import argparse
from pathlib import Path

import aiohttp
from loguru import logger

from structures.resources.membership import GuiUserBootstrapRequest, GuiUserBootstrapResponse
from .app.service_runner import (
    ControlPlaneServiceRunner,
    FailoverLoopOptions,
    RuntimeServiceRunner,
    ServeOptions,
)
from .config import load_config
from .logging import configure_logging
from .network.cli_client import ControlPlaneClient
from .nodes.control_plane import ControlPlaneNode
from .nodes.runtime import RuntimeNode
from .serialization import decode_value, encode_value
from .crypto import Ed25519KeyPair


def _namespace_value(args: argparse.Namespace, key: str) -> object | None:
    return args.__dict__.get(key)


def _first_set(*values: object | None) -> object | None:
    for value in values:
        if value is not None:
            return value
    return None


def _optional_path(value: str | None) -> Path | None:
    if not value:
        return None
    return Path(value)


def dump_gui_connection_yaml(
    cluster_name: str,
    control_plane_urls: list[str],
    user_id: str,
    role: str,
    public_key: str,
    private_key: str,
) -> str:
    config_name = f"{cluster_name}-{user_id}".lower().replace("_", "-")
    lines = [
        "apiVersion: xenage.io/v1alpha1",
        "kind: ClusterConnection",
        "metadata:",
        f"  name: {config_name}",
        "spec:",
        f"  clusterName: {cluster_name}",
        "  controlPlaneUrls:",
        *[f"    - {url}" for url in control_plane_urls],
        "  user:",
        f"    id: {user_id}",
        f"    role: {role}",
        f"    publicKey: {public_key}",
        f"    privateKey: {private_key}",
    ]
    return "\n".join(lines) + "\n"


def build_common_parser(program_name: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=program_name)
    parser.add_argument("--node-id", required=True)
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--endpoint", action="append", default=[])
    parser.add_argument("--log-level")
    parser.add_argument("--config")
    return parser


def control_plane_main() -> None:
    parser = build_common_parser("xenage-control-plane")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("--group-id", default="demo")
    init_parser.add_argument("--ttl-seconds", type=int)

    serve_parser = subparsers.add_parser("serve")
    serve_parser.add_argument("--host")
    serve_parser.add_argument("--port", type=int)
    serve_parser.add_argument("--bootstrap-out", action="append", default=[])
    serve_parser.add_argument("--bootstrap-ttl-seconds", type=int)
    serve_parser.add_argument("--state-ttl-seconds", type=int)
    serve_parser.add_argument("--disable-auto-failover", action="store_true")
    serve_parser.add_argument("--failover-check-interval-seconds", type=int)
    serve_parser.add_argument("--failover-escalation-seconds", type=int)

    token_parser = subparsers.add_parser("token")
    token_parser.add_argument("token_command", choices=["create"])
    token_parser.add_argument("--ttl-seconds", type=int)

    connect_parser = subparsers.add_parser("connect")
    connect_parser.add_argument("--leader-host", required=True)
    connect_parser.add_argument("--leader-pubkey", required=True)
    connect_parser.add_argument("--bootstrap-token", required=True)

    failover_parser = subparsers.add_parser("failover")
    failover_parser.add_argument("--ttl-seconds", type=int)

    gui_token_parser = subparsers.add_parser("gui-bootstrap-token")
    gui_token_parser.add_argument("--ttl-seconds", type=int)
    gui_token_parser.add_argument("--out")

    gui_bootstrap_user_parser = subparsers.add_parser("gui-bootstrap-user")
    gui_bootstrap_user_parser.add_argument("--leader-url", required=True)
    gui_bootstrap_user_parser.add_argument("--bootstrap-token", required=True)
    gui_bootstrap_user_parser.add_argument("--control-plane-url", action="append", default=[])
    gui_bootstrap_user_parser.add_argument("--user-id", default="admin")
    gui_bootstrap_user_parser.add_argument("--out")

    args = parser.parse_args()
    logger.trace("parsed control-plane args={}", args)
    config = load_config(_optional_path(args.config))
    log_level = args.log_level or config.log_level
    configure_logging(log_level)
    logger.debug("resolved control-plane config log_level={} config_path={}", log_level, args.config)
    state_ttl_seconds = int(_first_set(_namespace_value(args, "state_ttl_seconds"), config.control_plane.state_ttl_seconds))
    failover_escalation_seconds = int(
        _first_set(_namespace_value(args, "failover_escalation_seconds"), config.control_plane.failover_escalation_seconds)
    )
    node = ControlPlaneNode(
        args.node_id,
        Path(args.data_dir),
        list(args.endpoint),
        log_level,
        state_ttl_seconds,
        failover_escalation_seconds,
    )

    if args.command == "init":
        init_ttl_seconds = args.ttl_seconds or config.control_plane.init_ttl_seconds
        logger.debug("running control-plane init group_id={} ttl_seconds={}", args.group_id, init_ttl_seconds)
        state = node.initialize_group(args.group_id, init_ttl_seconds)
        print(state.dump_json())
        return
    if args.command == "serve":
        serve_host = args.host or config.network.control_plane_host
        serve_port = args.port or config.network.control_plane_port
        bootstrap_ttl_seconds = int(
            _first_set(_namespace_value(args, "bootstrap_ttl_seconds"), config.control_plane.bootstrap_ttl_seconds)
        )
        failover_check_interval_seconds = int(
            _first_set(
                _namespace_value(args, "failover_check_interval_seconds"),
                config.control_plane.failover_check_interval_seconds,
            )
        )
        logger.debug(
            "running control-plane serve host={} port={} bootstrap_ttl_seconds={} failover_interval={}",
            serve_host,
            serve_port,
            bootstrap_ttl_seconds,
            failover_check_interval_seconds,
        )
        for output_path in args.bootstrap_out:
            token = node.issue_bootstrap_token(bootstrap_ttl_seconds)
            Path(output_path).write_text(token, encoding="utf-8")
            logger.trace("wrote bootstrap token path={} bytes={}", output_path, len(token))
        auto_failover = config.control_plane.auto_failover and not args.disable_auto_failover
        runner = ControlPlaneServiceRunner(node, ServeOptions(host=serve_host, port=serve_port))
        failover_options: FailoverLoopOptions | None = None
        if auto_failover:
            failover_options = FailoverLoopOptions(
                ttl_seconds=state_ttl_seconds,
                interval_seconds=failover_check_interval_seconds,
            )
        asyncio.run(runner.serve_forever(failover=failover_options))
        return
    if args.command == "token":
        token_ttl_seconds = args.ttl_seconds or config.control_plane.bootstrap_ttl_seconds
        logger.debug("running control-plane token create ttl_seconds={}", token_ttl_seconds)
        token = node.issue_bootstrap_token(token_ttl_seconds)
        print(token)
        return
    if args.command == "connect":
        logger.debug("running control-plane connect leader_host={}", args.leader_host)
        state = asyncio.run(node.join_peer(args.leader_host, args.leader_pubkey, args.bootstrap_token))
        print(state.dump_json())
        return
    if args.command == "failover":
        failover_ttl_seconds = args.ttl_seconds or config.control_plane.state_ttl_seconds
        logger.debug("running control-plane failover check ttl_seconds={}", failover_ttl_seconds)
        state = asyncio.run(node.check_failover(failover_ttl_seconds))
        if state is None:
            logger.info("failover was not triggered")
            return
        print(state.dump_json())
        return
    if args.command == "gui-bootstrap-token":
        token_ttl_seconds = args.ttl_seconds or config.control_plane.bootstrap_ttl_seconds
        logger.debug("issuing gui bootstrap token ttl_seconds={}", token_ttl_seconds)
        token = node.issue_gui_bootstrap_token(token_ttl_seconds)
        if args.out:
            Path(args.out).write_text(token, encoding="utf-8")
            logger.info("wrote gui bootstrap token path={}", args.out)
        print(token)
        return
    if args.command == "gui-bootstrap-user":
        logger.debug(
            "bootstrapping gui user via api user_id={} leader_url={} control_plane_urls={}",
            args.user_id,
            args.leader_url,
            args.control_plane_url,
        )
        user_key = Ed25519KeyPair.generate()
        request = GuiUserBootstrapRequest(
            bootstrap_token=args.bootstrap_token,
            user_id=args.user_id,
            public_key=user_key.public_key_b64(),
            control_plane_urls=list(args.control_plane_url),
        )

        async def bootstrap_gui_user() -> GuiUserBootstrapResponse:
            timeout = aiohttp.ClientTimeout(total=3.0)
            url = f"{args.leader_url.rstrip('/')}/v1/gui/bootstrap-user"
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    url,
                    data=encode_value(request),
                    headers={"content-type": "application/json"},
                ) as response:
                    payload = await response.read()
                    if response.status != 200:
                        raise RuntimeError(payload.decode("utf-8", errors="replace"))
                    return decode_value(payload, GuiUserBootstrapResponse)

        bootstrap_response = asyncio.run(bootstrap_gui_user())
        gui_config = dump_gui_connection_yaml(
            cluster_name=bootstrap_response.cluster_name,
            control_plane_urls=bootstrap_response.control_plane_urls,
            user_id=bootstrap_response.user_id,
            role=bootstrap_response.role,
            public_key=bootstrap_response.public_key,
            private_key=user_key.private_key_b64(),
        )
        if args.out:
            Path(args.out).write_text(gui_config, encoding="utf-8")
            logger.info("wrote gui user config path={}", args.out)
        print(gui_config, end="" if gui_config.endswith("\n") else "\n")
        return
def runtime_main() -> None:
    parser = build_common_parser("xenage-runtime")
    subparsers = parser.add_subparsers(dest="command", required=True)

    serve_parser = subparsers.add_parser("serve")
    serve_parser.add_argument("--host")
    serve_parser.add_argument("--port", type=int)

    connect_parser = subparsers.add_parser("connect")
    connect_parser.add_argument("--leader-host", required=True)
    connect_parser.add_argument("--leader-pubkey", required=True)
    connect_parser.add_argument("--bootstrap-token", required=True)

    args = parser.parse_args()
    logger.trace("parsed runtime args={}", args)
    config = load_config(_optional_path(args.config))
    log_level = args.log_level or config.log_level
    configure_logging(log_level)
    logger.debug("resolved runtime config log_level={} config_path={}", log_level, args.config)
    if args.endpoint:
        logger.warning(
            "runtime endpoints are ignored; runtime nodes run in poll-only mode endpoints={}",
            args.endpoint,
        )
    node = RuntimeNode(args.node_id, Path(args.data_dir), log_level)

    if args.command == "serve":
        if args.host or args.port:
            logger.warning(
                "runtime serve host/port options are ignored in poll-only mode host={} port={}",
                args.host,
                args.port,
            )
        logger.debug("running runtime poll loop node_id={}", args.node_id)
        runner = RuntimeServiceRunner(node)
        asyncio.run(runner.serve_forever())
        return
    if args.command == "connect":
        logger.debug("running runtime connect leader_host={}", args.leader_host)
        state = asyncio.run(node.connect(args.leader_host, args.leader_pubkey, args.bootstrap_token))
        print(state.dump_json())


def xenage_cli_main() -> None:
    parser = argparse.ArgumentParser(prog="xenage")
    parser.add_argument("--config", help="Path to cluster connection config (yaml)")
    subparsers = parser.add_subparsers(dest="command", required=True)

    get_parser = subparsers.add_parser("get")
    get_parser.add_argument("resource", choices=["nodes", "group-config", "events", "state"])
    get_parser.add_argument("--limit", type=int, default=50)

    args = parser.parse_args()

    config_path = args.config
    if not config_path:
        default_path = Path.home() / ".xenage" / "config.yaml"
        if default_path.exists():
            config_path = str(default_path)
        else:
            print("Error: --config not provided and ~/.xenage/config.yaml not found")
            return

    client = ControlPlaneClient.from_yaml(config_path)

    if args.command == "get":
        if args.resource == "nodes":
            snapshot = asyncio.run(client.get_cluster_snapshot())
            print(f"{'NODE_ID':<20} {'ROLE':<15} {'STATUS':<15} {'ENDPOINT':<30}")
            for node in snapshot.nodes:
                endpoint = node.endpoints[0] if node.endpoints else "-"
                status = node.status
                if node.leader:
                    status += " (leader)"
                print(f"{node.node_id:<20} {node.role:<15} {status:<15} {endpoint:<30}")

        elif args.resource == "group-config":
            state = asyncio.run(client.get_current_state())
            print(state.config.dump_yaml())

        elif args.resource == "events":
            page = asyncio.run(client.get_events(limit=args.limit))
            print(f"{'SEQ':<10} {'TIMESTAMP':<25} {'EVENT_TYPE':<30} {'USER'}")
            for event in page.items:
                print(f"{event.sequence:<10} {event.timestamp:<25} {event.event_type:<30} {event.user_id}")

        elif args.resource == "state":
            state = asyncio.run(client.get_current_state())
            print(state.dump_json())
