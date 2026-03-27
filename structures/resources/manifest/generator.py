from __future__ import annotations

import re
from types import UnionType
from typing import Annotated, Union, get_args, get_origin

import msgspec

from ..base import ResourceDocument, Structure
from .gui import GUI_TABLES, NAVIGATION, RESOURCE_TYPES


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


def _field_label(name: str) -> str:
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", name.replace("_", " "))
    return " ".join(segment.capitalize() for segment in spaced.split())


def _column_width(name: str, field_type: str, is_array: bool) -> int:
    lowered = name.lower()
    if lowered == "sequence":
        return 90
    if lowered in {"details", "endpoints"}:
        return 440
    if lowered.endswith("_at") or lowered.endswith("at"):
        return 220
    if lowered.endswith("_id") or lowered.endswith("id") or lowered.endswith("_key"):
        return 220
    if is_array:
        return 360
    if field_type in {"int", "float"}:
        return 140
    if field_type == "bool":
        return 100
    return 220


def _column_min_width(width: int) -> int:
    if width >= 400:
        return 220
    if width >= 300:
        return 180
    if width >= 220:
        return 140
    return 100


def _table_columns(struct_type: type[Structure]) -> list[dict[str, object]]:
    columns: list[dict[str, object]] = []
    for field in msgspec.structs.fields(struct_type):
        field_type, is_array = _type_label(field.type)
        width = _column_width(field.name, field_type, is_array)
        
        display_only = False
        if get_origin(field.type) is Annotated:
            display_only = "display_only" in get_args(field.type)

        columns.append(
            {
                "key": field.name,
                "label": _field_label(field.name),
                "path": field.name,
                "type": field_type,
                "isArray": is_array,
                "width": width,
                "minWidth": _column_min_width(width),
                "displayOnly": display_only,
            }
        )
    return columns


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


def _sample_value_for_annotation(annotation: object) -> object:
    origin = get_origin(annotation)

    if origin is Annotated:
        return _sample_value_for_annotation(get_args(annotation)[0])

    if origin in (UnionType, Union):
        candidates = [item for item in get_args(annotation) if item is not type(None)]
        if not candidates:
            return None
        return _sample_value_for_annotation(candidates[0])

    if str(origin).endswith("Literal"):
        literal_values = get_args(annotation)
        return literal_values[0] if literal_values else ""

    if origin is list:
        return []

    if origin is dict:
        return {}

    if origin is tuple:
        return []

    if origin is None and isinstance(annotation, type):
        if issubclass(annotation, Structure):
            return _sample_struct(annotation)
        if annotation is str:
            return ""
        if annotation is bool:
            return False
        if annotation is int:
            return 0
        if annotation is float:
            return 0.0

    return ""


def _sample_struct(struct_type: type[Structure]) -> dict[str, object]:
    sample: dict[str, object] = {}
    for field in msgspec.structs.fields(struct_type):
        if field.default is not msgspec.NODEFAULT:
            sample[field.name] = _sample_object(field.default)
            continue
        if field.default_factory is not msgspec.NODEFAULT:
            sample[field.name] = _sample_object(field.default_factory())
            continue
        sample[field.name] = _sample_value_for_annotation(field.type)
    return sample


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


def _table_manifest(item: dict[str, object]) -> dict[str, object]:
    row_type = item["row_type"]
    if not isinstance(row_type, type):
        raise TypeError(f"invalid table row type: {row_type!r}")
    if not issubclass(row_type, Structure):
        raise TypeError(f"invalid table row type (not a Structure): {row_type!r}")
    return {
        "kind": item["kind"],
        "title": item["title"],
        "source": item["source"],
        "rowKind": row_type.kind,
        "rowKey": item["row_key"],
        "defaultSort": item["default_sort"],
        "pageSize": item.get("page_size"),
        "columns": _table_columns(row_type),
        "sample": _sample_struct(row_type),
    }


def build_release_manifest() -> dict[str, object]:
    resources = [_resource_manifest(resource_type) for resource_type in RESOURCE_TYPES]
    tables = [_table_manifest(item) for item in GUI_TABLES]
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
        "tables": tables,
    }
