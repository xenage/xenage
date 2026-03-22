from __future__ import annotations

import argparse
import sys
from pathlib import Path

from xenage.network.cli_client import ControlPlaneClient

from .commands import ApplyCommand, CanICommand, CliCommand, GetCommand
from .context import CommandContext


class XenageCliApp:
    def __init__(self) -> None:
        self.commands: dict[str, CliCommand] = {
            "get": GetCommand(),
            "apply": ApplyCommand(),
            "auth-can-i": CanICommand(),
            "can-i": CanICommand(),
        }

    def build_parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(prog="xenage")
        parser.add_argument("--config", help="Path to cluster connection config (yaml)")
        subparsers = parser.add_subparsers(dest="command", required=True)

        get_parser = subparsers.add_parser("get")
        get_parser.add_argument(
            "resource",
            choices=["nodes", "group-config", "events", "state", "serviceaccounts", "roles", "rolebindings"],
        )
        get_parser.add_argument("-o", "--output", choices=["table", "json", "yaml"], default="table")
        get_parser.add_argument("--limit", type=int, default=50)
        get_parser.add_argument("--namespace", default="default")

        apply_parser = subparsers.add_parser("apply")
        apply_parser.add_argument("-f", "--filename", required=True)
        apply_parser.add_argument("-o", "--output", choices=["table", "json", "yaml"], default="table")

        auth_parser = subparsers.add_parser("auth")
        auth_subparsers = auth_parser.add_subparsers(dest="auth_command", required=True)
        can_i_parser = auth_subparsers.add_parser("can-i")
        can_i_parser.add_argument("verb")
        can_i_parser.add_argument("resource")
        can_i_parser.add_argument("--namespace", default="default")

        top_can_i_parser = subparsers.add_parser("can-i")
        top_can_i_parser.add_argument("verb")
        top_can_i_parser.add_argument("resource")
        top_can_i_parser.add_argument("--namespace", default="default")

        return parser

    def execute(self, argv: list[str]) -> int:
        parser = self.build_parser()
        args = parser.parse_args(argv)
        config_path = self._resolve_config_path(args.config)
        client = ControlPlaneClient.from_yaml(config_path)
        context = CommandContext(client=client)

        command_key = str(args.command)
        if command_key == "auth":
            command_key = "auth-can-i"

        command = self.commands.get(command_key)
        if command is None:
            raise RuntimeError(f"unsupported command: {command_key}")
        return command.run(args, context)

    def _resolve_config_path(self, provided_path: str | None) -> str:
        if provided_path:
            return provided_path
        default_path = Path.home() / ".xenage" / "config.yaml"
        if default_path.exists():
            return str(default_path)
        raise RuntimeError("--config not provided and ~/.xenage/config.yaml not found")


def xenage_cli_main() -> None:
    app = XenageCliApp()
    exit_code = app.execute(sys.argv[1:])
    if exit_code != 0:
        raise SystemExit(exit_code)
