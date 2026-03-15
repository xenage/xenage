from __future__ import annotations

import asyncio
from http import HTTPStatus
import threading
from collections import deque
from typing import Final, TypeVar

import aiohttp
from aiohttp import web
from loguru import logger
import msgspec

from structures.resources.membership import RequestAuth

from ..cluster.time_utils import utc_now
from ..crypto import Ed25519KeyPair, make_nonce, payload_digest, verify_signature
from ..serialization import decode_value, encode_value

MAX_CLOCK_SKEW_SECONDS: Final[int] = 30
ResponseT = TypeVar("ResponseT")


class TransportError(RuntimeError):
    pass


class SignedTransportClient:
    def __init__(self, node_id: str, public_key: str, key_pair: Ed25519KeyPair, timeout_seconds: float = 3.0) -> None:
        self.node_id = node_id
        self.public_key = public_key
        self.key_pair = key_pair
        self.timeout_seconds = timeout_seconds
        logger.debug("transport client initialized node_id={} timeout_seconds={}", node_id, timeout_seconds)

    def build_auth(self, method: str, path: str, body: bytes) -> RequestAuth:
        timestamp = int(utc_now().timestamp())
        nonce = make_nonce()
        payload = self.signature_payload(method, path, timestamp, nonce, body)
        signature = self.key_pair.sign(payload)
        logger.trace("built auth method={} path={} node_id={} nonce={} body_bytes={}", method, path, self.node_id, nonce, len(body))
        return RequestAuth(node_id=self.node_id, timestamp=timestamp, nonce=nonce, signature=signature)

    async def post_json(
        self,
        url: str,
        path: str,
        payload: object,
        response_type: type[ResponseT],
    ) -> ResponseT:
        body = encode_value(payload)
        auth = self.build_auth("POST", path, body)
        logger.debug("POST request url={} path={} node_id={} body_bytes={}", url, path, self.node_id, len(body))
        headers = {
            "content-type": "application/json",
            "x-node-id": auth.node_id,
            "x-timestamp": str(auth.timestamp),
            "x-nonce": auth.nonce,
            "x-signature": auth.signature,
            "x-public-key": self.public_key,
        }
        response_body = await self._request("POST", f"{url.rstrip('/')}{path}", headers=headers, body=body)
        return decode_value(response_body, response_type)

    async def get(self, url: str, path: str) -> bytes:
        body = b""
        auth = self.build_auth("GET", path, body)
        logger.debug("GET request url={} path={} node_id={}", url, path, self.node_id)
        headers = {
            "x-node-id": auth.node_id,
            "x-timestamp": str(auth.timestamp),
            "x-nonce": auth.nonce,
            "x-signature": auth.signature,
            "x-public-key": self.public_key,
        }
        return await self._request("GET", f"{url.rstrip('/')}{path}", headers=headers, body=None)

    async def _request(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        body: bytes | None,
    ) -> bytes:
        timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self.timeout_seconds
        last_connect_error: Exception | None = None
        while True:
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.request(method, url, data=body, headers=headers) as response:
                        payload = await response.read()
                        if response.status == HTTPStatus.OK:
                            logger.trace(
                                "http response status={} method={} url={} bytes={}",
                                response.status,
                                method,
                                url,
                                len(payload),
                            )
                            return payload
                        error_message = self._extract_error(payload, response.reason)
                        logger.error(
                            "transport request failed method={} url={} status={} reason={}",
                            method,
                            url,
                            response.status,
                            error_message,
                        )
                        raise TransportError(error_message)
            except (aiohttp.ClientConnectorError, ConnectionRefusedError) as exc:
                last_connect_error = exc
                if loop.time() >= deadline:
                    break
                await asyncio.sleep(0.05)
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                logger.error("transport error {} {}: {}", method, url, exc)
                raise TransportError(str(exc)) from exc
        logger.error("transport error {} {}: {}", method, url, last_connect_error)
        raise TransportError(str(last_connect_error) if last_connect_error else "request timed out")

    @staticmethod
    def _extract_error(payload: bytes, fallback: str) -> str:
        if not payload:
            return fallback
        try:
            # Using msgspec.json.decode directly to handle generic JSON
            decoded = msgspec.json.decode(payload)
            if isinstance(decoded, dict):
                error = decoded.get("error", "")
                if isinstance(error, str) and error:
                    return error
                if error:
                    return str(error)
        except Exception:
            pass
        try:
            return payload.decode("utf-8")
        except Exception:
            return fallback

    @staticmethod
    def signature_payload(method: str, path: str, timestamp: int, nonce: str, body: bytes) -> bytes:
        return f"{method}\n{path}\n{timestamp}\n{nonce}\n{payload_digest(body)}".encode("utf-8")


