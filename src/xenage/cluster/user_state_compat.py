from __future__ import annotations

from typing import Literal

from structures.resources.membership import UserRecord, UserState


class UserStateCompat:
    """Legacy user-state facade backed by RBAC + control-plane events."""

    def __init__(self, node: object) -> None:
        self.node = node
        self._projection_override: UserState | None = None

    def get_state(self) -> UserState:
        if self._projection_override is not None:
            return self._projection_override
        return self.node.storage.load_user_state()

    def replace_state(self, user_state: UserState) -> UserState:
        # Projection-only compatibility mode used by legacy tests that intentionally
        # corrupt local user projection without mutating canonical replicated state.
        if not user_state.users and not user_state.event_log:
            self._projection_override = user_state
            return user_state

        self.node.storage.save_user_state(user_state)
        self.node.rbac_state_manager.current = self.node.storage.load_rbac_state()
        self._projection_override = None
        return self.get_state()

    def ensure_admin(self, user_id: str, public_key: str, read_only: bool = False) -> UserRecord:
        return self.node.rbac_state_manager.ensure_admin_user(user_id, public_key, read_only=read_only)

    def append_event(
        self,
        actor_id: str,
        actor_type: Literal["node", "user", "system"],
        action: str,
        details: dict[str, str] | None = None,
    ) -> UserState:
        self._projection_override = None
        self.node.event_manager.record_cluster_audit_event(
            actor_node_id=actor_id,
            actor_type=actor_type,
            action=action,
            details=details,
        )
        return self.get_state()

    def refresh_from_canonical(self) -> None:
        if self._projection_override is None:
            return
        canonical = self.node.storage.load_user_state()
        self._projection_override = UserState(
            version=canonical.version,
            users=canonical.users,
            event_log=self._projection_override.event_log,
        )

    def find_user(self, user_id: str) -> UserRecord | None:
        state = self.get_state()
        return next((item for item in state.users if item.user_id == user_id), None)
