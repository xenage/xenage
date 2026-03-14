from __future__ import annotations

from pathlib import Path

from loguru import logger

from structures.resources.membership import GroupState, StoredNodeIdentity, UserState


class StorageError(RuntimeError):
    pass


class StorageLayer:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.identity_path = self.root / "identity.json"
        self.group_state_path = self.root / "group_state.json"
        self.user_state_path = self.root / "user_state.json"
        logger.debug(
            "storage initialized root={} identity_path={} group_state_path={} user_state_path={}",
            self.root,
            self.identity_path,
            self.group_state_path,
            self.user_state_path,
        )

    def load_identity(self) -> StoredNodeIdentity | None:
        if not self.identity_path.exists():
            logger.trace("identity file is missing path={}", self.identity_path)
            return None
        logger.debug("loading node identity path={}", self.identity_path)
        identity = StoredNodeIdentity.load_json(self.identity_path)
        logger.trace("loaded node identity node_id={} role={}", identity.node_id, identity.role)
        return identity

    def save_identity(self, identity: StoredNodeIdentity) -> None:
        logger.debug(
            "persisting node identity node_id={} role={} path={}",
            identity.node_id,
            identity.role,
            self.identity_path,
        )
        payload = identity.dump_json()
        self.identity_path.write_text(payload, encoding="utf-8")
        logger.trace("node identity persisted bytes={}", len(payload.encode("utf-8")))

    def load_group_state(self) -> GroupState | None:
        if not self.group_state_path.exists():
            logger.trace("group state file is missing path={}", self.group_state_path)
            return None
        logger.debug("loading group state path={}", self.group_state_path)
        state = GroupState.load_json(self.group_state_path)
        logger.trace(
            "loaded group state version={} leader={} epoch={}",
            state.version,
            state.leader_node_id,
            state.leader_epoch,
        )
        return state

    def save_group_state(self, group_state: GroupState) -> None:
        logger.debug(
            "persisting group state version={} leader={} path={}",
            group_state.version,
            group_state.leader_node_id,
            self.group_state_path,
        )
        payload = group_state.dump_json()
        self.group_state_path.write_text(payload, encoding="utf-8")
        logger.trace("group state persisted bytes={}", len(payload.encode("utf-8")))

    def load_user_state(self) -> UserState:
        if not self.user_state_path.exists():
            logger.trace("user state file is missing path={}", self.user_state_path)
            return UserState()
        logger.debug("loading user state path={}", self.user_state_path)
        state = UserState.load_json(self.user_state_path)
        logger.trace(
            "loaded user state version={} users={} events={}",
            state.version,
            len(state.users),
            len(state.event_log),
        )
        return state

    def save_user_state(self, user_state: UserState) -> None:
        logger.debug(
            "persisting user state version={} users={} events={} path={}",
            user_state.version,
            len(user_state.users),
            len(user_state.event_log),
            self.user_state_path,
        )
        payload = user_state.dump_json()
        self.user_state_path.write_text(payload, encoding="utf-8")
        logger.trace("user state persisted bytes={}", len(payload.encode("utf-8")))
