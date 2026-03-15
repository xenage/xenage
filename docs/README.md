# Xenage Documentation

This folder contains architecture and API docs for the Xenage control plane/runtime system.

## Architecture

- [Node Types](node-types.md)
- [Node Sync](sync-nodes.md)
- [Events](events.md)
- [Control Plane API](control-plane-api.md)

## Auto-generated Structure Docs

- [Structures Reference](structures/README.md)

These files are generated from the Python structure definitions in `structures/`.

## Regenerate Docs

Run from the repository root:

```bash
.venv/bin/python scripts/export_structures.py
```

Useful flags:

```bash
# Change destination for generated structure markdown
.venv/bin/python scripts/export_structures.py --out-structures-docs docs/structures

# Skip structure markdown generation (JSON/TS only)
.venv/bin/python scripts/export_structures.py --skip-structures-docs
```
