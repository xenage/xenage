from __future__ import annotations

from typing import Literal

import msgspec

from .base import Structure


class TypeMeta(Structure):
    kind = "TypeMeta"
    kindName: str
    apiVersion: str = "xenage.io/v1alpha1"


class ObjectMeta(Structure):
    kind = "ObjectMeta"
    name: str
    namespace: str = "default"
    labels: dict[str, str] = msgspec.field(default_factory=dict)
    annotations: dict[str, str] = msgspec.field(default_factory=dict)
    uid: str | None = None
    generation: int = 1
    createdAt: str | None = None


class Condition(Structure):
    kind = "Condition"
    type: str
    status: Literal["True", "False", "Unknown"]
    reason: str
    message: str
    lastTransitionTime: str


class ResourceRef(Structure):
    kind = "ResourceRef"
    kindName: str
    name: str
    apiVersion: str = "xenage.io/v1alpha1"
    namespace: str = "default"


class MetricsWindow(Structure):
    kind = "MetricsWindow"
    lastHour: float = 0.0
    lastDay: float = 0.0
    lastWeek: float = 0.0
