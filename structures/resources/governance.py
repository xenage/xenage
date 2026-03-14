from __future__ import annotations

from typing import Literal

from ..base import Structure
from ..common import ObjectMeta
from .base import ResourceDocument


class ResourceTypeSpec(Structure):
    kind = "ResourceTypeSpec"
    group: str
    version: str
    scope: Literal["Cluster", "Namespaced"]
    printerColumns: list[str]


class ResourceTypeStatus(Structure):
    kind = "ResourceTypeStatus"
    phase: Literal["Published"]
    instances: int
    schemaVersion: str


class ResourceType(ResourceDocument):
    kind = "ResourceType"
    metadata: ObjectMeta = ObjectMeta(name="agents.xenage.io")
    spec: ResourceTypeSpec = ResourceTypeSpec(group="xenage.io", version="v1alpha1", scope="Namespaced", printerColumns=["phase", "replicas", "successRatePct"])
    status: ResourceTypeStatus = ResourceTypeStatus(phase="Published", instances=8, schemaVersion="2026-03-14")


class CustomResourceSpec(Structure):
    kind = "CustomResourceSpec"
    typeRef: str
    owner: str
    desiredState: dict[str, str]


class CustomResourceStatus(Structure):
    kind = "CustomResourceStatus"
    phase: Literal["Reconciling", "Ready", "Error"]
    lastAppliedAt: str
    driftDetected: bool


class CustomResource(ResourceDocument):
    kind = "CustomResource"
    metadata: ObjectMeta = ObjectMeta(name="support-bot-prod")
    spec: CustomResourceSpec = CustomResourceSpec(typeRef="Agent", owner="customer-success", desiredState={"replicas": "3", "modelRef": "gpt-5.4-mini"})
    status: CustomResourceStatus = CustomResourceStatus(phase="Ready", lastAppliedAt="2026-03-14T08:12:00Z", driftDetected=False)


class SecretSpec(Structure):
    kind = "SecretSpec"
    type: Literal["Opaque", "APIKey", "OAuthToken"]
    mountTargets: list[str]
    rotationPolicy: str


class SecretStatus(Structure):
    kind = "SecretStatus"
    phase: Literal["Active", "Expiring", "Revoked"]
    lastRotatedAt: str
    consumers: int


class Secret(ResourceDocument):
    kind = "Secret"
    metadata: ObjectMeta = ObjectMeta(name="openai-api-key")
    spec: SecretSpec = SecretSpec(type="APIKey", mountTargets=["Agent/research-agent"], rotationPolicy="30d")
    status: SecretStatus = SecretStatus(phase="Active", lastRotatedAt="2026-03-01T00:00:00Z", consumers=3)


class AccessControlSpec(Structure):
    kind = "AccessControlSpec"
    subject: str
    role: str
    scope: str
    verbs: list[str]


class AccessControlStatus(Structure):
    kind = "AccessControlStatus"
    phase: Literal["Bound", "Pending"]
    inherited: bool
    lastReviewedAt: str


class AccessControl(ResourceDocument):
    kind = "AccessControl"
    metadata: ObjectMeta = ObjectMeta(name="ops-admin")
    spec: AccessControlSpec = AccessControlSpec(subject="group:ops", role="admin", scope="cluster/demo-cluster", verbs=["get", "list", "watch", "patch"])
    status: AccessControlStatus = AccessControlStatus(phase="Bound", inherited=False, lastReviewedAt="2026-03-10T09:00:00Z")


class ConfigHistorySpec(Structure):
    kind = "ConfigHistorySpec"
    resourceRef: str
    author: str
    changeSummary: str
    revision: str


class ConfigHistoryStatus(Structure):
    kind = "ConfigHistoryStatus"
    phase: Literal["Applied", "RolledBack"]
    changedAt: str
    driftResolved: bool


class ConfigHistory(ResourceDocument):
    kind = "ConfigHistory"
    metadata: ObjectMeta = ObjectMeta(name="agent-research-agent-r42")
    spec: ConfigHistorySpec = ConfigHistorySpec(resourceRef="Agent/research-agent", author="ops@example.com", changeSummary="Raised concurrency from 6 to 8", revision="42")
    status: ConfigHistoryStatus = ConfigHistoryStatus(phase="Applied", changedAt="2026-03-14T07:18:00Z", driftResolved=True)
