from __future__ import annotations

import urllib.error
import urllib.request
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Final

from loguru import logger

from structures.resources.membership import GroupState, JoinResponse, RequestAuth, UserState

from ..crypto import Ed25519KeyPair, make_nonce, payload_digest, verify_signature
from ..serialization import decode_value, encode_value
from ..cluster.time_utils import utc_now

MAX_CLOCK_SKEW_SECONDS: Final[int] = 30


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

    def post_json(
        self,
        url: str,
        path: str,
        payload: object,
        response_type: type[GroupState] | type[JoinResponse] | type[UserState],
    ) -> GroupState | JoinResponse | UserState:
        body = encode_value(payload)
        auth = self.build_auth("POST", path, body)
        logger.debug("POST request url={} path={} node_id={} body_bytes={}", url, path, self.node_id, len(body))
        request = urllib.request.Request(
            f"{url}{path}",
            data=body,
            method="POST",
            headers={
                "content-type": "application/json",
                "x-node-id": auth.node_id,
                "x-timestamp": str(auth.timestamp),
                "x-nonce": auth.nonce,
                "x-signature": auth.signature,
                "x-public-key": self.public_key,
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                response_body = response.read()
                logger.trace("POST response status={} url={} path={} bytes={}", response.status, url, path, len(response_body))
        except urllib.error.URLError as exc:
            logger.error("transport error posting to {}{}: {}", url, path, exc)
            raise TransportError(str(exc)) from exc
        return decode_value(response_body, response_type)

    def get(self, url: str, path: str) -> bytes:
        body = b""
        auth = self.build_auth("GET", path, body)
        logger.debug("GET request url={} path={} node_id={}", url, path, self.node_id)
        request = urllib.request.Request(
            f"{url}{path}",
            method="GET",
            headers={
                "x-node-id": auth.node_id,
                "x-timestamp": str(auth.timestamp),
                "x-nonce": auth.nonce,
                "x-signature": auth.signature,
                "x-public-key": self.public_key,
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                payload = response.read()
                logger.trace("GET response status={} url={} path={} bytes={}", response.status, url, path, len(payload))
                return payload
        except urllib.error.URLError as exc:
            logger.error("transport error getting {}{}: {}", url, path, exc)
            raise TransportError(str(exc)) from exc

    @staticmethod
    def signature_payload(method: str, path: str, timestamp: int, nonce: str, body: bytes) -> bytes:
        return f"{method}\n{path}\n{timestamp}\n{nonce}\n{payload_digest(body)}".encode("utf-8")


class RequestVerifier:
    def __init__(self) -> None:
        self.seen_nonces: set[str] = set()

    def verify(self, method: str, path: str, body: bytes, auth: RequestAuth, public_key: str) -> None:
        now = int(utc_now().timestamp())
        if abs(now - auth.timestamp) > MAX_CLOCK_SKEW_SECONDS:
            raise TransportError("request timestamp is outside the allowed skew")
        nonce_key = f"{auth.node_id}:{auth.nonce}"
        if nonce_key in self.seen_nonces:
            raise TransportError("request nonce was already used")
        payload = SignedTransportClient.signature_payload(method, path, auth.timestamp, auth.nonce, body)
        if not verify_signature(public_key, payload, auth.signature):
            raise TransportError("request signature validation failed")
        self.seen_nonces.add(nonce_key)
        logger.trace("request verified method={} path={} node_id={} nonce={}", method, path, auth.node_id, auth.nonce)


class NodeHTTPServer:
    def __init__(self, host: str, port: int, node: "HTTPNodeProtocol") -> None:
        self.host = host
        self.port = port
        self.node = node
        self.verifier = RequestVerifier()
        self.server = ThreadingHTTPServer((host, port), self._build_handler())
        logger.debug("http server initialized host={} port={} node_type={}", host, port, type(node).__name__)

    def _build_handler(self) -> type[BaseHTTPRequestHandler]:
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                outer.handle("GET", self)

            def do_POST(self) -> None:
                outer.handle("POST", self)

            def log_message(self, format: str, *args: object) -> None:
                logger.trace("http server raw log: " + format, *args)

        return Handler

    def handle(self, method: str, handler: BaseHTTPRequestHandler) -> None:
        body = handler.rfile.read(int(handler.headers.get("content-length", "0")))
        auth = RequestAuth(
            node_id=handler.headers.get("x-node-id", ""),
            timestamp=int(handler.headers.get("x-timestamp", "0")),
            nonce=handler.headers.get("x-nonce", ""),
            signature=handler.headers.get("x-signature", ""),
        )
        public_key = handler.headers.get("x-public-key", "")
        logger.debug(
            "incoming request method={} path={} node_id={} body_bytes={} has_public_key={}",
            method,
            handler.path,
            auth.node_id,
            len(body),
            bool(public_key),
        )
        try:
            if public_key:
                self.verifier.verify(method, handler.path, body, auth, public_key)
            response = self.node.handle_request(method, handler.path, body, auth, public_key)
            payload = encode_value(response)
            handler.send_response(HTTPStatus.OK)
            handler.send_header("content-type", "application/json")
            handler.send_header("content-length", str(len(payload)))
            handler.end_headers()
            handler.wfile.write(payload)
            logger.trace("request handled method={} path={} status=200 response_bytes={}", method, handler.path, len(payload))
        except TransportError as exc:
            logger.error("transport rejection method={} path={} reason={}", method, handler.path, exc)
            payload = encode_value({"error": str(exc)})
            handler.send_response(HTTPStatus.UNAUTHORIZED)
            handler.send_header("content-type", "application/json")
            handler.send_header("content-length", str(len(payload)))
            handler.end_headers()
            handler.wfile.write(payload)
        except Exception as exc:
            logger.exception("handler failure method={} path={}", method, handler.path)
            payload = encode_value({"error": str(exc)})
            handler.send_response(HTTPStatus.INTERNAL_SERVER_ERROR)
            handler.send_header("content-type", "application/json")
            handler.send_header("content-length", str(len(payload)))
            handler.end_headers()
            handler.wfile.write(payload)

    def serve_forever(self) -> None:
        logger.info("starting http server on {}:{}", self.host, self.port)
        self.server.serve_forever()

    def shutdown(self) -> None:
        logger.debug("shutting down http server on {}:{}", self.host, self.port)
        self.server.shutdown()
        self.server.server_close()


class HTTPNodeProtocol:
    def handle_request(
        self,
        method: str,
        path: str,
        body: bytes,
        auth: RequestAuth,
        public_key: str,
    ) -> GroupState | JoinResponse | UserState | dict[str, str]:
        raise NotImplementedError
