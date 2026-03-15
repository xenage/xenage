from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Literal

from loguru import logger

from structures.resources.events import (
    ClusterAuditEventBase,
    ClusterBootstrapEvent,
    ClusterFailoverPromotedEvent,
    ClusterNodeEndpointsUpdatedEvent,
    ClusterNodeJoinedEvent,
    ClusterNodeRevokedEvent,
    RbacAdminUserUpsertEvent,
)
from structures.resources.membership import (
    GroupEndpoint,
    GroupState,
    JoinRequest,
    NodeRecord,
    NodeRole,
    UserRecord,
)

from ...cluster.time_utils import parse_timestamp, utc_now
from ...network.http_transport import TransportError
from .sync_logic import EventHistoryAheadError
from .utils import sort_control_planes

if TYPE_CHECKING:
    from .main import ControlPlaneNode


class ControlPlaneStateLogic:
    def __init__(self, node: ControlPlaneNode) -> None:
        self.node = node

    @staticmethod
    def _normalize_endpoints(endpoints: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for endpoint in endpoints:
            value = endpoint.strip()
            if not value or value in seen:
                continue
            seen.add(value)
            normalized.append(value)
        return normalized

    @staticmethod
    def _node_role(state: GroupState, node_id: str) -> NodeRole | None:
        for item in state.control_planes:
            if item.node_id == node_id:
                return "control-plane"
        for item in state.runtimes:
            if item.node_id == node_id:
                return "runtime"
        return None

    def initialize_group(self, group_id: str, ttl_seconds: int) -> GroupState:
        logger.info("bootstrapping self-managed group group_id={}", group_id)
        state = self.node.state_manager.bootstrap_state(
            group_id,
            self.node.node_record(),
            [GroupEndpoint(node_id=self.node.identity.node_id, url=url) for url in self.node.identity.endpoints],
            ttl_seconds,
            self.node.key_pair,
        )
        self.node.event_manager.record_group_state(self.node.identity.node_id, state)
        self.node.upsert_sync_status(self.node.identity.node_id, "synced")
        
        # Audit event
        self.node.append_cluster_event(
            ClusterBootstrapEvent(group_id=group_id, leader_node_id=self.node.identity.node_id),
        )
        return self.node.state_with_sync_statuses(state)

    def apply_join(self, join_request: JoinRequest, ttl_seconds: int) -> GroupState:
        state = self.node.require_leader()
        logger.info("apply_join_start node_id={} role={}", join_request.node.node_id, join_request.node.role)
        logger.debug(
            "applying join request node_id={} role={} ttl_seconds={} endpoints={}",
            join_request.node.node_id,
            join_request.node.role,
            ttl_seconds,
            join_request.node.endpoints
        )
        self.node.tokens.validate(join_request.bootstrap_token)
        self.node.tokens.mark_used(join_request.bootstrap_token)
        
        new_node = join_request.node
        normalized_endpoints = self._normalize_endpoints(new_node.endpoints)
        if new_node.role == "runtime" and new_node.endpoints:
            logger.warning(
                "runtime join included endpoints; dropping endpoints for poll-only mode node_id={} endpoint_count={}",
                new_node.node_id,
                len(new_node.endpoints),
            )
            new_node = NodeRecord(
                node_id=new_node.node_id,
                role=new_node.role,
                public_key=new_node.public_key,
                endpoints=[],
            )
        elif normalized_endpoints != new_node.endpoints:
            new_node = NodeRecord(
                node_id=new_node.node_id,
                role=new_node.role,
                public_key=new_node.public_key,
                endpoints=normalized_endpoints,
            )
        control_planes = [item for item in state.control_planes if item.node_id != new_node.node_id]
        runtimes = [item for item in state.runtimes if item.node_id != new_node.node_id]
        
        if new_node.role == "control-plane":
            control_planes.append(new_node)
            self.node.upsert_sync_status(new_node.node_id, "syncing", "waiting for initial event sync")
        else:
            runtimes.append(new_node)
            
        endpoints = [item for item in state.endpoints if item.node_id != new_node.node_id]
        endpoints.extend(GroupEndpoint(node_id=new_node.node_id, url=url) for url in new_node.endpoints)
        
        next_state = self.node.state_manager.build_next_state(
            self.node.identity.node_id,
            self.node.identity.public_key,
            sort_control_planes(control_planes),
            sorted(runtimes, key=lambda item: (item.node_id, item.public_key)),
            sorted(endpoints, key=lambda item: (item.node_id, item.url)),
            ttl_seconds,
            self.node.key_pair,
        )
        applied = self.node.state_manager.replace_state(next_state)
        
        # Diff event
        self.node.event_manager.record_node_joined(self.node.identity.node_id, new_node, applied)
        
        # Audit event
        self.node.append_cluster_event(
            ClusterNodeJoinedEvent(
                node_id=new_node.node_id,
                role=new_node.role,
                state_version=applied.version,
            ),
        )
        logger.info("accepted join node_id={} role={} version={}", new_node.node_id, new_node.role, applied.version)
        return self.node.state_with_sync_statuses(applied)

    def revoke_node(self, node_id: str, ttl_seconds: int) -> GroupState:
        self.node.require_leader()
        logger.info("revoke_node_start node_id={}", node_id)
        logger.debug("revoking node node_id={} ttl_seconds={}", node_id, ttl_seconds)
        state = self.node.state_manager.require_state()
        node_role = self._node_role(state, node_id)
        if node_role is None:
            raise TransportError("node not found")
        if node_id == state.leader_node_id:
            raise TransportError("cannot revoke active leader")
        
        control_planes = [item for item in state.control_planes if item.node_id != node_id]
        runtimes = [item for item in state.runtimes if item.node_id != node_id]
        endpoints = [item for item in state.endpoints if item.node_id != node_id]
        
        next_state = self.node.state_manager.build_next_state(
            self.node.identity.node_id,
            self.node.identity.public_key,
            sort_control_planes(control_planes),
            runtimes,
            endpoints,
            ttl_seconds,
            self.node.key_pair,
        )
        applied = self.node.state_manager.replace_state(next_state)
        self.node.sync_status_by_node.pop(node_id, None)
        
        # Diff event
        self.node.event_manager.record_node_revoked(self.node.identity.node_id, node_id, applied)
        
        # Audit event
        self.node.append_cluster_event(
            ClusterNodeRevokedEvent(node_id=node_id, state_version=applied.version),
        )
        logger.info("revoked node node_id={} version={}", node_id, applied.version)
        return self.node.state_with_sync_statuses(applied)

    def update_node_endpoints(self, node_id: str, endpoints: list[str], ttl_seconds: int) -> GroupState:
        self.node.require_leader()
        normalized_endpoints = self._normalize_endpoints(endpoints)
        logger.info("update_endpoints_start node_id={} count={}", node_id, len(normalized_endpoints))
        logger.debug(
            "updating node endpoints node_id={} endpoints={} ttl_seconds={}",
            node_id,
            normalized_endpoints,
            ttl_seconds,
        )
        state = self.node.state_manager.require_state()
        node_role = self._node_role(state, node_id)
        if node_role is None:
            raise TransportError("node not found")
        if node_role == "runtime":
            raise TransportError("runtime nodes do not support endpoint updates; runtime connectivity is poll-only")

        control_planes = [
            NodeRecord(
                node_id=item.node_id,
                role=item.role,
                public_key=item.public_key,
                endpoints=normalized_endpoints if item.node_id == node_id else item.endpoints,
            )
            for item in state.control_planes
        ]
        runtimes = [
            NodeRecord(
                node_id=item.node_id,
                role=item.role,
                public_key=item.public_key,
                endpoints=normalized_endpoints if item.node_id == node_id else item.endpoints,
            )
            for item in state.runtimes
        ]
        merged_endpoints = [item for item in state.endpoints if item.node_id != node_id]
        merged_endpoints.extend(GroupEndpoint(node_id=node_id, url=url) for url in normalized_endpoints)
        
        next_state = self.node.state_manager.build_next_state(
            self.node.identity.node_id,
            self.node.identity.public_key,
            sort_control_planes(control_planes),
            runtimes,
            sorted(merged_endpoints, key=lambda item: (item.node_id, item.url)),
            ttl_seconds,
            self.node.key_pair,
        )
        applied = self.node.state_manager.replace_state(next_state)
        
        # Diff event
        self.node.event_manager.record_endpoints_updated(self.node.identity.node_id, node_id, applied)
        
        # Audit event
        self.node.append_cluster_event(
            ClusterNodeEndpointsUpdatedEvent(node_id=node_id, state_version=applied.version),
        )
        logger.info("updated endpoints node_id={} version={}", node_id, applied.version)
        return self.node.state_with_sync_statuses(applied)

    def ensure_admin_user(self, user_id: str, public_key: str) -> UserRecord:
        if not self.node.is_leader():
            logger.debug("skip ensure_admin_user: node is not the active leader node_id={}", self.node.identity.node_id)
            return self.node.user_state_manager.ensure_admin(user_id, public_key, read_only=True)

        existing = self.node.user_state_manager.find_user(user_id)
        if existing is not None:
            return self.node.user_state_manager.ensure_admin(user_id, public_key)

        user = self.node.user_state_manager.ensure_admin(user_id, public_key)
        state = self.node.user_state_manager.get_state()
        
        # Diff event
        self.node.event_manager.record_user_upserted(self.node.identity.node_id, user, state.version)
        
        # Audit event
        self.node.append_cluster_event(RbacAdminUserUpsertEvent(user_id=user_id))
        return user

    def ensure_admin_user_with_bootstrap_token(self, bootstrap_token: str, user_id: str, public_key: str) -> UserRecord:
        self.node.require_leader()
        self.node.gui_tokens.validate(bootstrap_token)
        user = self.ensure_admin_user(user_id, public_key)
        self.node.gui_tokens.mark_used(bootstrap_token)
        return user

    def append_cluster_event(self, event: ClusterAuditEventBase) -> None:
        if not self.node.is_leader():
            logger.debug("skip append_cluster_event: node is not the active leader node_id={} action={}", 
                         self.node.identity.node_id, event.action())
            return

        updated = self.node.user_state_manager.append_event(
            self.node.identity.node_id,
            "node",
            event.action(),
            event.details(),
        )
        # Diff event
        self.node.event_manager.record_user_event_appended(
            self.node.identity.node_id, 
            updated.event_log[-1], 
            updated.version
        )

    async def check_failover(self, ttl_seconds: int) -> GroupState | None:
        state = self.node.state_manager.get_state()
        if state is None:
            return None
        if self.node.broken_sync_reason:
            return None

        # Leader case: renew lease
        if state.leader_node_id == self.node.identity.node_id:
            if self.node.state_manager.is_expired(state, margin_seconds=ttl_seconds // 2):
                # Before renewing a self-leader lease, reconcile with reachable peers.
                # This prevents a restarted/stale former leader from extending an obsolete term
                # while another control plane has already promoted a newer leader.
                peer_urls = [
                    item.url
                    for item in state.endpoints
                    if item.node_id != self.node.identity.node_id
                    and any(cp.node_id == item.node_id for cp in state.control_planes)
                ]
                if peer_urls:
                    try:
                        synced = await self.node.sync_logic.sync_events_from_urls(
                            peer_urls,
                            report_sync_status=False,
                            trusted_leader_pubkey=state.leader_pubkey,
                            raise_on_divergence=True,
                        )
                    except EventHistoryAheadError as exc:
                        await self.node.mark_broken(str(exc), peer_urls)
                        return None
                    if synced is not None:
                        current = self.node.state_manager.get_state()
                        if current is not None and (
                            current.leader_node_id != self.node.identity.node_id
                            or current.leader_epoch > state.leader_epoch
                            or current.version > state.version
                        ):
                            logger.info(
                                "leader lease renewal skipped due to newer peer state node_id={} local_leader={} "
                                "peer_leader={} local_epoch={} peer_epoch={}",
                                self.node.identity.node_id,
                                state.leader_node_id,
                                current.leader_node_id,
                                state.leader_epoch,
                                current.leader_epoch,
                            )
                            return self.node.state_with_sync_statuses(current)
                logger.debug("leader renewing state version={} node_id={}", state.version, self.node.identity.node_id)
                next_state = self.node.state_manager.build_next_state(
                    self.node.identity.node_id,
                    self.node.identity.public_key,
                    sort_control_planes(state.control_planes),
                    state.runtimes,
                    state.endpoints,
                    ttl_seconds,
                    self.node.key_pair,
                    increment_version=False, # Just a lease renewal
                )
                applied = self.node.state_manager.replace_state(next_state)
                # No event for just a lease renewal (no meaningful change)
                return self.node.state_with_sync_statuses(applied)
            return None

        # Non-leader case
        # Check if leader is up
        leader_urls = [item.url for item in state.endpoints if item.node_id == state.leader_node_id]
        leader_alive = False
        for leader_url in leader_urls:
            # We use an explicit check instead of broad try/except for control flow where possible
            # but heartbeat check over network inherently might raise exceptions
            try:
                await self.node.client.get(leader_url, "/v1/heartbeat")
                leader_alive = True
                break
            except Exception:
                continue
        
        if leader_alive:
            # Sync events from leader if it is alive
            await self.node.sync_logic.sync_control_plane_events()
            return self.node.state_manager.get_state()

        # Leader is dead (or unreachable), check if state is expired
        if not self.node.state_manager.is_expired(state):
            return None

        # State is expired, leader is dead. Try to failover.
        # Before failover, sync from all available peers to make sure we have latest state
        peer_urls = [
            item.url
            for item in state.endpoints
            if item.node_id != self.node.identity.node_id
            and item.node_id != state.leader_node_id
            and any(cp.node_id == item.node_id for cp in state.control_planes)
        ]
        try:
            await self.node.sync_logic.sync_from_peers(raise_on_divergence=True)
        except EventHistoryAheadError as exc:
            await self.node.mark_broken(str(exc), peer_urls)
            return None
        state = self.node.state_manager.get_state()
        if state is None or not self.node.state_manager.is_expired(state):
            return state

        # Determine next candidate in strict order
        candidate = self.node.current_failover_candidate(state)
        if candidate is None:
            return None

        # Before promoting self, we MUST try to reach others one last time 
        # to ensure no one else has already promoted themselves.
        # This is especially important for nodes returning from downtime with stale state.
        other_peers = [
            item.url for item in state.endpoints 
            if item.node_id != self.node.identity.node_id
        ]
        if other_peers:
            logger.debug("checking other peers before potential promotion node_id={}", self.node.identity.node_id)
            # Try to sync from ANY other peer. If someone has a newer state, sync_events_from_urls will apply it.
            try:
                synced_state = await self.node.sync_logic.sync_events_from_urls(
                    other_peers,
                    report_sync_status=False,
                    raise_on_divergence=True,
                )
            except EventHistoryAheadError as exc:
                await self.node.mark_broken(str(exc), other_peers)
                return None
            if synced_state:
                # If we synced something, check if we are still expired or if there's a new leader
                if not self.node.state_manager.is_expired(synced_state) or synced_state.leader_node_id != state.leader_node_id:
                    logger.info("detected new state from peers, aborting promotion node_id={}", self.node.identity.node_id)
                    return synced_state
                state = synced_state

        # If it's not us, we check if the candidate is reachable
        if candidate.node_id != self.node.identity.node_id:
            logger.debug("waiting for failover candidate to promote node_id={} candidate={}", self.node.identity.node_id, candidate.node_id)
            candidate_urls = [item.url for item in state.endpoints if item.node_id == candidate.node_id]
            # Try to sync from the candidate just in case they are already leader
            # This also serves as a heartbeat check
            candidate_reachable = False
            for url in candidate_urls:
                try:
                    await self.node.client.get(url, "/v1/heartbeat")
                    candidate_reachable = True
                    break
                except Exception:
                    continue

            if candidate_reachable:
                try:
                    await self.node.sync_logic.sync_events_from_urls(
                        candidate_urls,
                        report_sync_status=False,
                        raise_on_divergence=True,
                    )
                except EventHistoryAheadError as exc:
                    await self.node.mark_broken(str(exc), candidate_urls)
                return None
            
            # Candidate is NOT reachable. If ALL other peers are down, we promote self as leader.
            # We already checked other peers just before this block.
            others_reachable = False
            for url in other_peers:
                try:
                    await self.node.client.get(url, "/v1/heartbeat")
                    others_reachable = True
                    break
                except Exception:
                    continue
            
            if not others_reachable:
                # To prevent multiple nodes from promoting themselves simultaneously when they can't see each other,
                # we should only allow promotion if we are the "best" candidate among all nodes we know about.
                # Since we can't see anyone, we can only rely on the deterministic order.
                # However, if we just promote regardless of order when isolated, we might end up with a split brain.
                # But the instruction says: "If all peers are down - promote self as leader from latest known state"
                
                # Check for "failover escalation" - we only promote if we've been waiting long enough
                # and still no one is reachable. This gives "better" candidates time to promote if they ARE alive.
                # However, the current code doesn't have a clear "waiting since" timestamp for failover.
                # For now, let's just implement the promotion but only if we are the next available candidate
                # who is alive. Since NO one is alive, we are the only candidate.
                logger.warning("all peers down, promoting self as leader node_id={}", self.node.identity.node_id)
            else:
                # Someone else is reachable, but not the current candidate.
                # We should continue to wait, maybe they will promote or the current candidate will come back.
                return None

        # It's our turn to promote (or everyone else is down)!
        previous_leader_node_id = state.leader_node_id
        next_state = self.node.state_manager.build_next_state(
            self.node.identity.node_id,
            self.node.identity.public_key,
            sort_control_planes(state.control_planes),
            state.runtimes,
            state.endpoints,
            ttl_seconds,
            self.node.key_pair,
            leader_epoch=state.leader_epoch + 1,
        )
        applied = self.node.state_manager.replace_state(next_state)
        self.node.upsert_sync_status(self.node.identity.node_id, "synced")
        
        # Diff event
        self.node.event_manager.record_leader_promoted(self.node.identity.node_id, applied)
        
        logger.warning("failover promoted node_id={} epoch={}", self.node.identity.node_id, applied.leader_epoch)
        self.node.append_cluster_event(
            ClusterFailoverPromotedEvent(
                leader_node_id=self.node.identity.node_id,
                previous_leader_node_id=previous_leader_node_id,
                leader_epoch=applied.leader_epoch,
            ),
        )
        return self.node.state_with_sync_statuses(applied)
