from __future__ import annotations

from datetime import timedelta

from loguru import logger

from structures.resources.membership import BootstrapTokenRecord

from .crypto import make_token
from .cluster.time_utils import utc_now


class TokenValidationError(RuntimeError):
    pass


class BootstrapTokenManager:
    def __init__(self) -> None:
        self.tokens: dict[str, BootstrapTokenRecord] = {}

    def issue_token(self, ttl_seconds: int) -> BootstrapTokenRecord:
        now = int(utc_now().timestamp())
        record = BootstrapTokenRecord(
            token=make_token(),
            issued_at=now,
            expires_at=now + ttl_seconds,
        )
        self.tokens[record.token] = record
        logger.info("issued bootstrap token expiring_at={}", record.expires_at)
        return record

    def validate(self, token: str) -> None:
        record = self.tokens.get(token)
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
        record = self.tokens[token]
        self.tokens[token] = BootstrapTokenRecord(
            token=record.token,
            issued_at=record.issued_at,
            expires_at=record.expires_at,
            used=True,
        )
        logger.info("marked bootstrap token as used")
