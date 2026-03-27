from __future__ import annotations

import base64
import hashlib
import secrets
from typing import Final

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

RAW_ENCODING: Final[serialization.Encoding] = serialization.Encoding.Raw
RAW_FORMAT_PRIVATE: Final[serialization.PrivateFormat] = serialization.PrivateFormat.Raw
RAW_FORMAT_PUBLIC: Final[serialization.PublicFormat] = serialization.PublicFormat.Raw


class Ed25519KeyPair:
    def __init__(self, private_key: Ed25519PrivateKey) -> None:
        self.private_key = private_key
        self.public_key = private_key.public_key()

    @classmethod
    def generate(cls) -> "Ed25519KeyPair":
        return cls(Ed25519PrivateKey.generate())

    @classmethod
    def from_private_key_b64(cls, value: str) -> "Ed25519KeyPair":
        private_bytes = base64.b64decode(value.encode("utf-8"))
        return cls(Ed25519PrivateKey.from_private_bytes(private_bytes))

    def private_key_b64(self) -> str:
        private_bytes = self.private_key.private_bytes(
            encoding=RAW_ENCODING,
            format=RAW_FORMAT_PRIVATE,
            encryption_algorithm=serialization.NoEncryption(),
        )
        return base64.b64encode(private_bytes).decode("utf-8")

    def public_key_b64(self) -> str:
        public_bytes = self.public_key.public_bytes(encoding=RAW_ENCODING, format=RAW_FORMAT_PUBLIC)
        return base64.b64encode(public_bytes).decode("utf-8")

    def sign(self, payload: bytes) -> str:
        return base64.b64encode(self.private_key.sign(payload)).decode("utf-8")


def verify_signature(public_key_b64: str, payload: bytes, signature_b64: str) -> bool:
    public_bytes = base64.b64decode(public_key_b64.encode("utf-8"))
    signature = base64.b64decode(signature_b64.encode("utf-8"))
    public_key = Ed25519PublicKey.from_public_bytes(public_bytes)
    try:
        public_key.verify(signature, payload)
    except InvalidSignature:
        return False
    return True


def normalize_public_key_b64(value: str | Ed25519PublicKey | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    public_bytes = value.public_bytes(encoding=RAW_ENCODING, format=RAW_FORMAT_PUBLIC)
    return base64.b64encode(public_bytes).decode("utf-8")


def make_nonce() -> str:
    return secrets.token_hex(16)


def make_token() -> str:
    return secrets.token_urlsafe(18)


def payload_digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()
