from __future__ import annotations

import hashlib

import msgspec
from loguru import logger

from structures.resources.events import (
    ClusterAuditEventAppendedEvent,
    ControlPlaneEventLog,
    ControlPlaneEventPage,
    ControlPlaneSyncEvent,
    GroupEndpointsUpdatedEvent,
    GroupLeaderPromotedEvent,
    GroupNodeJoinedEvent,
    GroupNodeRevokedEvent,
    GroupStateApplyEvent,
    RbacStateApplyEvent,
    UserEventAppendedEvent,
    UserStateApplyEvent,
    UserUpsertedEvent,
)
from structures.resources.membership import EventLogEntry, GroupState, NodeRecord, UserRecord
from structures.resources.rbac import RbacState

from ..crypto import make_nonce
from ..persistence.storage_layer import StorageLayer
from .rbac_state_manager import RbacStateManager
from .state_manager import StateManager, StateVersionRegressedError
from .time_utils import format_timestamp, utc_now


class ControlPlaneEventSyncError(RuntimeError):
    pass


class ControlPlaneEventManager:
    def __init__(self, storage: StorageLayer, state_manager: StateManager, rbac_state_manager: RbacStateManager) -> None:
        self.storage = storage
        self.state_manager = state_manager
        self.rbac_state_manager = rbac_state_manager
        self.current = storage.load_control_plane_event_log()
        logger.debug("control-plane event manager initialized items={}", len(self.current.items))

    def get_last_event_id(self) -> int:
        return self.current.items[-1].event_id if self.current.items else 0

    def get_last_event_nonce(self) -> str:
        return self.current.items[-1].nonce if self.current.items else ""

    def current_state_hash(self) -> str:
        rbac_state = self.rbac_state_manager.get_state()
        events_payload = msgspec.json.encode(self.current)
        rbac_payload = msgspec.json.encode(rbac_state)
        return hashlib.sha256(events_payload + b"\n" + rbac_payload).hexdigest()

    def cluster_audit_events(self) -> list[EventLogEntry]:
        items: list[EventLogEntry] = []
        has_cluster_audit = any(isinstance(sync_event, ClusterAuditEventAppendedEvent) for sync_event in self.current.items)
        for sync_event in self.current.items:
            if isinstance(sync_event, ClusterAuditEventAppendedEvent):
                items.append(sync_event.event)
            elif isinstance(sync_event, UserEventAppendedEvent) and not has_cluster_audit:
                # Legacy compatibility for old persisted logs.
                items.append(sync_event.event)
        return items

    def _next_audit_sequence(self) -> int:
        entries = self.cluster_audit_events()
        return (entries[-1].sequence + 1) if entries else 1

    def _persist(self) -> None:
        self.storage.save_control_plane_event_log(self.current)

    def _append(self, event: ControlPlaneSyncEvent) -> None:
        expected = self.get_last_event_id() + 1
        if event.event_id != expected:
            raise ControlPlaneEventSyncError(f"event id gap: expected {expected}, got {event.event_id}")
        self.current = ControlPlaneEventLog(items=[*self.current.items, event])
        self._persist()

    def record_group_state(self, actor_node_id: str, group_state: GroupState) -> GroupStateApplyEvent:
        event = GroupStateApplyEvent(
            event_id=self.get_last_event_id() + 1,
            happened_at=format_timestamp(utc_now()),
            actor_node_id=actor_node_id,
            nonce=make_nonce(),
            group_state=group_state,
            version=group_state.version,
        )
        self._append(event)
        logger.debug("recorded group-state sync event event_id={} state_version={}", event.event_id, group_state.version)
        return event

    def record_rbac_state(self, actor_node_id: str, rbac_state: RbacState) -> RbacStateApplyEvent:
        event = RbacStateApplyEvent(
            event_id=self.get_last_event_id() + 1,
            happened_at=format_timestamp(utc_now()),
            actor_node_id=actor_node_id,
            nonce=make_nonce(),
            rbac_state=rbac_state,
            version=rbac_state.version,
        )
        self._append(event)
        logger.debug("recorded rbac-state sync event event_id={} rbac_state_version={}", event.event_id, rbac_state.version)
        return event

    def record_cluster_audit_event(
        self,
        actor_node_id: str,
        actor_type: str,
        action: str,
        details: dict[str, str] | None = None,
    ) -> ClusterAuditEventAppendedEvent:
        event_entry = EventLogEntry(
            sequence=self._next_audit_sequence(),
            happened_at=format_timestamp(utc_now()),
            actor_id=actor_node_id,
            actor_type=actor_type,
            action=action,
            details=details or {},
        )
        event = ClusterAuditEventAppendedEvent(
            event_id=self.get_last_event_id() + 1,
            happened_at=format_timestamp(utc_now()),
            actor_node_id=actor_node_id,
            nonce=make_nonce(),
            event=event_entry,
        )
        self._append(event)
        return event

    def record_user_upserted(self, actor_node_id: str, user: UserRecord, version: int) -> UserUpsertedEvent:
        event = UserUpsertedEvent(
            event_id=self.get_last_event_id() + 1,
            happened_at=format_timestamp(utc_now()),
            actor_node_id=actor_node_id,
            nonce=make_nonce(),
            user=user,
            version=version,
        )
        self._append(event)
        return event

    def record_user_event_appended(self, actor_node_id: str, event_entry: EventLogEntry, version: int) -> UserEventAppendedEvent:
        event = UserEventAppendedEvent(
            event_id=self.get_last_event_id() + 1,
            happened_at=format_timestamp(utc_now()),
            actor_node_id=actor_node_id,
            nonce=make_nonce(),
            event=event_entry,
            version=version,
        )
        self._append(event)
        return event

    def event_page(self, leader_node_id: str, after_event_id: int, limit: int) -> ControlPlaneEventPage:
        safe_limit = max(1, min(limit, 500))
        offset = 0
        if after_event_id > 0:
            while offset < len(self.current.items) and self.current.items[offset].event_id <= after_event_id:
                offset += 1
        items = self.current.items[offset : offset + safe_limit]
        has_more = offset + safe_limit < len(self.current.items)

        state = self.state_manager.get_state()
        leader_pubkey = state.leader_pubkey if state else ""
        leader_epoch = state.leader_epoch if state else 0

        return ControlPlaneEventPage(
            leader_node_id=leader_node_id,
            leader_pubkey=leader_pubkey,
            leader_epoch=leader_epoch,
            last_event_id=self.get_last_event_id(),
            last_event_nonce=self.get_last_event_nonce(),
            state_hash=self.current_state_hash(),
            items=items,
            has_more=has_more,
        )

    def record_node_joined(self, actor_node_id: str, node: NodeRecord, group_state: GroupState) -> GroupNodeJoinedEvent:
        event = GroupNodeJoinedEvent(
            event_id=self.get_last_event_id() + 1,
            happened_at=format_timestamp(utc_now()),
            actor_node_id=actor_node_id,
            nonce=make_nonce(),
            node=node,
            endpoints=group_state.endpoints,
            version=group_state.version,
            expires_at=group_state.expires_at,
        )
        self._append(event)
        return event

    def record_node_revoked(self, actor_node_id: str, node_id: str, group_state: GroupState) -> GroupNodeRevokedEvent:
        event = GroupNodeRevokedEvent(
            event_id=self.get_last_event_id() + 1,
            happened_at=format_timestamp(utc_now()),
            actor_node_id=actor_node_id,
            nonce=make_nonce(),
            node_id=node_id,
            version=group_state.version,
            expires_at=group_state.expires_at,
        )
        self._append(event)
        return event

    def record_endpoints_updated(self, actor_node_id: str, node_id: str, group_state: GroupState) -> GroupEndpointsUpdatedEvent:
        event = GroupEndpointsUpdatedEvent(
            event_id=self.get_last_event_id() + 1,
            happened_at=format_timestamp(utc_now()),
            actor_node_id=actor_node_id,
            nonce=make_nonce(),
            node_id=node_id,
            endpoints=group_state.endpoints,
            version=group_state.version,
            expires_at=group_state.expires_at,
        )
        self._append(event)
        return event

    def record_leader_promoted(self, actor_node_id: str, group_state: GroupState) -> GroupLeaderPromotedEvent:
        event = GroupLeaderPromotedEvent(
            event_id=self.get_last_event_id() + 1,
            happened_at=format_timestamp(utc_now()),
            actor_node_id=actor_node_id,
            nonce=make_nonce(),
            leader_node_id=group_state.leader_node_id,
            leader_pubkey=group_state.leader_pubkey,
            leader_epoch=group_state.leader_epoch,
            version=group_state.version,
            expires_at=group_state.expires_at,
            leader_signature=group_state.leader_signature,
            control_planes=group_state.control_planes,
            runtimes=group_state.runtimes,
            endpoints=group_state.endpoints,
            node_statuses=group_state.node_statuses,
        )
        self._append(event)
        return event

    def apply_remote_event(self, event: ControlPlaneSyncEvent, trusted_leader_pubkey: str | None = None) -> bool:
        last_event_id = self.get_last_event_id()
        if event.event_id <= last_event_id:
            logger.trace("skipping already applied event event_id={} local_last={}", event.event_id, last_event_id)
            return False

        try:
            if isinstance(event, GroupStateApplyEvent):
                current = self.state_manager.get_state()
                if current and event.version < current.version:
                    logger.warning(
                        "skipping remote event application because state version regressed: event_id={} error=group_state version regressed",
                        event.event_id,
                    )
                else:
                    self.state_manager.replace_state(event.group_state, trusted_leader_pubkey=trusted_leader_pubkey)
                    logger.info("applied remote group-state event event_id={} state_version={}", event.event_id, event.group_state.version)
            elif isinstance(event, RbacStateApplyEvent):
                current = self.rbac_state_manager.get_state()
                if current and event.version < current.version:
                    logger.warning(
                        "skipping remote event application because rbac state version regressed: event_id={} error=rbac_state version regressed",
                        event.event_id,
                    )
                else:
                    self.rbac_state_manager.replace_state(event.rbac_state)
                    logger.info("applied remote rbac-state event event_id={} rbac_state_version={}", event.event_id, event.rbac_state.version)
            elif isinstance(event, GroupNodeJoinedEvent):
                state = self.state_manager.require_state()
                control_planes = [item for item in state.control_planes if item.node_id != event.node.node_id]
                runtimes = [item for item in state.runtimes if item.node_id != event.node.node_id]
                if event.node.role == "control-plane":
                    control_planes.append(event.node)
                else:
                    runtimes.append(event.node)
                new_state = GroupState(
                    group_id=state.group_id,
                    version=event.version,
                    leader_epoch=state.leader_epoch,
                    leader_node_id=state.leader_node_id,
                    leader_pubkey=state.leader_pubkey,
                    control_planes=control_planes,
                    runtimes=runtimes,
                    endpoints=event.endpoints,
                    node_statuses=state.node_statuses,
                    expires_at=event.expires_at,
                    leader_signature="",
                )
                self.state_manager.replace_state(new_state, trusted_leader_pubkey=trusted_leader_pubkey, verify_signature_required=False)
            elif isinstance(event, GroupNodeRevokedEvent):
                state = self.state_manager.require_state()
                control_planes = [item for item in state.control_planes if item.node_id != event.node_id]
                runtimes = [item for item in state.runtimes if item.node_id != event.node_id]
                endpoints = [item for item in state.endpoints if item.node_id != event.node_id]
                new_state = GroupState(
                    group_id=state.group_id,
                    version=event.version,
                    leader_epoch=state.leader_epoch,
                    leader_node_id=state.leader_node_id,
                    leader_pubkey=state.leader_pubkey,
                    control_planes=control_planes,
                    runtimes=runtimes,
                    endpoints=endpoints,
                    node_statuses=state.node_statuses,
                    expires_at=event.expires_at,
                    leader_signature="",
                )
                self.state_manager.replace_state(new_state, trusted_leader_pubkey=trusted_leader_pubkey, verify_signature_required=False)
            elif isinstance(event, GroupEndpointsUpdatedEvent):
                state = self.state_manager.require_state()
                new_state = GroupState(
                    group_id=state.group_id,
                    version=event.version,
                    leader_epoch=state.leader_epoch,
                    leader_node_id=state.leader_node_id,
                    leader_pubkey=state.leader_pubkey,
                    control_planes=state.control_planes,
                    runtimes=state.runtimes,
                    endpoints=event.endpoints,
                    node_statuses=state.node_statuses,
                    expires_at=event.expires_at,
                    leader_signature="",
                )
                self.state_manager.replace_state(new_state, trusted_leader_pubkey=trusted_leader_pubkey, verify_signature_required=False)
            elif isinstance(event, GroupLeaderPromotedEvent):
                state = self.state_manager.require_state()
                control_planes = event.control_planes if event.control_planes is not None else state.control_planes
                runtimes = event.runtimes if event.runtimes is not None else state.runtimes
                endpoints = event.endpoints if event.endpoints is not None else state.endpoints
                node_statuses = event.node_statuses if event.node_statuses is not None else state.node_statuses
                new_state = GroupState(
                    group_id=state.group_id,
                    version=event.version,
                    leader_epoch=event.leader_epoch,
                    leader_node_id=event.leader_node_id,
                    leader_pubkey=event.leader_pubkey,
                    control_planes=control_planes,
                    runtimes=runtimes,
                    endpoints=endpoints,
                    node_statuses=node_statuses,
                    expires_at=event.expires_at,
                    leader_signature=event.leader_signature,
                )
                self.state_manager.replace_state(new_state, trusted_leader_pubkey=trusted_leader_pubkey)
            elif isinstance(event, ClusterAuditEventAppendedEvent):
                pass
            elif isinstance(event, UserStateApplyEvent | UserUpsertedEvent | UserEventAppendedEvent):
                # Legacy compatibility: old user-state events are accepted but ignored.
                logger.warning("ignoring legacy user-state sync event event_id={} type={}", event.event_id, type(event).__name__)
            else:
                raise ControlPlaneEventSyncError(f"unsupported event type {type(event)!r}")
        except StateVersionRegressedError as exc:
            logger.warning(
                "skipping remote event application because state version regressed: event_id={} error={}",
                event.event_id,
                str(exc),
            )
        except Exception as exc:
            if "version regressed" in str(exc).lower():
                logger.warning(
                    "skipping remote event application because state version regressed: event_id={} error={}",
                    event.event_id,
                    str(exc),
                )
            else:
                raise

        self._append(event)
        return True

    def apply_remote_events(self, events: list[ControlPlaneSyncEvent], trusted_leader_pubkey: str | None = None) -> int:
        applied = 0
        for event in events:
            if self.apply_remote_event(event, trusted_leader_pubkey=trusted_leader_pubkey):
                applied += 1
        return applied

    @staticmethod
    def decode_event_page(payload: bytes) -> ControlPlaneEventPage:
        return msgspec.json.decode(payload, type=ControlPlaneEventPage)
