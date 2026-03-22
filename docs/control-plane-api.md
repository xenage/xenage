# Control Plane API

Control-plane API is served over HTTP with request-signature verification for protected routes.

## Auth Model

Protected requests include headers:

- `x-node-id`
- `x-timestamp`
- `x-nonce`
- `x-signature`
- `x-public-key`

The server verifies timestamp skew, nonce replay, and Ed25519 signature.

Unsigned exception:

- `POST /v1/gui/bootstrap-user` is bootstrap-token based and does not require request signature.

## Routes

| Method | Path | Purpose | Notes |
|---|---|---|---|
| `GET` | `/v1/heartbeat` | Liveness check | Control-plane nodes |
| `POST` | `/v1/join` | Join control-plane/runtime node | Leader-only |
| `POST` | `/v1/revoke` | Revoke node from membership | Leader-only |
| `POST` | `/v1/endpoints` | Update node endpoints | Leader-only |
| `POST` | `/v1/control-plane/sync-status` | Report follower sync status | Control-plane peers, leader-only handler |
| `GET` | `/v1/control-plane/events` | Page control-plane sync events | Leader-only; `after_event_id`, `limit` |
| `GET` | `/v1/state/current` | Return current signed group state | Used by runtimes and peers |
| `GET` | `/v1/gui/cluster` | Build GUI cluster snapshot | Leader-only, admin user required |
| `GET` | `/v1/gui/events` | Page GUI/audit events | Leader-only, admin user required |
| `POST` | `/v1/resources/apply` | Apply RBAC manifest | Signed, RBAC `apply` required |
| `POST` | `/v1/auth/can-i` | Check RBAC permission | Signed |
| `GET` | `/v1/resources/{resource}` | List RBAC resources | Signed, RBAC `list` required (`namespace` query) |
| `POST` | `/v1/gui/bootstrap-user` | Bootstrap admin GUI user config | Leader-only, bootstrap token based |

Resource list endpoint is prefix-routed under `/v1/resources/*` (for example: `serviceaccounts`, `roles`, `rolebindings`).

## Paging Parameters

`/v1/control-plane/events`:

- `after_event_id` (default `0`)
- `limit` (bounded to `1..500`)

`/v1/gui/events`:

- `limit` (bounded to `1..200`)
- `before_sequence` (optional cursor)

`/v1/resources/{resource}`:

- `namespace` (default `default`)

## Failure Responses

Transport and auth failures return JSON error payloads:

```json
{"error":"..."}
```

with HTTP `401` for transport/auth errors and `500` for internal errors.

Runtime nodes are poll-only clients and do not expose inbound API routes.

## Request Logging

Signed request logs include:

- `Signed BY: <x-public-key>`
- `Auth by: <cluster + RBAC summary>`

`Auth by` includes cluster identity (`control-plane`/`runtime`/`external`) and RBAC subject details (`serviceAccountName`, service account status, key match, bindings).
