from __future__ import annotations

from pathlib import Path

import msgspec


class ManifestParser:
    def parse_file(self, file_path: str) -> list[dict[str, object]]:
        raw = Path(file_path).read_text(encoding="utf-8")
        docs = self._split_documents(raw)
        parsed: list[dict[str, object]] = []
        index = 0
        while index < len(docs):
            doc = docs[index].strip()
            if doc:
                payload = msgspec.yaml.decode(doc.encode("utf-8"), type=dict[str, object])
                parsed.append(payload)
            index += 1
        return parsed

    def _split_documents(self, raw: str) -> list[str]:
        lines = raw.splitlines()
        docs: list[str] = []
        current: list[str] = []
        index = 0
        while index < len(lines):
            line = lines[index]
            if line.strip() == "---":
                docs.append("\n".join(current))
                current = []
            else:
                current.append(line)
            index += 1
        docs.append("\n".join(current))
        return docs
