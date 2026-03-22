# RULES.md

## Purpose
This document defines mandatory engineering rules for changes in Xenage.
Any new change must comply with these rules before merge.

## Project Map (important parts)
- `structures/` — single source of truth for control-plane types and schemas (via `msgspec.Struct`).
- `structures/resources/*` — all resource contracts for API/events/GUI tables.
- `structures/resources/manifest/generator.py` — release manifest builder for GUI.
- `scripts/export_structures.py` — codegen for JSON/TS manifest and docs.
- `src/xenage/` — backend/runtime/control-plane logic.
- `apps/xenage-gui/src/` — GUI (React + TypeScript).
- `apps/xenage-gui/src/generated/*` — generated only, do not edit manually.
- `tests/` — pytest test suite, primary entry point for TDD.

## Non-Negotiable Rules
1. Strict typing everywhere.
2. Avoid `try/except` as primary control flow.
3. Test-driven development.
4. Modularity and decomposition.
5. Class-based files as the primary style.
6. Maximum 400 lines per file (generated files excluded).
7. Avoid `*args`/`**kwargs/*` in function signatures.
8. All contract changes must go through `structures/resources/*` with frontend codegen.
9. Do not keep any legacy/deprecated code: at the platform development stage, always remove old feature code when it is unused or being replaced with a new implementation.

## 1) Strict Typing
- Python:
  - All functions/methods must have explicit type hints (inputs and outputs).
  - No implicit `Any` in new logic.
  - Domain data must be described with typed structures (`Structure`, `ResourceDocument`).
- TypeScript:
  - No `any`/unsafe casts without justification.
  - Use types from `apps/xenage-gui/src/types/*` and `apps/xenage-gui/src/generated/controlPlaneSchema.ts`.

## 2) Error Handling (no try/except overuse)
- Prefer:
  - Explicit input/state validation.
  - Narrow domain exceptions (`StateValidationError`, `TransportError`, etc.).
- Forbidden:
  - Broad `except Exception` without a critical reason.
  - Exceptions for normal branching when an explicit if/guard check is possible.
- If `try/except` is unavoidable (I/O, network, cryptography):
  - Catch only specific error types.
  - Log context and re-raise/convert to a domain exception.

## 3) TDD Process
- Mandatory cycle: `RED -> GREEN -> REFACTOR`.
- For each new feature/fix:
  - Write the test first in `tests/` (or in frontend next to code as `*.test.tsx|*.test.ts`).
  - Implement the minimum code needed to make the test pass.
  - Refactor without behavior changes.
- Every regression must be covered by a dedicated reproducing test.

## 4) Modularity
- One file = one clear responsibility.
- Split complex logic into dedicated components/modules (state, sync, urls, rbac, transport).
- Extract repetitive logic into reusable services/utilities.

## 5) Class-Based Style
- For backend domain logic, use classes as the primary container for behavior and state.
- For data contracts, use `msgspec.Struct` via `Structure/ResourceDocument`.
- Functional style is allowed for small stateless helper functions.

## 6) File Size Limit
- Limit: no more than 400 lines per hand-written file.
- Warning threshold: 350+ lines — plan decomposition early.
- If a file exceeds the limit:
  - extract submodules/components,
  - split responsibilities into dedicated folders.
- Exception: generated files (`apps/xenage-gui/src/generated/*`, `docs/structures/*`).

## 7) Public Signatures
- Do not use `*args` and `**kwargs` in public functions/methods.
- Parameters must be explicit and typed.
- For extensibility, use typed config objects/structs instead of hidden variadic arguments.

## 8) Structures + Frontend Codegen (mandatory)
Any API/resource/table schema change must follow this flow:
1. Update/add structures in `structures/resources/*` (and `structures/common.py` when needed).
2. Update manifest logic when needed (`structures/resources/manifest/*`).
3. Run codegen:
   - `.venv/bin/python scripts/export_structures.py`
4. Verify and commit related artifacts:
   - `apps/xenage-gui/src/generated/control-plane-release.json`
   - `apps/xenage-gui/src/generated/controlPlaneSchema.ts`
   - `docs/structures/*`

## Definition Of Done
- Types are complete and consistent (Python + TS).
- Tests are added and passing.
- No unjustified broad `try/except`.
- Files are within the 400-line limit (except generated).
- Contracts are updated via `structures/resources/*` and codegen is completed.