class RequestVerifier:
    def __init__(self) -> None:
        self._seen_nonce_at: dict[str, int] = {}
        self._nonce_order: deque[tuple[str, int]] = deque()

    def _prune(self, now: int) -> None:
        # Keep nonce history only for a small replay window to avoid unbounded memory growth.
        ttl_seconds = MAX_CLOCK_SKEW_SECONDS * 2
        cutoff = now - ttl_seconds
        while self._nonce_order:
            nonce_key, timestamp = self._nonce_order[0]
            if timestamp > cutoff:
                break
            self._nonce_order.popleft()
            if self._seen_nonce_at.get(nonce_key) == timestamp:
                self._seen_nonce_at.pop(nonce_key, None)

    def verify(self, method: str, path: str, body: bytes, auth: RequestAuth, public_key: str) -> None:
        now = int(utc_now().timestamp())
        self._prune(now)
        if abs(now - auth.timestamp) > MAX_CLOCK_SKEW_SECONDS:
            raise TransportError("request timestamp is outside the allowed skew")
        nonce_key = f"{auth.node_id}:{auth.nonce}"
        if nonce_key in self._seen_nonce_at:
            raise TransportError("request nonce was already used")
        payload = SignedTransportClient.signature_payload(method, path, auth.timestamp, auth.nonce, body)
        if not verify_signature(public_key, payload, auth.signature):
            logger.warning("request_signature_check_failed method={} path={} node_id={} public_key={}", method, path, auth.node_id, public_key)
            raise TransportError("request signature validation failed")
        self._seen_nonce_at[nonce_key] = auth.timestamp
        self._nonce_order.append((nonce_key, auth.timestamp))
        logger.info("request_signature_check_success method={} path={} node_id={} public_key={}", method, path, auth.node_id, public_key)
        logger.trace("request verified method={} path={} node_id={} nonce={}", method, path, auth.node_id, auth.nonce)


class NodeHTTPServer:
    def __init__(self, host: str, port: int, node: "HTTPNodeProtocol") -> None:
        self.host = host
        self.port = port
        self.node = node
        self.verifier = RequestVerifier()
        self._shutdown_event: asyncio.Event | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._started_event = threading.Event()
        self._shutdown_requested = threading.Event()
        logger.debug("http server initialized host={} port={} node_type={}", host, port, type(node).__name__)

    async def _handle(self, request: web.Request) -> web.Response:
        method = request.method
        raw_path = request.raw_path
        body = await request.read()
        auth = RequestAuth(
            node_id=request.headers.get("x-node-id", ""),
            timestamp=int(request.headers.get("x-timestamp", "0")),
            nonce=request.headers.get("x-nonce", ""),
            signature=request.headers.get("x-signature", ""),
        )
        public_key = request.headers.get("x-public-key", "")
        
        # Log request at INFO level for visibility, DEBUG for details
        logger.info("request_received method={} path={} node_id={} public_key={} body_len={}", 
                    method, raw_path, auth.node_id, public_key, len(body))
        
        if len(body) < 4096:
             logger.trace("request_body method={} path={} body={!r}", method, raw_path, body)

        try:
            if public_key:
                self.verifier.verify(method, raw_path, body, auth, public_key)
            
            response = await self.node.handle_request(method, raw_path, body, auth, public_key)
            
            # For non-GET requests that were successful, log that a mutating action occurred
            if method != "GET":
                logger.info("mutation_request_success method={} path={} node_id={}", method, raw_path, auth.node_id)

            payload = encode_value(response)
            
            logger.info("request_success method={} path={} node_id={} status=200", method, raw_path, auth.node_id)
            if len(payload) < 4096:
                logger.debug("response_body method={} path={} body={!r}", method, raw_path, payload)
            else:
                logger.debug("response_body method={} path={} body_len={}", method, raw_path, len(payload))

            return web.Response(status=HTTPStatus.OK, body=payload, content_type="application/json")
        except TransportError as exc:
            logger.warning("request_rejected method={} path={} node_id={} reason={}", method, raw_path, auth.node_id, exc)
            payload = encode_value({"error": str(exc)})
            return web.Response(status=HTTPStatus.UNAUTHORIZED, body=payload, content_type="application/json")
        except Exception as exc:
            logger.exception("request_failed method={} path={} node_id={} reason={}", method, raw_path, auth.node_id, exc)
            payload = encode_value({"error": str(exc)})
            return web.Response(status=HTTPStatus.INTERNAL_SERVER_ERROR, body=payload, content_type="application/json")

    async def serve_forever_async(self) -> None:
        app = web.Application()
        app.router.add_route("*", "/{tail:.*}", self._handle)
        runner = web.AppRunner(app, access_log=None)
        await runner.setup()
        site = web.TCPSite(runner, self.host, self.port)
        await site.start()

        self._loop = asyncio.get_running_loop()
        self._shutdown_event = asyncio.Event()
        logger.info("starting http server on {}:{}", self.host, self.port)
        self._started_event.set()
        if self._shutdown_requested.is_set():
            self._shutdown_event.set()

        try:
            await self._shutdown_event.wait()
        finally:
            await runner.cleanup()
            self._shutdown_event = None
            self._loop = None
            self._started_event.clear()

    def serve_forever(self) -> None:
        asyncio.run(self.serve_forever_async())

    def wait_until_ready(self, timeout_seconds: float = 1.0) -> bool:
        return self._started_event.wait(timeout_seconds)

    def shutdown(self) -> None:
        logger.debug("shutting down http server on {}:{}", self.host, self.port)
        self._shutdown_requested.set()
        if self._loop is None or self._shutdown_event is None:
            return
        if self._loop.is_closed():
            return
        self._loop.call_soon_threadsafe(self._shutdown_event.set)


class HTTPNodeProtocol:
    async def handle_request(
        self,
        method: str,
        path: str,
        body: bytes,
        auth: RequestAuth,
        public_key: str,
    ) -> object:
        raise NotImplementedError
