from __future__ import annotations

from typing import TypeVar

import msgspec

StructureT = TypeVar("StructureT")


def encode_value(value: object) -> bytes:
    return msgspec.json.encode(value)


def decode_value(payload: bytes, value_type: type[StructureT]) -> StructureT:
    return msgspec.json.decode(payload, type=value_type)
