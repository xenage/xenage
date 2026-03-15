from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass

from loguru import logger

from ..nodes.control_plane import ControlPlaneNode
from ..nodes.runtime import RuntimeNode
from ..network.http_transport import NodeHTTPServer

DEFAULT_GROUP_ID = "demo"
DEFAULT_STATE_TTL_SECONDS = 60


@dataclass(frozen=True)
class ServeOptions:
    host: str
    port: int


@dataclass(frozen=True)
class FailoverLoopOptions:
    ttl_seconds: int
    interval_seconds: int


class ControlPlaneServiceRunner:
    def __init__(self, node: ControlPlaneNode, serve: ServeOptions) -> None:
        self.node = node
        self.serve = serve

    @staticmethod
    async def run_failover_loop(node: ControlPlaneNode, options: FailoverLoopOptions) -> None:
        logger.debug(
            "starting failover loop node_id={} ttl_seconds={} interval_seconds={}",
            node.identity.node_id,
            options.ttl_seconds,
            options.interval_seconds,
        )
        while True:
            try:
                await node.check_failover(options.ttl_seconds)
            except Exception:
                logger.exception("auto failover loop iteration failed")
            await asyncio.sleep(options.interval_seconds)

    async def serve_forever(self, failover: FailoverLoopOptions | None = None) -> None:
        logger.info(
            "control-plane service startup node_id={} host={} port={} failover_enabled={}",
            self.node.identity.node_id,
            self.serve.host,
            self.serve.port,
            failover is not None,
        )
        await self.node.sync_logic.sync_on_startup()

        state = self.node.state_manager.get_state()
        if state is None:
            logger.warning(
                "startup has no known group state after sync; bootstrapping local leader node_id={} group_id={} ttl_seconds={}",
                self.node.identity.node_id,
                DEFAULT_GROUP_ID,
                DEFAULT_STATE_TTL_SECONDS,
            )
            try:
                self.node.initialize_group(DEFAULT_GROUP_ID, DEFAULT_STATE_TTL_SECONDS)
            except Exception:
                logger.exception("failed bootstrap fallback on startup node_id={}", self.node.identity.node_id)

        server = NodeHTTPServer(self.serve.host, self.serve.port, self.node)
        failover_task: asyncio.Task[None] | None = None

        if failover is not None:
            failover_task = asyncio.create_task(self.run_failover_loop(self.node, failover))

        try:
            await server.serve_forever_async()
        finally:
            logger.info("control-plane service shutting down node_id={}", self.node.identity.node_id)
            if failover_task is not None:
                failover_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await failover_task


class RuntimeServiceRunner:
    def __init__(self, node: RuntimeNode) -> None:
        self.node = node

    @staticmethod
    async def run_pull_loop(node: RuntimeNode) -> None:
        logger.info(
            "runtime pull loop started node_id={} pull_interval_seconds=2",
            node.identity.node_id,
        )
        while True:
            try:
                await node.pull_group_state()
            except Exception:
                logger.exception("runtime pull loop iteration failed")
            await asyncio.sleep(2)

    async def serve_forever(self) -> None:
        logger.info("runtime service startup node_id={}", self.node.identity.node_id)
        await self.run_pull_loop(self.node)
