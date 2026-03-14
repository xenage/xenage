from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from loguru import logger

from ..nodes.control_plane import ControlPlaneNode
from ..nodes.runtime import RuntimeNode
from ..network.http_transport import NodeHTTPServer


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
    def run_failover_loop(node: ControlPlaneNode, options: FailoverLoopOptions) -> None:
        logger.debug(
            "starting failover loop node_id={} ttl_seconds={} interval_seconds={}",
            node.identity.node_id,
            options.ttl_seconds,
            options.interval_seconds,
        )
        while True:
            try:
                node.check_failover(options.ttl_seconds)
            except Exception:
                logger.exception("auto failover loop iteration failed")
            time.sleep(options.interval_seconds)

    def serve_forever(self, failover: FailoverLoopOptions | None = None) -> None:
        if failover is not None:
            thread = threading.Thread(
                target=self.run_failover_loop,
                args=(self.node, failover),
                daemon=True,
            )
            thread.start()
        server = NodeHTTPServer(self.serve.host, self.serve.port, self.node)
        server.serve_forever()


class RuntimeServiceRunner:
    def __init__(self, node: RuntimeNode, serve: ServeOptions) -> None:
        self.node = node
        self.serve = serve

    def serve_forever(self) -> None:
        logger.info(
            "runtime pull loop started node_id={} pull_interval_seconds=2",
            self.node.identity.node_id,
        )
        while True:
            try:
                self.node.pull_group_state()
            except Exception:
                logger.exception("runtime pull loop iteration failed")
            time.sleep(2)
