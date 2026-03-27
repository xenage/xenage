from __future__ import annotations

import msgspec
from typing import Literal, TypeAlias

from ...base import Structure


def _detail_value(value: object) -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    if isinstance(value, (bool, int, float)):
        return str(value)
    return msgspec.json.encode(value).decode("utf-8")


class ClusterAuditEventBase(Structure, tag_field="event_type"):
    kind = "ClusterAuditEventBase"

    def action(self) -> str:
        payload = msgspec.to_builtins(self)
        event_type = payload.get("event_type", "")
        if not isinstance(event_type, str) or not event_type:
            raise ValueError("event_type is required")
        return event_type

    def details(self) -> dict[str, str]:
        payload = msgspec.to_builtins(self)
        payload.pop("event_type", None)
        return {key: _detail_value(value) for key, value in payload.items()}


class ClusterBootstrapEvent(ClusterAuditEventBase, tag="cluster.bootstrap"):
    kind = "ClusterBootstrapEvent"
    group_id: str
    leader_node_id: str


class RbacAdminUserUpsertEvent(ClusterAuditEventBase, tag="rbac.admin.user.upsert"):
    kind = "RbacAdminUserUpsertEvent"
    user_id: str


class ClusterNodeJoinedEvent(ClusterAuditEventBase, tag="cluster.node.joined"):
    kind = "ClusterNodeJoinedEvent"
    node_id: str
    role: Literal["control-plane", "runtime"]
    state_version: int


class ClusterNodeRevokedEvent(ClusterAuditEventBase, tag="cluster.node.revoked"):
    kind = "ClusterNodeRevokedEvent"
    node_id: str
    state_version: int


class ClusterNodeEndpointsUpdatedEvent(ClusterAuditEventBase, tag="cluster.node.endpoints.updated"):
    kind = "ClusterNodeEndpointsUpdatedEvent"
    node_id: str
    state_version: int


class ClusterFailoverPromotedEvent(ClusterAuditEventBase, tag="cluster.failover.promoted"):
    kind = "ClusterFailoverPromotedEvent"
    leader_node_id: str
    previous_leader_node_id: str
    leader_epoch: int


class GuiClusterSnapshotReadEvent(ClusterAuditEventBase, tag="gui.cluster.snapshot.read"):
    kind = "GuiClusterSnapshotReadEvent"
    user_id: str


ClusterAuditEvent: TypeAlias = (
    ClusterBootstrapEvent
    | RbacAdminUserUpsertEvent
    | ClusterNodeJoinedEvent
    | ClusterNodeRevokedEvent
    | ClusterNodeEndpointsUpdatedEvent
    | ClusterFailoverPromotedEvent
    | GuiClusterSnapshotReadEvent
)
