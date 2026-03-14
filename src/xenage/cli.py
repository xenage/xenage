from __future__ import annotations

import argparse
from pathlib import Path

from loguru import logger

from .app.service_runner import (
    ControlPlaneServiceRunner,
    FailoverLoopOptions,
    RuntimeServiceRunner,
    ServeOptions,
)
from .config import load_config
from .logging import configure_logging
from .nodes.control_plane import ControlPlaneNode
from .nodes.runtime import RuntimeNode


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

    gui_user_parser = subparsers.add_parser("gui-user-config")
    gui_user_parser.add_argument("--control-plane-url", action="append", default=[])
    gui_user_parser.add_argument("--user-id", default="admin")
    gui_user_parser.add_argument("--out")

    args = parser.parse_args()
    logger.trace("parsed control-plane args={}", args)
    config = load_config(Path(args.config) if args.config else None)
    log_level = args.log_level or config.log_level
    configure_logging(log_level)
    logger.debug("resolved control-plane config log_level={} config_path={}", log_level, args.config)
    state_ttl_seconds = getattr(args, "state_ttl_seconds", None) or config.control_plane.state_ttl_seconds
    failover_escalation_seconds = getattr(args, "failover_escalation_seconds", None) or config.control_plane.failover_escalation_seconds
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
        bootstrap_ttl_seconds = getattr(args, "bootstrap_ttl_seconds", None) or config.control_plane.bootstrap_ttl_seconds
        failover_check_interval_seconds = getattr(args, "failover_check_interval_seconds", None) or config.control_plane.failover_check_interval_seconds
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
        failover_options = (
            FailoverLoopOptions(
                ttl_seconds=state_ttl_seconds,
                interval_seconds=failover_check_interval_seconds,
            )
            if auto_failover
            else None
        )
        runner.serve_forever(failover=failover_options)
        return
    if args.command == "token":
        token_ttl_seconds = args.ttl_seconds or config.control_plane.bootstrap_ttl_seconds
        logger.debug("running control-plane token create ttl_seconds={}", token_ttl_seconds)
        token = node.issue_bootstrap_token(token_ttl_seconds)
        print(token)
        return
    if args.command == "connect":
        logger.debug("running control-plane connect leader_host={}", args.leader_host)
        state = node.join_peer(args.leader_host, args.leader_pubkey, args.bootstrap_token)
        print(state.dump_json())
        return
    if args.command == "failover":
        failover_ttl_seconds = args.ttl_seconds or config.control_plane.state_ttl_seconds
        logger.debug("running control-plane failover check ttl_seconds={}", failover_ttl_seconds)
        state = node.check_failover(failover_ttl_seconds)
        if state is None:
            logger.info("failover was not triggered")
            return
        print(state.dump_json())
        return
    if args.command == "gui-user-config":
        logger.debug("issuing gui user config user_id={} control_plane_urls={}", args.user_id, args.control_plane_url)
        gui_config = node.issue_gui_connection_config(list(args.control_plane_url), args.user_id)
        payload = dump_gui_connection_yaml(
            cluster_name=gui_config.cluster_name,
            control_plane_urls=gui_config.control_plane_urls,
            user_id=gui_config.user_id,
            role=gui_config.role,
            public_key=gui_config.public_key,
            private_key=gui_config.private_key,
        )
        if args.out:
            Path(args.out).write_text(payload, encoding="utf-8")
            logger.info("wrote gui user config path={}", args.out)
        print(payload, end="" if payload.endswith("\n") else "\n")


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
    config = load_config(Path(args.config) if args.config else None)
    log_level = args.log_level or config.log_level
    configure_logging(log_level)
    logger.debug("resolved runtime config log_level={} config_path={}", log_level, args.config)
    node = RuntimeNode(args.node_id, Path(args.data_dir), list(args.endpoint), log_level)

    if args.command == "serve":
        serve_host = args.host or config.network.runtime_host
        serve_port = args.port or config.network.runtime_port
        logger.debug("running runtime serve host={} port={}", serve_host, serve_port)
        runner = RuntimeServiceRunner(node, ServeOptions(host=serve_host, port=serve_port))
        runner.serve_forever()
        return
    if args.command == "connect":
        logger.debug("running runtime connect leader_host={}", args.leader_host)
        state = node.connect(args.leader_host, args.leader_pubkey, args.bootstrap_token)
        print(state.dump_json())
