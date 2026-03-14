from __future__ import annotations

from types import UnionType
from typing import Annotated, Union, get_args, get_origin

import msgspec

from ..base import Structure
from .base import ResourceDocument
from .cluster import Cluster, Node
from .governance import (
    AccessControl,
    ConfigHistory,
    CustomResource,
    ResourceType,
    Secret,
)
from .integration import APIAccess, MCP, Model, Tool
from .observability import Alert, Event, Log
from .runtime import Agent, ExecutionEnvironment, Interface, Job, Run, Session, Usage

RESOURCE_TYPES: tuple[type[ResourceDocument], ...] = (
    Cluster,
    Node,
    Agent,
    Run,
    Session,
    Tool,
    MCP,
    Job,
    Event,
    Log,
    ResourceType,
    CustomResource,
    ExecutionEnvironment,
    Secret,
    AccessControl,
    Interface,
    Model,
    APIAccess,
    ConfigHistory,
    Alert,
    Usage,
)

NAVIGATION = {
    "label": "Cluster",
    "children": [
        {"label": "Overview", "kind": "Cluster"},
        {"label": "Nodes", "kind": "Node"},
        {"label": "Agents", "kind": "Agent"},
        {"label": "Runs", "kind": "Run"},
        {"label": "Sessions", "kind": "Session"},
        {"label": "Tools", "kind": "Tool"},
        {"label": "MCP", "kind": "MCP"},
        {"label": "Jobs", "kind": "Job"},
        {"label": "Events", "kind": "Event"},
        {"label": "Logs", "kind": "Log"},
        {"label": "Resource Types", "kind": "ResourceType"},
        {"label": "Custom Resources", "kind": "CustomResource"},
        {"label": "Execution Environments", "kind": "ExecutionEnvironment"},
        {"label": "Secrets", "kind": "Secret"},
        {"label": "Access Control", "kind": "AccessControl"},
        {"label": "Interfaces", "kind": "Interface"},
        {"label": "Models", "kind": "Model"},
        {"label": "API Access", "kind": "APIAccess"},
        {"label": "Config History", "kind": "ConfigHistory"},
        {"label": "Alerts", "kind": "Alert"},
        {"label": "Usage", "kind": "Usage"},
    ],
}


def _type_label(annotation: object) -> tuple[str, bool]:
    origin = get_origin(annotation)
    if origin is list:
        inner, _ = _type_label(get_args(annotation)[0])
        return inner, True

    if origin is Annotated:
        return _type_label(get_args(annotation)[0])

    if origin in (UnionType, Union):
        options = [label for label, _ in (_type_label(arg) for arg in get_args(annotation)) if label != "NoneType"]
        if not options:
            return "unknown", False
        if len(options) == 1:
            return f"{options[0]}?", False
        return " | ".join(options), False

    if str(origin).endswith("Literal"):
        return "literal", False

    if origin is None:
        if isinstance(annotation, type):
            return annotation.__name__, False
        return str(annotation), False

    if origin is dict:
        return "map", False

    if origin is tuple:
        return "tuple", False

    name = getattr(origin, "__name__", str(origin))
    return name, False


def _field_docs(struct_type: type[Structure]) -> list[dict[str, object]]:
    fields: list[dict[str, object]] = []
    for field in msgspec.structs.fields(struct_type):
        field_type, is_array = _type_label(field.type)
        fields.append(
            {
                "name": field.name,
                "type": field_type,
                "required": field.default is msgspec.NODEFAULT and field.default_factory is msgspec.NODEFAULT,
                "isArray": is_array,
            }
        )
    return fields


def _sample_object(value: object) -> object:
    if isinstance(value, msgspec.Struct):
        result: dict[str, object] = {}
        for field in msgspec.structs.fields(type(value)):
            result[field.name] = _sample_object(getattr(value, field.name))
        return result

    if isinstance(value, list):
        return [_sample_object(item) for item in value]

    if isinstance(value, dict):
        return {key: _sample_object(item) for key, item in value.items()}

    return value


def _resource_manifest(resource_type: type[ResourceDocument]) -> dict[str, object]:
    sample = resource_type()
    return {
        "kind": resource_type.kind,
        "title": resource_type.kind.replace("API", "API "),
        "fields": _field_docs(resource_type),
        "sections": {
            "metadata": _field_docs(type(sample.metadata)),
            "spec": _field_docs(type(sample.spec)),
            "status": _field_docs(type(sample.status)),
        },
        "sample": _sample_object(sample),
    }


def build_release_manifest() -> dict[str, object]:
    resources = [_resource_manifest(resource_type) for resource_type in RESOURCE_TYPES]
    return {
        "apiVersion": "xenage.io/v1alpha1",
        "kind": "ControlPlaneRelease",
        "generatedAt": "2026-03-14T12:30:00Z",
        "product": {
            "name": "Xenage",
            "tagline": "AI Agent Control Plane",
        },
        "navigation": NAVIGATION,
        "resources": resources,
    }
