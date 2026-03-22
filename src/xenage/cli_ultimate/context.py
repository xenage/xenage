from __future__ import annotations

from dataclasses import dataclass

from xenage.network.cli_client import ControlPlaneClient


@dataclass(frozen=True)
class CommandContext:
    client: ControlPlaneClient
