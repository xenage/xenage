from __future__ import annotations

import pytest

from xenage.cluster.time_utils import utc_now
from xenage.crypto import Ed25519KeyPair, verify_signature
from xenage.network.http_transport import RequestVerifier, SignedTransportClient, TransportError
from structures.resources.membership import RequestAuth


def test_ed25519_sign_and_verify_roundtrip() -> None:
    key_pair = Ed25519KeyPair.generate()
    payload = b"xenage"
    signature = key_pair.sign(payload)
    assert verify_signature(key_pair.public_key_b64(), payload, signature)


def test_request_verifier_rejects_reused_nonce() -> None:
    key_pair = Ed25519KeyPair.generate()
    body = b'{"ok":true}'
    timestamp = int(utc_now().timestamp())
    auth = RequestAuth(
        node_id="node-a",
        timestamp=timestamp,
        nonce="same",
        signature=key_pair.sign(SignedTransportClient.signature_payload("POST", "/v1/state/publish", timestamp, "same", body)),
    )
    verifier = RequestVerifier()
    verifier.verify("POST", "/v1/state/publish", body, auth, key_pair.public_key_b64())
    with pytest.raises(TransportError):
        verifier.verify("POST", "/v1/state/publish", body, auth, key_pair.public_key_b64())
