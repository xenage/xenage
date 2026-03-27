from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import msgspec


@dataclass(frozen=True)
class Table:
    headers: list[str]
    rows: list[list[str]]


def render_table(table: Table) -> str:
    widths: list[int] = []
    index = 0
    while index < len(table.headers):
        max_width = len(table.headers[index])
        row_index = 0
        while row_index < len(table.rows):
            value = table.rows[row_index][index]
            if len(value) > max_width:
                max_width = len(value)
            row_index += 1
        widths.append(max_width)
        index += 1

    parts: list[str] = []
    header_cells: list[str] = []
    header_index = 0
    while header_index < len(table.headers):
        header_cells.append(table.headers[header_index].ljust(widths[header_index]))
        header_index += 1
    parts.append("  ".join(header_cells))

    row_index = 0
    while row_index < len(table.rows):
        cells: list[str] = []
        column_index = 0
        while column_index < len(table.headers):
            cells.append(table.rows[row_index][column_index].ljust(widths[column_index]))
            column_index += 1
        parts.append("  ".join(cells))
        row_index += 1
    return "\n".join(parts) + "\n"


def render_json(value: object) -> str:
    payload = msgspec.json.encode(value)
    pretty = msgspec.json.format(payload, indent=2)
    return pretty.decode("utf-8") + "\n"


def render_yaml(value: object) -> str:
    return msgspec.yaml.encode(value).decode("utf-8")


def first_endpoint(endpoints: Sequence[str]) -> str:
    if len(endpoints) == 0:
        return "-"
    return endpoints[0]
