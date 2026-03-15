from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import TypeVar

from loguru import logger

from structures.resources.base import Structure
from structures.resources.events import ControlPlaneEventLog
from structures.resources.membership import BootstrapTokenSet, GroupState, StoredNodeIdentity, UserState


class StorageError(RuntimeError):
    pass


StructureT = TypeVar("StructureT", bound=Structure)


class StorageLayer:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.db_path = self.root / "xenage.db"

        self._initialize_db()

        logger.debug(
            "storage initialized root={} db_path={}",
            self.root,
            self.db_path,
        )

    def _connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=NORMAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _initialize_db(self) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS kv_store (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """,
            )
            connection.commit()

    def _load_raw(self, key: str) -> str | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT value FROM kv_store WHERE key = ?",
                (key,),
            ).fetchone()
        if row is None:
            logger.debug("storage_load_raw key={} status=not_found", key)
            return None
        logger.debug("storage_load_raw key={} status=found value_len={}", key, len(str(row[0])))
        return str(row[0])

    def _save_raw(self, key: str, value: str) -> None:
        logger.debug("storage_save_raw key={} value_len={}", key, len(value))
        with self._connection() as connection:
            connection.execute(
                "INSERT INTO kv_store(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )
            connection.commit()

    def _repair_json_payload(self, key: str, payload: str) -> str | None:
        # Attempt to recover payloads with trailing garbage, then persist normalized JSON.
        text = payload.strip()
        if not text:
            return None
        try:
            parsed, end = json.JSONDecoder().raw_decode(text)
        except json.JSONDecodeError:
            return None
        trailing = text[end:].strip()
        if trailing:
            logger.warning(
                "detected trailing characters in stored JSON key={} db={} trailing_len={}",
                key,
                self.db_path,
                len(trailing),
            )
        return json.dumps(parsed, separators=(",", ":"), ensure_ascii=False)

    def _load_struct(self, key: str, struct_type: type[StructureT]) -> StructureT | None:
        payload = self._load_raw(key)
        if payload is None:
            return None
        try:
            return struct_type.load_json(payload)
        except Exception as exc:
            repaired = self._repair_json_payload(key, payload)
            if repaired is not None:
                try:
                    value = struct_type.load_json(repaired)
                except Exception as repaired_exc:
                    logger.error(
                        "failed to decode repaired JSON key={} type={} db={} reason={}",
                        key,
                        struct_type.__name__,
                        self.db_path,
                        repaired_exc,
                    )
                else:
                    self._save_raw(key, repaired)
                    logger.warning(
                        "repaired malformed JSON key={} type={} db={}",
                        key,
                        struct_type.__name__,
                        self.db_path,
                    )
                    return value
            logger.error(
                "failed to decode stored JSON key={} type={} db={} reason={}",
                key,
                struct_type.__name__,
                self.db_path,
                exc,
            )
            return None

    def _save_struct(self, key: str, value: Structure) -> None:
        self._save_raw(key, value.dump_json())

    def load_identity(self) -> StoredNodeIdentity | None:
        identity = self._load_struct("identity", StoredNodeIdentity)
        if identity is None:
            logger.trace("identity is missing in sqlite path={}", self.db_path)
            return None
        logger.debug("loaded node identity node_id={} role={} from sqlite", identity.node_id, identity.role)
        return identity

    def save_identity(self, identity: StoredNodeIdentity) -> None:
        logger.debug(
            "persisting node identity node_id={} role={} db={}",
            identity.node_id,
            identity.role,
            self.db_path,
        )
        self._save_struct("identity", identity)

    def load_group_state(self) -> GroupState | None:
        state = self._load_struct("group_state", GroupState)
        if state is None:
            logger.trace("group state is missing in sqlite path={}", self.db_path)
            return None
        logger.debug(
            "loaded group state version={} leader={} epoch={} from sqlite",
            state.version,
            state.leader_node_id,
            state.leader_epoch,
        )
        return state

    def save_group_state(self, group_state: GroupState) -> None:
        logger.debug(
            "persisting group state version={} leader={} db={}",
            group_state.version,
            group_state.leader_node_id,
            self.db_path,
        )
        self._save_struct("group_state", group_state)

    def load_user_state(self) -> UserState:
        state = self._load_struct("user_state", UserState)
        if state is None:
            logger.trace("user state is missing in sqlite path={}", self.db_path)
            return UserState()
        logger.debug(
            "loaded user state version={} users={} events={} from sqlite",
            state.version,
            len(state.users),
            len(state.event_log),
        )
        return state

    def save_user_state(self, user_state: UserState) -> None:
        logger.debug(
            "persisting user state version={} users={} events={} db={}",
            user_state.version,
            len(user_state.users),
            len(user_state.event_log),
            self.db_path,
        )
        self._save_struct("user_state", user_state)

    def load_control_plane_event_log(self) -> ControlPlaneEventLog:
        event_log = self._load_struct("control_plane_events", ControlPlaneEventLog)
        if event_log is None:
            logger.trace("control-plane event log is missing in sqlite path={}", self.db_path)
            return ControlPlaneEventLog()
        logger.debug("loaded control-plane event log items={} from sqlite", len(event_log.items))
        return event_log

    def save_control_plane_event_log(self, event_log: ControlPlaneEventLog) -> None:
        logger.debug(
            "persisting control-plane event log items={} db={}",
            len(event_log.items),
            self.db_path,
        )
        self._save_struct("control_plane_events", event_log)

    def load_bootstrap_token_set(self, key: str) -> BootstrapTokenSet:
        tokens = self._load_struct(key, BootstrapTokenSet)
        if tokens is None:
            logger.trace("bootstrap token set missing key={} db={}", key, self.db_path)
            return BootstrapTokenSet()
        return tokens

    def save_bootstrap_token_set(self, key: str, token_set: BootstrapTokenSet) -> None:
        logger.debug(
            "persisting bootstrap token set key={} count={} db={}",
            key,
            len(token_set.items),
            self.db_path,
        )
        self._save_struct(key, token_set)
