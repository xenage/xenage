from __future__ import annotations

from structures.resources.membership import NodeRecord


def sort_control_planes(control_planes: list[NodeRecord]) -> list[NodeRecord]:
    return sorted(control_planes, key=lambda item: (item.node_id, item.public_key))
