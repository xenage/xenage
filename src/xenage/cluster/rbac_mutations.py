from __future__ import annotations

from structures.resources.rbac import RbacState
from xenage.network.http_transport import TransportError


def delete_action_name(manifest: dict[str, object]) -> str | None:
    metadata = manifest.get("metadata")
    if not isinstance(metadata, dict):
        return None
    annotations = metadata.get("annotations")
    if not isinstance(annotations, dict):
        return None
    action = str(annotations.get("xenage.io/action", "")).strip().lower()
    if action != "delete":
        return None
    name = str(metadata.get("name", "")).strip()
    if not name:
        raise TransportError("metadata.name is required for delete action")
    return name


def delete_service_account(state: RbacState, service_account_name: str) -> RbacState:
    service_accounts = [
        item for item in state.serviceAccounts if item.metadata.name != service_account_name
    ]
    role_bindings = [
        binding for binding in state.roleBindings if all(
            not (subject.subjectKind == "ServiceAccount" and subject.name == service_account_name)
            for subject in binding.subjects
        )
    ]
    changed = len(service_accounts) != len(state.serviceAccounts) or len(role_bindings) != len(state.roleBindings)
    if not changed:
        return state
    return RbacState(
        version=state.version + 1,
        serviceAccounts=sorted(service_accounts, key=lambda item: item.metadata.name),
        roles=state.roles,
        roleBindings=sorted(role_bindings, key=lambda item: item.metadata.name),
    )


def delete_role(state: RbacState, role_name: str) -> RbacState:
    roles = [item for item in state.roles if item.metadata.name != role_name]
    role_bindings = [binding for binding in state.roleBindings if binding.roleRef.name != role_name]
    changed = len(roles) != len(state.roles) or len(role_bindings) != len(state.roleBindings)
    if not changed:
        return state
    return RbacState(
        version=state.version + 1,
        serviceAccounts=state.serviceAccounts,
        roles=sorted(roles, key=lambda item: item.metadata.name),
        roleBindings=sorted(role_bindings, key=lambda item: item.metadata.name),
    )


def delete_role_binding(state: RbacState, role_binding_name: str) -> RbacState:
    role_bindings = [item for item in state.roleBindings if item.metadata.name != role_binding_name]
    if len(role_bindings) == len(state.roleBindings):
        return state
    return RbacState(
        version=state.version + 1,
        serviceAccounts=state.serviceAccounts,
        roles=state.roles,
        roleBindings=sorted(role_bindings, key=lambda item: item.metadata.name),
    )
