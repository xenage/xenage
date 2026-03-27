from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Literal

from loguru import logger

from structures.resources.events import ControlPlaneEventPage
from structures.resources.membership import GroupState, ControlPlaneSyncStatusRequest, JoinResponse
from ...serialization import decode_value
from ...network.http_transport import TransportError
from ...crypto import normalize_public_key_b64

if TYPE_CHECKING:
    from .main import ControlPlaneNode


class EventHistoryAheadError(RuntimeError):
    pass


class ControlPlaneSyncLogic:
    def __init__(self, node: ControlPlaneNode) -> None:
        self.node = node

    @staticmethod
    def _control_plane_urls(state: GroupState, exclude_node_ids: set[str] | None = None) -> list[str]:
        excluded = exclude_node_ids or set()
        control_plane_ids = {item.node_id for item in state.control_planes}
        urls: list[str] = []
        seen_urls: set[str] = set()
        for endpoint in state.endpoints:
            if endpoint.node_id in excluded:
                continue
            if endpoint.node_id not in control_plane_ids:
                continue
            if endpoint.url in seen_urls:
                continue
            seen_urls.add(endpoint.url)
            urls.append(endpoint.url)
        return urls

    @staticmethod
    def _node_urls(state: GroupState, node_id: str) -> list[str]:
        urls: list[str] = []
        seen_urls: set[str] = set()
        for endpoint in state.endpoints:
            if endpoint.node_id != node_id:
                continue
            if endpoint.url in seen_urls:
                continue
            seen_urls.add(endpoint.url)
            urls.append(endpoint.url)
        return urls

    @staticmethod
    def _peer_leader_metadata_is_newer(local_state: GroupState | None, page: ControlPlaneEventPage) -> bool:
        if local_state is None:
            return False
        if page.leader_epoch > local_state.leader_epoch:
            return True
        if page.leader_epoch == local_state.leader_epoch and page.leader_node_id != local_state.leader_node_id:
            return True
        return False

    async def _sync_group_state_from_url(self, peer_url: str, trusted_leader_pubkey: str | None = None) -> GroupState:
        payload = await self.node.client.get(peer_url, "/v1/state/current")
        remote_state = decode_value(payload, GroupState)
        trust_anchor = normalize_public_key_b64(trusted_leader_pubkey) or remote_state.leader_pubkey
        return self.node.state_manager.replace_state(remote_state, trusted_leader_pubkey=trust_anchor)

    async def sync_events_from_urls(
        self,
        urls: list[str],
        report_sync_status: bool = False,
        trusted_leader_pubkey: str | None = None,
        raise_on_divergence: bool = False,
    ) -> GroupState | None:
        trusted_leader_pubkey = normalize_public_key_b64(trusted_leader_pubkey)
        if not urls:
            return None

        last_divergence_reason: str | None = None
        initial_state = self.node.state_manager.get_state()
        initial_state_fingerprint = None
        if initial_state is not None:
            initial_state_fingerprint = (
                initial_state.version,
                initial_state.leader_epoch,
                initial_state.leader_node_id,
                initial_state.leader_pubkey,
            )
        for leader_url in urls:
            logger.info("sync_attempt leader_url={} node_id={}", leader_url, self.node.identity.node_id)
            if report_sync_status:
                self.node.set_local_sync_status("syncing")
                await self.publish_sync_status(leader_url, "syncing")

            after_event_id = self.node.event_manager.get_last_event_id()
            logger.debug("sync_start_fetching leader_url={} after_event_id={}", leader_url, after_event_id)
            divergence_reason: str | None = None
            last_page: ControlPlaneEventPage | None = None
            try:
                while True:
                    payload = await self.node.client.get(
                        leader_url,
                        f"/v1/control-plane/events?after_event_id={after_event_id}&limit=250",
                    )
                    page = decode_value(payload, ControlPlaneEventPage)
                    last_page = page
                    logger.debug("sync_page_received leader_url={} event_count={} has_more={} last_event_id={}", 
                                 leader_url, len(page.items), page.has_more, page.last_event_id)
                    if (
                        trusted_leader_pubkey
                        and page.leader_pubkey
                        and page.leader_pubkey != trusted_leader_pubkey
                    ):
                        logger.warning(
                            "sync_page_leader_pubkey_changed node_id={} leader_url={} trusted_pubkey={} page_pubkey={} "
                            "continuing with trusted anchor verification",
                            self.node.identity.node_id,
                            leader_url,
                            trusted_leader_pubkey,
                            page.leader_pubkey,
                        )
                    
                    current_last = self.node.event_manager.get_last_event_id()
                    current_nonce = self.node.event_manager.get_last_event_nonce()
                    if current_last > page.last_event_id and page.last_event_id != 0:
                        reason = f"local event history {current_last} is ahead of leader {page.last_event_id}"
                        logger.error("sync_divergence_detected leader_url={} reason={}", leader_url, reason)
                        # This leader is stale for us. Move on to the next candidate URL.
                        divergence_reason = reason
                        break
                    if (
                        current_last == page.last_event_id
                        and current_last != 0
                        and current_nonce
                        and page.last_event_nonce
                        and current_nonce != page.last_event_nonce
                    ):
                        reason = (
                            f"local event nonce {current_nonce} differs from leader nonce {page.last_event_nonce} "
                            f"at event id {current_last}"
                        )
                        logger.error("sync_divergence_detected leader_url={} reason={}", leader_url, reason)
                        divergence_reason = reason
                        break
                    
                    previous_after_event_id = after_event_id
                    trusted_page_leader_pubkey = trusted_leader_pubkey or page.leader_pubkey
                    self.node.event_manager.apply_remote_events(
                        page.items,
                        trusted_leader_pubkey=trusted_page_leader_pubkey,
                    )
                    after_event_id = self.node.event_manager.get_last_event_id()
                    if page.has_more and after_event_id <= previous_after_event_id:
                        raise TransportError(
                            f"sync stalled at event_id={after_event_id} while reading from {leader_url}"
                        )
                    if not page.has_more and page.state_hash:
                        local_state_hash = self.node.event_manager.current_state_hash()
                        if local_state_hash != page.state_hash:
                            raise TransportError(
                                f"state hash mismatch after sync local={local_state_hash} leader={page.state_hash}"
                            )
                    if not page.has_more:
                        break

                # A restarted node can have the same last_event_id as peer but stale leader state.
                # In that case, reconcile from signed state snapshot exposed by the peer.
                # Only do this when there is no explicit divergence (local ahead of peer).
                current_state = self.node.state_manager.get_state()
                if (
                    divergence_reason is None
                    and last_page is not None
                    and self._peer_leader_metadata_is_newer(current_state, last_page)
                ):
                    logger.warning(
                        "peer reports newer leader metadata without additional events; syncing state snapshot "
                        "node_id={} peer_url={} local_leader={} local_epoch={} peer_leader={} peer_epoch={}",
                        self.node.identity.node_id,
                        leader_url,
                        current_state.leader_node_id if current_state else "",
                        current_state.leader_epoch if current_state else 0,
                        last_page.leader_node_id,
                        last_page.leader_epoch,
                    )
                    await self._sync_group_state_from_url(leader_url, trusted_leader_pubkey=last_page.leader_pubkey)
            except Exception as exc:
                logger.error(
                    "sync_failed node_id={} leader_url={} reason={}",
                    self.node.identity.node_id,
                    leader_url,
                    exc,
                )
                continue

            if divergence_reason is not None:
                last_divergence_reason = divergence_reason
                continue

            logger.info("sync_completed leader_url={} last_event_id={}", leader_url, after_event_id)

            if report_sync_status:
                self.node.set_local_sync_status("synced")
                await self.publish_sync_status(leader_url, "synced")
            if hasattr(self.node, "user_state_manager") and hasattr(self.node.user_state_manager, "refresh_from_canonical"):
                self.node.user_state_manager.refresh_from_canonical()
            current_state = self.node.state_manager.get_state()
            if current_state is None:
                return None
            current_state_fingerprint = (
                current_state.version,
                current_state.leader_epoch,
                current_state.leader_node_id,
                current_state.leader_pubkey,
            )
            if current_state_fingerprint == initial_state_fingerprint:
                return None
            return current_state

        if last_divergence_reason is not None and (report_sync_status or raise_on_divergence):
            raise EventHistoryAheadError(last_divergence_reason)
        return None

    async def publish_sync_status(self, leader_url: str, status: Literal["syncing", "synced", "broken"], reason: str = "") -> bool:
        try:
            await self.node.client.post_json(
                leader_url,
                "/v1/control-plane/sync-status",
                ControlPlaneSyncStatusRequest(status=status, reason=reason),
                dict[str, str],
            )
            return True
        except Exception as exc:
            logger.debug(
                "failed to publish sync status node_id={} leader_url={} status={} reason={}",
                self.node.identity.node_id,
                leader_url,
                status,
                exc,
            )
            return False

    async def sync_on_startup(self) -> GroupState | None:
        state = self.node.state_manager.get_state()
        if state is None:
            return None

        peers = self._control_plane_urls(state, exclude_node_ids={self.node.identity.node_id})
        if not peers:
            return state

        logger.info("syncing from all peers on startup node_id={} peers={}", self.node.identity.node_id, peers)
        # Try each peer until one succeeds or all fail
        for url in peers:
            synced = await self.sync_events_from_urls([url], report_sync_status=False)
            if synced:
                return synced
        
        return self.node.state_manager.get_state()

    async def sync_from_peers(self, raise_on_divergence: bool = False) -> GroupState | None:
        state = self.node.state_manager.get_state()
        if state is None:
            return None

        peers = self._control_plane_urls(
            state,
            exclude_node_ids={self.node.identity.node_id, state.leader_node_id},
        )
        if not peers:
            return state
            
        logger.info("syncing from peers before failover node_id={} peers={}", self.node.identity.node_id, peers)
        return await self.sync_events_from_urls(
            peers,
            report_sync_status=False,
            raise_on_divergence=raise_on_divergence,
        )

    async def sync_control_plane_events(self, preferred_leader_url: str | None = None) -> GroupState | None:
        if self.node.broken_sync_reason:
            logger.warning(
                "sync skipped because node is broken node_id={} reason={}",
                self.node.identity.node_id,
                self.node.broken_sync_reason,
            )
            return self.node.state_manager.get_state()

        current = self.node.state_manager.get_state()
        leader_urls: list[str] = []
        try:
            if preferred_leader_url:
                leader_urls = [preferred_leader_url]
                leader_pubkey: str | None = None
                if current is not None:
                    leader_pubkey = current.leader_pubkey
                synced = await self.sync_events_from_urls(
                    leader_urls,
                    report_sync_status=True,
                    trusted_leader_pubkey=leader_pubkey,
                )
                return synced or self.node.state_manager.get_state()
            if current is None:
                return None
            if current.leader_node_id == self.node.identity.node_id:
                return current

            leader_urls = self._node_urls(current, current.leader_node_id)
            synced = await self.sync_events_from_urls(
                leader_urls,
                report_sync_status=True,
                trusted_leader_pubkey=current.leader_pubkey,
            )
            return synced or self.node.state_manager.get_state()
        except EventHistoryAheadError as exc:
            await self.node.mark_broken(str(exc), leader_urls)
            return self.node.state_manager.get_state()

    async def join_peer(self, leader_url: str, leader_pubkey: str, bootstrap_token: str) -> GroupState:
        leader_pubkey = normalize_public_key_b64(leader_pubkey) or ""
        # If we are already part of the known membership, sync first; otherwise join first.
        current = self.node.state_manager.get_state()
        known_node_ids: set[str] = set()
        if current is not None:
            known_node_ids.update(item.node_id for item in current.control_planes)
            known_node_ids.update(item.node_id for item in current.runtimes)
        if self.node.identity.node_id in known_node_ids:
            await self.sync_events_from_urls([leader_url], report_sync_status=False, trusted_leader_pubkey=leader_pubkey)
        
        # Then join
        join_request = self.node.state_manager.build_join_request(bootstrap_token, self.node.identity.node_id, self.node.endpoints)
        response = await self.node.client.post_json(
            leader_url,
            "/v1/join",
            join_request,
            JoinResponse,
        )
        if not response.accepted:
            raise TransportError(f"join rejected: {response.reason}")
        
        if response.group_state is None:
            raise TransportError("join accepted but no group state provided")
        if response.group_state.leader_pubkey != leader_pubkey:
            raise TransportError("leader pubkey mismatch in group state")
            
        self.node.state_manager.replace_state(response.group_state, trusted_leader_pubkey=leader_pubkey)
        await self.sync_events_from_urls([leader_url], report_sync_status=False, trusted_leader_pubkey=leader_pubkey)
        return response.group_state
