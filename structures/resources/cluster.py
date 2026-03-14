from __future__ import annotations

import msgspec
from typing import Literal

from ..base import Structure
from ..common import ObjectMeta
from .base import ResourceDocument


class ClusterSpec(Structure):
    kind = "ClusterSpec"
    displayName: str
    provider: str
    region: str
    runtimeVersion: str
    controlPlaneEndpoint: str


class ClusterStatus(Structure):
    kind = "ClusterStatus"
    phase: Literal["Provisioning", "Ready", "Degraded"]
    health: Literal["Healthy", "Warning", "Critical"]
    nodesReady: int
    agentsReady: int
    activeAlerts: int = 0


class Cluster(ResourceDocument):
    kind = "Cluster"
    metadata: ObjectMeta = ObjectMeta(name="demo-cluster")
    spec: ClusterSpec = ClusterSpec(
        displayName="Demo Cluster",
        provider="Bare Metal",
        region="fra-1",
        runtimeVersion="0.1.0",
        controlPlaneEndpoint="https://control.demo.xenage.local",
    )
    status: ClusterStatus = ClusterStatus(
        phase="Ready",
        health="Healthy",
        nodesReady=6,
        agentsReady=23,
        activeAlerts=1,
    )


class NodeSpec(Structure):
    kind = "NodeSpec"
    role: Literal["control-plane", "worker", "gpu"]
    architecture: str
    runtime: str
    zone: str
    taints: list[str] = msgspec.field(default_factory=list)


class NodeStatus(Structure):
    kind = "NodeStatus"
    phase: Literal["Ready", "Draining", "Offline"]
    cpuUsagePct: int
    memoryUsagePct: int
    sessionsRunning: int


class Node(ResourceDocument):
    kind = "Node"
    metadata: ObjectMeta = ObjectMeta(name="node-a", labels={"topology.kubernetes.io/zone": "fra-1a"})
    spec: NodeSpec = NodeSpec(role="worker", architecture="arm64", runtime="containerd", zone="fra-1a")
    status: NodeStatus = NodeStatus(phase="Ready", cpuUsagePct=48, memoryUsagePct=61, sessionsRunning=14)
