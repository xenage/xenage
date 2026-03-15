from __future__ import annotations

import msgspec
from typing import TypeAlias, Literal

from ...base import Structure
from ..membership import GroupState, GroupNodeSyncStatus, UserState, NodeRecord, GroupEndpoint, UserRecord, EventLogEntry


class ControlPlaneSyncEventBase(Structure, tag_field="event_type", kw_only=True):
    kind = "ControlPlaneSyncEventBase"
    event_id: int
    happened_at: str
    actor_node_id: str
    nonce: str = ""


class GroupStateApplyEvent(ControlPlaneSyncEventBase, tag="group_state.apply"):
    kind = "GroupStateApplyEvent"
    group_state: GroupState
    version: int


class UserStateApplyEvent(ControlPlaneSyncEventBase, tag="user_state.apply"):
    kind = "UserStateApplyEvent"
    user_state: UserState
    version: int


class GroupNodeJoinedEvent(ControlPlaneSyncEventBase, tag="group.node_joined"):
    kind = "GroupNodeJoinedEvent"
    node: NodeRecord
    endpoints: list[GroupEndpoint]
    version: int
    expires_at: str


class GroupNodeRevokedEvent(ControlPlaneSyncEventBase, tag="group.node_revoked"):
    kind = "GroupNodeRevokedEvent"
    node_id: str
    version: int
    expires_at: str


class GroupEndpointsUpdatedEvent(ControlPlaneSyncEventBase, tag="group.endpoints_updated"):
    kind = "GroupEndpointsUpdatedEvent"
    node_id: str
    endpoints: list[GroupEndpoint]
    version: int
    expires_at: str


class GroupLeaderPromotedEvent(ControlPlaneSyncEventBase, tag="group.leader_promoted"):
    kind = "GroupLeaderPromotedEvent"
    leader_node_id: str
    leader_pubkey: str
    leader_epoch: int
    version: int
    expires_at: str
    leader_signature: str = ""
    control_planes: list[NodeRecord] | None = msgspec.field(default=None)
    runtimes: list[NodeRecord] | None = msgspec.field(default=None)
    endpoints: list[GroupEndpoint] | None = msgspec.field(default=None)
    node_statuses: list[GroupNodeSyncStatus] | None = msgspec.field(default=None)


class UserUpsertedEvent(ControlPlaneSyncEventBase, tag="user.upserted"):
    kind = "UserUpsertedEvent"
    user: UserRecord
    version: int


class UserEventAppendedEvent(ControlPlaneSyncEventBase, tag="user.event_appended"):
    kind = "UserEventAppendedEvent"
    event: EventLogEntry
    version: int


ControlPlaneSyncEvent: TypeAlias = (
    GroupStateApplyEvent
    | UserStateApplyEvent
    | GroupNodeJoinedEvent
    | GroupNodeRevokedEvent
    | GroupEndpointsUpdatedEvent
    | GroupLeaderPromotedEvent
    | UserUpsertedEvent
    | UserEventAppendedEvent
)


class ControlPlaneEventLog(Structure):
    kind = "ControlPlaneEventLog"
    items: list[ControlPlaneSyncEvent] = msgspec.field(default_factory=list)


class ControlPlaneEventPage(Structure):
    kind = "ControlPlaneEventPage"
    leader_node_id: str
    last_event_id: int
    items: list[ControlPlaneSyncEvent] = msgspec.field(default_factory=list)
    has_more: bool = False
    leader_pubkey: str = ""
    leader_epoch: int = 0
    last_event_nonce: str = ""
    state_hash: str = ""
