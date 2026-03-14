from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar, Self

import msgspec


class Structure(msgspec.Struct, kw_only=True, omit_defaults=True, frozen=True):
    """Shared base for all typed control plane documents."""

    kind: ClassVar[str]

    @classmethod
    def _read_input(cls, value: str | bytes | bytearray | Path) -> bytes:
        if isinstance(value, Path):
            return value.read_bytes()

        if isinstance(value, (bytes, bytearray)):
            return bytes(value)

        if isinstance(value, str):
            path = Path(value)
            if path.exists():
                return path.read_bytes()
            return value.encode("utf-8")

        raise TypeError(f"Unsupported input type for {cls.__name__}: {type(value)!r}")

    @classmethod
    def load_json(cls, value: str | bytes | bytearray | Path) -> Self:
        return msgspec.json.decode(cls._read_input(value), type=cls)

    @classmethod
    def load_jston(cls, value: str | bytes | bytearray | Path) -> Self:
        return cls.load_json(value)

    @classmethod
    def load_yaml(cls, value: str | bytes | bytearray | Path) -> Self:
        return msgspec.yaml.decode(cls._read_input(value), type=cls)

    def dump_json(self, *, indent: int = 2) -> str:
        return msgspec.json.format(msgspec.json.encode(self), indent=indent).decode("utf-8")

    def dump_yaml(self) -> str:
        return msgspec.yaml.encode(self).decode("utf-8")

    def to_builtins(self) -> dict[str, Any]:
        return msgspec.to_builtins(self)
