from __future__ import annotations

from typing import Literal

import msgspec

from ..base import Structure
from .base import ResourceDocument


class NodeMeta(Structure):
    kind = "NodeMeta"
    name: str
    labels: dict[str, str] = msgspec.field(default_factory=dict)
    annotations: dict[str, str] = msgspec.field(default_factory=dict)
    uid: str | None = None
    generation: int = 1
    createdAt: str | None = None


class NodeSpec(Structure):
    kind = "NodeSpec"
    nodeId: str
    role: Literal["control-plane", "runtime"]
    publicKey: str
    endpoints: list[str] = msgspec.field(default_factory=list)


class NodeStatus(Structure):
    kind = "NodeStatus"
    phase: Literal["Connected", "Unreachable"]
    leader: bool
    lastSeenAt: str


class Node(ResourceDocument):
    kind = "Node"
    metadata: NodeMeta = NodeMeta(name="cp-1")
    spec: NodeSpec = NodeSpec(
        nodeId="cp-1",
        role="control-plane",
        publicKey="base64-public-key",
        endpoints=["http://127.0.0.1:8734"],
    )
    status: NodeStatus = NodeStatus(
        phase="Connected",
        leader=True,
        lastSeenAt="2026-03-14T12:24:00Z",
    )
