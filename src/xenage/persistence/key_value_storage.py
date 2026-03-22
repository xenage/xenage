from __future__ import annotations

import sqlite3
from pathlib import Path

from loguru import logger


class KeyValueStorage:
    def __init__(self, root: Path, db_name: str = "xenage.db") -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.db_path = self.root / db_name
        self._initialize_db()

        logger.debug(
            "key-value storage initialized root={} db_path={}",
            self.root,
            self.db_path,
        )

    def get(self, key: str) -> str | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT value FROM kv_store WHERE key = ?",
                (key,),
            ).fetchone()
        if row is None:
            logger.debug("kv_get key={} status=not_found", key)
            return None
        value = str(row[0])
        logger.debug("kv_get key={} status=found value_len={}", key, len(value))
        return value

    def set(self, key: str, value: str) -> None:
        logger.debug("kv_set key={} value_len={}", key, len(value))
        with self._connection() as connection:
            connection.execute(
                "INSERT INTO kv_store(key, value) VALUES(?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )
            connection.commit()

    def delete(self, key: str) -> None:
        logger.debug("kv_delete key={}", key)
        with self._connection() as connection:
            connection.execute("DELETE FROM kv_store WHERE key = ?", (key,))
            connection.commit()

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
