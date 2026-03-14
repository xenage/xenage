from __future__ import annotations

from typing import Literal

from loguru import logger

from structures.resources.membership import EventLogEntry, UserRecord, UserRoleBinding, UserState

from .time_utils import format_timestamp, utc_now
from ..persistence.storage_layer import StorageLayer


class UserStateValidationError(RuntimeError):
    pass


class UserStateManager:
    def __init__(self, storage: StorageLayer) -> None:
        self.storage = storage
        self.current = storage.load_user_state()
        logger.debug(
            "user state manager initialized version={} users={} events={}",
            self.current.version,
            len(self.current.users),
            len(self.current.event_log),
        )

    def get_state(self) -> UserState:
        return self.current

    def refresh_from_storage(self) -> UserState:
        disk_state = self.storage.load_user_state()
        if disk_state.version > self.current.version:
            logger.debug(
                "refreshing user state from storage current_version={} disk_version={}",
                self.current.version,
                disk_state.version,
            )
            self.current = disk_state
        return self.current

    def replace_state(self, user_state: UserState) -> UserState:
        if user_state.version < self.current.version:
            raise UserStateValidationError("user state version regressed")
        self.current = user_state
        self.storage.save_user_state(user_state)
        return user_state

    def ensure_admin(self, user_id: str, public_key: str) -> UserRecord:
        existing = next((item for item in self.current.users if item.user_id == user_id), None)
        if existing is not None:
            if existing.public_key != public_key:
                raise UserStateValidationError("existing admin user has different public key")
            if not existing.enabled:
                raise UserStateValidationError("admin user is disabled")
            return existing

        user = UserRecord(
            user_id=user_id,
            public_key=public_key,
            roles=[UserRoleBinding(role="admin")],
            created_at=format_timestamp(utc_now()),
            enabled=True,
        )
        next_state = UserState(
            version=self.current.version + 1,
            users=[*self.current.users, user],
            event_log=self.current.event_log,
        )
        self.replace_state(next_state)
        logger.info("created admin user user_id={}", user_id)
        return user

    def append_event(
        self,
        actor_id: str,
        actor_type: Literal["node", "user", "system"],
        action: str,
        details: dict[str, str] | None = None,
    ) -> UserState:
        next_sequence = self.current.event_log[-1].sequence + 1 if self.current.event_log else 1
        event = EventLogEntry(
            sequence=next_sequence,
            happened_at=format_timestamp(utc_now()),
            actor_id=actor_id,
            actor_type=actor_type,
            action=action,
            details=details or {},
        )
        next_state = UserState(
            version=self.current.version + 1,
            users=self.current.users,
            event_log=[*self.current.event_log, event],
        )
        self.replace_state(next_state)
        logger.debug(
            "appended event sequence={} actor_id={} actor_type={} action={}",
            event.sequence,
            actor_id,
            actor_type,
            action,
        )
        return next_state

    def find_user(self, user_id: str) -> UserRecord | None:
        return next((item for item in self.current.users if item.user_id == user_id), None)
