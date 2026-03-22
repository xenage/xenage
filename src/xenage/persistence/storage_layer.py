from __future__ import annotations

import json
from pathlib import Path
from typing import TypeVar

import msgspec
from loguru import logger

from structures.resources.base import Structure
from structures.resources.events import ClusterAuditEventAppendedEvent, ControlPlaneEventLog, UserEventAppendedEvent
from structures.resources.membership import BootstrapTokenSet, GroupState, StoredNodeIdentity, UserRecord, UserRoleBinding, UserState
from structures.resources.rbac import PolicyRule, RbacState, Role, RoleBinding, RoleRef, ServiceAccount, ServiceAccountSpec, Subject
from .key_value_storage import KeyValueStorage


class StorageError(RuntimeError):
    pass


StructureT = TypeVar("StructureT", bound=Structure)


class StorageLayer:
    def __init__(self, root: Path) -> None:
        self.kv = KeyValueStorage(root)
        self.root = self.kv.root
        self.db_path = self.kv.db_path

        logger.debug(
            "storage initialized root={} db_path={}",
            self.root,
            self.db_path,
        )

    def _load_raw(self, key: str) -> str | None:
        return self.kv.get(key)

    def _save_raw(self, key: str, value: str) -> None:
        self.kv.set(key, value)

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

    def load_control_plane_event_log(self) -> ControlPlaneEventLog:
        event_log = self._load_struct("control_plane_events", ControlPlaneEventLog)
        if event_log is None:
            logger.trace("control-plane event log is missing in sqlite path={}", self.db_path)
            return ControlPlaneEventLog()
        logger.debug("loaded control-plane event log items={} from sqlite", len(event_log.items))
        return event_log

    def load_user_state(self) -> UserState:
        # Legacy compatibility projection over RBAC + control-plane audit events.
        rbac_state = self.load_rbac_state()
        event_log = self.load_control_plane_event_log()
        users: list[UserRecord] = []
        for account in rbac_state.serviceAccounts:
            users.append(
                UserRecord(
                    user_id=account.metadata.name,
                    public_key=account.spec.publicKey,
                    roles=[UserRoleBinding(role="admin")],
                    created_at="",
                    enabled=account.spec.enabled,
                ),
            )

        entries = []
        has_cluster_audit = any(isinstance(item, ClusterAuditEventAppendedEvent) for item in event_log.items)
        for item in event_log.items:
            if isinstance(item, ClusterAuditEventAppendedEvent):
                entries.append(item.event)
            elif isinstance(item, UserEventAppendedEvent) and not has_cluster_audit:
                # Compatibility for old persisted events.
                entries.append(item.event)

        users = sorted(users, key=lambda item: item.user_id)
        version = max(rbac_state.version, len(entries))
        return UserState(version=version, users=users, event_log=entries)

    def save_user_state(self, user_state: UserState) -> None:
        # Legacy compatibility writer that projects UserState into RBAC state.
        service_accounts: list[ServiceAccount] = []
        role_bindings: list[RoleBinding] = []

        for user in user_state.users:
            name = user.user_id
            service_accounts.append(
                ServiceAccount(
                    metadata=msgspec.convert(
                        {"name": name},
                        type=type(ServiceAccount().metadata),
                    ),
                    spec=ServiceAccountSpec(engine="gui/v1", publicKey=user.public_key, enabled=user.enabled),
                ),
            )
            if any(binding.role == "admin" for binding in user.roles):
                role_bindings.append(
                    RoleBinding(
                        metadata=msgspec.convert(
                            {"name": f"admin-binding-{name}"},
                            type=type(RoleBinding().metadata),
                        ),
                        subjects=[Subject(subjectKind="ServiceAccount", name=name)],
                        roleRef=RoleRef(apiGroup="rbac.authorization.xenage.dev", kindName="Role", name="admin"),
                    ),
                )

        roles: list[Role] = [
            Role(
                metadata=msgspec.convert(
                    {"name": "admin"},
                    type=type(Role().metadata),
                ),
                rules=[PolicyRule(apiGroups=["*"], namespaces=["*"], resources=["*"], verbs=["*"])],
            ),
        ]

        current = self.load_rbac_state()
        same_payload = (
            current.serviceAccounts == sorted(service_accounts, key=lambda item: item.metadata.name)
            and current.roles == sorted(roles, key=lambda item: item.metadata.name)
            and current.roleBindings == sorted(role_bindings, key=lambda item: item.metadata.name)
        )
        target_version = current.version if same_payload else current.version + 1
        next_state = RbacState(
            version=target_version,
            serviceAccounts=sorted(service_accounts, key=lambda item: item.metadata.name),
            roles=sorted(roles, key=lambda item: item.metadata.name),
            roleBindings=sorted(role_bindings, key=lambda item: item.metadata.name),
        )
        self.save_rbac_state(next_state)

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

    def load_rbac_state(self) -> RbacState:
        state = self._load_struct("rbac_state", RbacState)
        if state is None:
            logger.trace("rbac state is missing in sqlite path={}", self.db_path)
            return RbacState()
        logger.debug(
            "loaded rbac state version={} service_accounts={} roles={} bindings={} from sqlite",
            state.version,
            len(state.serviceAccounts),
            len(state.roles),
            len(state.roleBindings),
        )
        return state

    def save_rbac_state(self, rbac_state: RbacState) -> None:
        logger.debug(
            "persisting rbac state version={} service_accounts={} roles={} bindings={} db={}",
            rbac_state.version,
            len(rbac_state.serviceAccounts),
            len(rbac_state.roles),
            len(rbac_state.roleBindings),
            self.db_path,
        )
        self._save_struct("rbac_state", rbac_state)
