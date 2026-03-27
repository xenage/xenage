from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from loguru import logger

from structures.resources.membership import BootstrapTokenRecord, BootstrapTokenSet

from .crypto import make_token
from .cluster.time_utils import utc_now

if TYPE_CHECKING:
    from .persistence.storage_layer import StorageLayer


class TokenValidationError(RuntimeError):
    pass


class BootstrapTokenManager:
    def __init__(self, storage: "StorageLayer | None" = None, storage_key: str = "") -> None:
        self.storage = storage
        self.storage_key = storage_key
        self.tokens: dict[str, BootstrapTokenRecord] = {}

    def _load_tokens(self) -> dict[str, BootstrapTokenRecord]:
        if self.storage is None or not self.storage_key:
            return dict(self.tokens)
        token_set = self.storage.load_bootstrap_token_set(self.storage_key)
        return {item.token: item for item in token_set.items}

    def _save_tokens(self, tokens: dict[str, BootstrapTokenRecord]) -> None:
        if self.storage is None or not self.storage_key:
            self.tokens = dict(tokens)
            return
        ordered = sorted(tokens.values(), key=lambda item: (item.expires_at, item.token))
        self.storage.save_bootstrap_token_set(self.storage_key, BootstrapTokenSet(items=ordered))

    def issue_token(self, ttl_seconds: int) -> BootstrapTokenRecord:
        tokens = self._load_tokens()
        now = int(utc_now().timestamp())
        record = BootstrapTokenRecord(
            token=make_token(),
            issued_at=now,
            expires_at=now + ttl_seconds,
        )
        tokens[record.token] = record
        self._save_tokens(tokens)
        logger.info("issued bootstrap token expiring_at={}", record.expires_at)
        return record

    def validate(self, token: str) -> None:
        record = self._load_tokens().get(token)
        now = int(utc_now().timestamp())
        if record is None:
            logger.warning("rejected unknown bootstrap token")
            raise TokenValidationError("bootstrap token was not found")
        if record.used:
            logger.warning("rejected used bootstrap token")
            raise TokenValidationError("bootstrap token already used")
        if record.expires_at <= now:
            logger.warning("rejected expired bootstrap token")
            raise TokenValidationError("bootstrap token expired")

    def mark_used(self, token: str) -> None:
        tokens = self._load_tokens()
        record = tokens[token]
        tokens[token] = BootstrapTokenRecord(
            token=record.token,
            issued_at=record.issued_at,
            expires_at=record.expires_at,
            used=True,
        )
        self._save_tokens(tokens)
        logger.info("marked bootstrap token as used")
