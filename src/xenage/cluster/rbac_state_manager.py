from __future__ import annotations

from dataclasses import dataclass

import msgspec
from loguru import logger

from structures.resources.membership import UserRecord, UserRoleBinding
from structures.resources.rbac import PolicyRule, RbacState, Role, RoleBinding, RoleRef, ServiceAccount, ServiceAccountSpec, Subject

from xenage.network.http_transport import TransportError
from xenage.persistence.storage_layer import StorageLayer


@dataclass(frozen=True)
class SubjectIdentity:
    name: str


class RbacStateManager:
    def __init__(self, storage: StorageLayer) -> None:
        self.storage = storage
        self.current = storage.load_rbac_state()
        logger.debug(
            "rbac state manager initialized version={} service_accounts={} roles={} bindings={}",
            self.current.version,
            len(self.current.serviceAccounts),
            len(self.current.roles),
            len(self.current.roleBindings),
        )

    def get_state(self) -> RbacState:
        return self.current

    def replace_state(self, state: RbacState) -> RbacState:
        if state.version < self.current.version:
            raise TransportError("rbac state version regressed")
        self.current = state
        self.storage.save_rbac_state(state)
        return state

    def parse_subject_identity(self, user_id: str) -> SubjectIdentity:
        return SubjectIdentity(name=user_id)

    def verify_service_account(self, user_id: str, public_key: str) -> ServiceAccount:
        identity = self.parse_subject_identity(user_id)
        account = self._find_service_account(identity.name)
        if account is None:
            raise TransportError("unknown service account")
        if not account.spec.enabled:
            raise TransportError("service account is disabled")
        if account.spec.publicKey != public_key:
            raise TransportError("request signer public key does not match service account key")
        return account

    def find_service_account(self, user_id: str) -> ServiceAccount | None:
        identity = self.parse_subject_identity(user_id)
        return self._find_service_account(identity.name)

    def authorize(self, user_id: str, public_key: str, verb: str, resource: str, namespace: str) -> bool:
        account = self.verify_service_account(user_id, public_key)
        bindings = self._bindings_for_subject(account.metadata.name)
        return self._allows_with_bindings(bindings, verb, resource, namespace)

    def can_i(self, user_id: str, public_key: str, verb: str, resource: str, namespace: str) -> bool:
        identity = self.parse_subject_identity(user_id)
        account = self._find_service_account(identity.name)
        if account is None:
            logger.debug(
                "rbac_can_i_denied user_id={} namespace={} verb={} resource={} reason=missing_service_account",
                user_id,
                namespace,
                verb,
                resource,
            )
            return False
        if not account.spec.enabled:
            logger.debug(
                "rbac_can_i_denied user_id={} namespace={} verb={} resource={} reason=service_account_disabled",
                user_id,
                namespace,
                verb,
                resource,
            )
            return False
        if account.spec.publicKey != public_key:
            logger.debug(
                "rbac_can_i_denied user_id={} namespace={} verb={} resource={} reason=public_key_mismatch",
                user_id,
                namespace,
                verb,
                resource,
            )
            return False
        bindings = self._bindings_for_subject(account.metadata.name)
        allowed = self._allows_with_bindings(bindings, verb, resource, namespace)
        logger.trace(
            "rbac_can_i_checked user_id={} namespace={} verb={} resource={} allowed={} binding_count={}",
            user_id,
            namespace,
            verb,
            resource,
            allowed,
            len(bindings),
        )
        return allowed

    def describe_auth_subject(self, user_id: str, public_key: str) -> str:
        identity = self.parse_subject_identity(user_id)
        account = self._find_service_account(identity.name)
        if account is None:
            return f"rbac=none subject={identity.name}"
        key_match = account.spec.publicKey == public_key
        bindings = self._bindings_for_subject(identity.name)
        binding_refs: list[str] = []
        index = 0
        while index < len(bindings):
            binding = bindings[index]
            binding_refs.append(f"{binding.metadata.name}->{binding.roleRef.name}")
            index += 1
        refs = ",".join(binding_refs) if binding_refs else "-"
        return f"rbac=service_account subject={identity.name} enabled={account.spec.enabled} key_match={key_match} bindings={refs}"

    def ensure_admin_bundle(self, user_id: str, public_key: str, engine: str) -> RbacState:
        identity = self.parse_subject_identity(user_id)

        account = ServiceAccount(
            metadata=msgspec.convert({"name": identity.name}, type=type(ServiceAccount().metadata)),
            spec=ServiceAccountSpec(engine=engine, publicKey=public_key, enabled=True),
        )
        role = Role(
            metadata=msgspec.convert({"name": "admin"}, type=type(Role().metadata)),
            rules=[PolicyRule(apiGroups=["*"], namespaces=["*"], resources=["*"], verbs=["*"])],
        )
        binding = RoleBinding(
            metadata=msgspec.convert({"name": f"admin-binding-{identity.name}"}, type=type(RoleBinding().metadata)),
            subjects=[Subject(subjectKind="ServiceAccount", name=identity.name)],
            roleRef=RoleRef(apiGroup="rbac.authorization.xenage.dev", kindName="Role", name="admin"),
        )

        next_state = self._upsert_service_account(self.current, account)
        next_state = self._upsert_role(next_state, role)
        next_state = self._upsert_role_binding(next_state, binding)
        return self.replace_state(next_state)

    def ensure_admin_user(self, user_id: str, public_key: str, engine: str = "gui/v1", read_only: bool = False) -> UserRecord:
        existing = self.find_service_account(user_id)
        if existing is not None:
            if existing.spec.publicKey != public_key:
                raise TransportError("existing admin user has different public key")
            if not existing.spec.enabled:
                raise TransportError("admin user is disabled")
            return self._service_account_to_user_record(existing)
        if read_only:
            raise TransportError("admin user not found and running in read-only mode")
        self.ensure_admin_bundle(user_id, public_key, engine)
        created = self.find_service_account(user_id)
        if created is None:
            raise TransportError("failed to create admin user")
        return self._service_account_to_user_record(created)

    @staticmethod
    def _ensure_cluster_wide_manifest(manifest: dict[str, object]) -> None:
        metadata = manifest.get("metadata")
        if isinstance(metadata, dict):
            if "namespace" in metadata:
                raise TransportError("metadata.namespace is not supported for RBAC resources; use role.rules[].namespaces scope")

    def apply_manifest(self, manifest: dict[str, object]) -> dict[str, object]:
        api_version = str(manifest.get("apiVersion", ""))
        kind = str(manifest.get("kind", ""))
        self._ensure_cluster_wide_manifest(manifest)

        if api_version == "xenage.dev/v1" and kind == "ServiceAccount":
            account = msgspec.convert(manifest, type=ServiceAccount)
            next_state = self._upsert_service_account(self.current, account)
            self.replace_state(next_state)
            return {
                "kind": account.kind,
                "name": account.metadata.name,
                "namespace": "cluster",
                "status": "applied",
            }

        if api_version == "rbac.authorization.xenage.dev/v1" and kind == "Role":
            role = msgspec.convert(manifest, type=Role)
            next_state = self._upsert_role(self.current, role)
            self.replace_state(next_state)
            return {
                "kind": role.kind,
                "name": role.metadata.name,
                "namespace": "cluster",
                "status": "applied",
            }

        if api_version == "rbac.authorization.xenage.dev/v1" and kind == "RoleBinding":
            binding = msgspec.convert(manifest, type=RoleBinding)
            if self._find_role(binding.roleRef.name) is None:
                raise TransportError("roleRef points to missing role")
            next_state = self._upsert_role_binding(self.current, binding)
            self.replace_state(next_state)
            return {
                "kind": binding.kind,
                "name": binding.metadata.name,
                "namespace": "cluster",
                "status": "applied",
            }

        raise TransportError("unsupported resource apiVersion/kind")

    def list_resources(self, resource: str, namespace: str) -> list[dict[str, object]]:
        _ = namespace
        values: list[dict[str, object]] = []
        if resource == "serviceaccounts":
            index = 0
            while index < len(self.current.serviceAccounts):
                values.append(msgspec.to_builtins(self.current.serviceAccounts[index], str_keys=True))
                index += 1
            return values
        if resource == "roles":
            index = 0
            while index < len(self.current.roles):
                values.append(msgspec.to_builtins(self.current.roles[index], str_keys=True))
                index += 1
            return values
        if resource == "rolebindings":
            index = 0
            while index < len(self.current.roleBindings):
                values.append(msgspec.to_builtins(self.current.roleBindings[index], str_keys=True))
                index += 1
            return values
        raise TransportError("unsupported resource type")

    def _allows_with_bindings(self, bindings: list[RoleBinding], verb: str, resource: str, namespace: str) -> bool:
        role_index = self._role_index()
        index = 0
        while index < len(bindings):
            binding = bindings[index]
            role = role_index.get(binding.roleRef.name)
            if role is not None and self._role_allows(role, verb, resource, namespace):
                return True
            index += 1
        return False

    def _find_service_account(self, name: str) -> ServiceAccount | None:
        index = 0
        while index < len(self.current.serviceAccounts):
            item = self.current.serviceAccounts[index]
            if item.metadata.name == name:
                return item
            index += 1
        return None

    def _find_role(self, name: str) -> Role | None:
        index = 0
        while index < len(self.current.roles):
            item = self.current.roles[index]
            if item.metadata.name == name:
                return item
            index += 1
        return None

    def _role_index(self) -> dict[str, Role]:
        result: dict[str, Role] = {}
        index = 0
        while index < len(self.current.roles):
            role = self.current.roles[index]
            result[role.metadata.name] = role
            index += 1
        return result

    def _bindings_for_subject(self, name: str) -> list[RoleBinding]:
        result: list[RoleBinding] = []
        index = 0
        while index < len(self.current.roleBindings):
            binding = self.current.roleBindings[index]
            subject_index = 0
            while subject_index < len(binding.subjects):
                subject = binding.subjects[subject_index]
                if subject.subjectKind == "ServiceAccount" and subject.name == name:
                    result.append(binding)
                subject_index += 1
            index += 1
        return result

    def _role_allows(self, role: Role, verb: str, resource: str, namespace: str) -> bool:
        rule_index = 0
        while rule_index < len(role.rules):
            rule = role.rules[rule_index]
            namespaces = rule.namespaces if rule.namespaces else ["*"]
            if self._match(rule.verbs, verb) and self._match(rule.resources, resource) and self._match(namespaces, namespace):
                return True
            rule_index += 1
        return False

    def _match(self, values: list[str], expected: str) -> bool:
        index = 0
        while index < len(values):
            value = values[index]
            if value == "*" or value == expected:
                return True
            index += 1
        return False

    def _service_account_to_user_record(self, account: ServiceAccount) -> UserRecord:
        return UserRecord(
            user_id=account.metadata.name,
            public_key=account.spec.publicKey,
            roles=[UserRoleBinding(role="admin")],
            enabled=account.spec.enabled,
            created_at="",
        )

    def _upsert_service_account(self, state: RbacState, account: ServiceAccount) -> RbacState:
        service_accounts: list[ServiceAccount] = []
        replaced = False
        index = 0
        while index < len(state.serviceAccounts):
            item = state.serviceAccounts[index]
            same = item.metadata.name == account.metadata.name
            if same:
                replaced = True
                if item.spec.publicKey != account.spec.publicKey:
                    raise TransportError("service account publicKey is immutable")
                service_accounts.append(account)
            else:
                service_accounts.append(item)
            index += 1
        if not replaced:
            service_accounts.append(account)
        return RbacState(
            version=state.version + 1,
            serviceAccounts=sorted(service_accounts, key=lambda item: item.metadata.name),
            roles=state.roles,
            roleBindings=state.roleBindings,
        )

    def _upsert_role(self, state: RbacState, role: Role) -> RbacState:
        roles: list[Role] = []
        replaced = False
        index = 0
        while index < len(state.roles):
            item = state.roles[index]
            if item.metadata.name == role.metadata.name:
                roles.append(role)
                replaced = True
            else:
                roles.append(item)
            index += 1
        if not replaced:
            roles.append(role)
        return RbacState(
            version=state.version + 1,
            serviceAccounts=state.serviceAccounts,
            roles=sorted(roles, key=lambda item: item.metadata.name),
            roleBindings=state.roleBindings,
        )

    def _upsert_role_binding(self, state: RbacState, binding: RoleBinding) -> RbacState:
        role_bindings: list[RoleBinding] = []
        replaced = False
        index = 0
        while index < len(state.roleBindings):
            item = state.roleBindings[index]
            if item.metadata.name == binding.metadata.name:
                role_bindings.append(binding)
                replaced = True
            else:
                role_bindings.append(item)
            index += 1
        if not replaced:
            role_bindings.append(binding)
        return RbacState(
            version=state.version + 1,
            serviceAccounts=state.serviceAccounts,
            roles=state.roles,
            roleBindings=sorted(role_bindings, key=lambda item: item.metadata.name),
        )
