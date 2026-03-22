from __future__ import annotations

import msgspec
from typing import Literal

from ..base import Structure
from .base import ResourceDocument


class RbacObjectMeta(Structure):
    kind = "RbacObjectMeta"
    name: str
    labels: dict[str, str] = msgspec.field(default_factory=dict)
    annotations: dict[str, str] = msgspec.field(default_factory=dict)
    uid: str | None = None
    generation: int = 1
    createdAt: str | None = None


class ServiceAccountSpec(Structure):
    kind = "ServiceAccountSpec"
    engine: str
    publicKey: str
    enabled: bool = True


class ServiceAccount(ResourceDocument):
    kind = "ServiceAccount"
    apiVersion: str = "xenage.dev/v1"
    metadata: RbacObjectMeta = RbacObjectMeta(name="default")
    spec: ServiceAccountSpec = ServiceAccountSpec(engine="runtime/v1", publicKey="")


class PolicyRule(Structure):
    kind = "PolicyRule"
    apiGroups: list[str] = msgspec.field(default_factory=lambda: [""])
    namespaces: list[str] = msgspec.field(default_factory=lambda: ["*"])
    resources: list[str] = msgspec.field(default_factory=list)
    verbs: list[str] = msgspec.field(default_factory=list)


class Role(ResourceDocument):
    kind = "Role"
    apiVersion: str = "rbac.authorization.xenage.dev/v1"
    metadata: RbacObjectMeta = RbacObjectMeta(name="default")
    rules: list[PolicyRule] = msgspec.field(default_factory=list)


class Subject(Structure):
    kind = "Subject"
    name: str
    subjectKind: Literal["ServiceAccount"] = msgspec.field(name="kind", default="ServiceAccount")


class RoleRef(Structure):
    kind = "RoleRef"
    apiGroup: str
    name: str
    kindName: Literal["Role"] = msgspec.field(name="kind", default="Role")


class RoleBinding(ResourceDocument):
    kind = "RoleBinding"
    apiVersion: str = "rbac.authorization.xenage.dev/v1"
    metadata: RbacObjectMeta = RbacObjectMeta(name="default")
    subjects: list[Subject] = msgspec.field(default_factory=list)
    roleRef: RoleRef = RoleRef(apiGroup="rbac.authorization.xenage.dev", name="")


class RbacState(Structure):
    kind = "RbacState"
    version: int = 0
    serviceAccounts: list[ServiceAccount] = msgspec.field(default_factory=list)
    roles: list[Role] = msgspec.field(default_factory=list)
    roleBindings: list[RoleBinding] = msgspec.field(default_factory=list)
