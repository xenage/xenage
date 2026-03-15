from __future__ import annotations

import msgspec
from typing import Annotated, Literal

from ..base import Structure
from ..common import ObjectMeta
from .base import ResourceDocument


NodeRole = Literal["control-plane", "runtime"]
NodeSyncPhase = Literal["unknown", "syncing", "synced", "broken"]


class NodeRecord(Structure):
    kind = "NodeRecord"
    node_id: str
    role: NodeRole
    public_key: str
    endpoints: list[str] = msgspec.field(default_factory=list)


class GroupEndpoint(Structure):
    kind = "GroupEndpoint"
    node_id: str
    url: str


class GroupNodeSyncStatus(Structure):
    kind = "GroupNodeSyncStatus"
    node_id: str
    status: NodeSyncPhase = "unknown"
    reason: str = ""
    updated_at: str = ""


class GroupState(Structure):
    kind = "GroupState"
    group_id: str
    version: int
    leader_epoch: int
    leader_node_id: str
    leader_pubkey: str
    control_planes: list[NodeRecord]
    runtimes: list[NodeRecord]
    endpoints: list[GroupEndpoint]
    expires_at: str
    node_statuses: list[GroupNodeSyncStatus] = msgspec.field(default_factory=list)
    leader_signature: str = ""


class GroupConfigSpec(Structure):
    kind = "GroupConfigSpec"
    groupId: str
    stateVersion: int
    leaderEpoch: int
    leaderNodeId: str
    leaderPubkey: str
    controlPlanes: list[NodeRecord]
    runtimes: list[NodeRecord]
    endpoints: list[GroupEndpoint]
    expiresAt: str
    nodeStatuses: list[GroupNodeSyncStatus] = msgspec.field(default_factory=list)


class GroupConfigStatus(Structure):
    kind = "GroupConfigStatus"
    phase: Literal["Active", "Stale"]
    controlPlaneCount: int
    runtimeCount: int


class GroupConfig(ResourceDocument):
    kind = "GroupConfig"
    metadata: ObjectMeta = ObjectMeta(name="main")
    spec: GroupConfigSpec = GroupConfigSpec(
        groupId="demo",
        stateVersion=42,
        leaderEpoch=3,
        leaderNodeId="cp-1",
        leaderPubkey="base64-public-key",
        controlPlanes=[
            NodeRecord(node_id="cp-1", role="control-plane", public_key="base64-public-key", endpoints=["http://127.0.0.1:8734"])
        ],
        runtimes=[
            NodeRecord(node_id="rt-1", role="runtime", public_key="base64-runtime-key", endpoints=["http://127.0.0.1:8735"])
        ],
        endpoints=[
            GroupEndpoint(node_id="cp-1", url="http://127.0.0.1:8734"),
            GroupEndpoint(node_id="rt-1", url="http://127.0.0.1:8735"),
        ],
        expiresAt="2026-03-14T12:30:00Z",
    )
    status: GroupConfigStatus = GroupConfigStatus(phase="Active", controlPlaneCount=1, runtimeCount=1)


class StoredNodeIdentity(Structure):
    kind = "StoredNodeIdentity"
    node_id: str
    role: NodeRole
    public_key: str
    private_key: str
    endpoints: list[str] = msgspec.field(default_factory=list)


class RequestAuth(Structure):
    kind = "RequestAuth"
    node_id: str
    timestamp: int
    nonce: str
    signature: str


class JoinRequest(Structure):
    kind = "JoinRequest"
    bootstrap_token: str
    node: NodeRecord


class JoinResponse(Structure):
    kind = "JoinResponse"
    accepted: bool
    reason: str | None = None
    group_state: GroupState | None = None


class RevokeNodeRequest(Structure):
    kind = "RevokeNodeRequest"
    node_id: str


class EndpointUpdateRequest(Structure):
    kind = "EndpointUpdateRequest"
    node_id: str
    endpoints: list[str]


class BootstrapTokenRecord(Structure):
    kind = "BootstrapTokenRecord"
    token: str
    issued_at: int
    expires_at: int
    used: bool = False


class BootstrapTokenSet(Structure):
    kind = "BootstrapTokenSet"
    items: list[BootstrapTokenRecord] = msgspec.field(default_factory=list)


class SignedBody(Structure):
    kind = "SignedBody"
    auth: RequestAuth
    payload: bytes = b""


class UserRoleBinding(Structure):
    kind = "UserRoleBinding"
    role: Literal["admin"] = "admin"


class UserRecord(Structure):
    kind = "UserRecord"
    user_id: str
    public_key: str
    roles: list[UserRoleBinding] = msgspec.field(default_factory=lambda: [UserRoleBinding()])
    created_at: str = ""
    enabled: bool = True


class EventLogEntry(Structure):
    kind = "EventLogEntry"
    sequence: int
    happened_at: str
    actor_id: str
    actor_type: Literal["node", "user", "system"]
    action: str
    details: dict[str, str] = msgspec.field(default_factory=dict)


class UserState(Structure):
    kind = "UserState"
    version: int = 0
    users: list[UserRecord] = msgspec.field(default_factory=list)
    event_log: list[EventLogEntry] = msgspec.field(default_factory=list)


class ControlPlaneSyncStatusRequest(Structure):
    kind = "ControlPlaneSyncStatusRequest"
    status: Literal["syncing", "synced", "broken"]
    reason: str = ""


class ClusterNodeTableRow(Structure):
    kind = "ClusterNodeTableRow"
    node_id: str
    role: NodeRole
    leader: bool
    public_key: Annotated[str, "display_only"]
    endpoints: list[str] = msgspec.field(default_factory=list)
    status: str = ""
    name: str = ""
    version: str = ""
    age: str = ""
    last_poll_at: str = ""


class GroupConfigKeyTableRow(Structure):
    kind = "GroupConfigKeyTableRow"
    key: str
    value: str


class GuiClusterSnapshot(Structure):
    kind = "GuiClusterSnapshot"
    group_id: str
    state_version: int
    leader_epoch: int
    nodes: list[ClusterNodeTableRow] = msgspec.field(default_factory=list)
    group_config: list[GroupConfigKeyTableRow] = msgspec.field(default_factory=list)
    users: list[UserRecord] = msgspec.field(default_factory=list)


class GuiEventPage(Structure):
    kind = "GuiEventPage"
    items: list[EventLogEntry] = msgspec.field(default_factory=list)
    has_more: bool = False
    next_before_sequence: int = 0


class GuiConnectionConfig(Structure):
    kind = "GuiConnectionConfig"
    cluster_name: str
    control_plane_urls: list[str]
    user_id: str
    public_key: str
    private_key: str
    role: Literal["admin"] = "admin"


class GuiUserBootstrapRequest(Structure):
    kind = "GuiUserBootstrapRequest"
    bootstrap_token: str
    user_id: str = "admin"
    public_key: str = ""
    control_plane_urls: list[str] = msgspec.field(default_factory=list)


class GuiUserBootstrapResponse(Structure):
    kind = "GuiUserBootstrapResponse"
    cluster_name: str
    control_plane_urls: list[str]
    user_id: str
    public_key: str
    role: Literal["admin"] = "admin"
