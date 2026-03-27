# Node Types

Xenage has two node roles in the cluster:

| Role | Main responsibility | Writes cluster membership | Participates in failover |
|---|---|---|---|
| `control-plane` | Owns group state, event replication, admin/API surfaces | Yes | Yes |
| `runtime` | Executes workloads and consumes state from control-plane | No | No |

## Shared Base Behavior

Both roles inherit from `BaseNode` and share:

- Persistent node identity (`node_id`, role, key pair, endpoints)
- Signed HTTP transport client
- Local `GroupState` storage
- Local RBAC state storage
- Core route handling primitives
- Unified auth description used in request logs (`cluster` + `RBAC` summary)

## Control Plane Node

`ControlPlaneNode` extends the base node with:

- Bootstrap token issuing/validation
- Group membership mutation (`join`, `revoke`, endpoint updates)
- Event log replication (`ControlPlaneEventManager`)
- GUI-facing snapshots and event pages
- Sync status tracking for peers (`unknown`, `syncing`, `synced`, `broken`)
- Leader failover checks and leader promotion

### Leader-only operations

The active leader is required for:

- `POST /v1/join`
- `POST /v1/revoke`
- `POST /v1/endpoints`
- `POST /v1/control-plane/sync-status`
- `GET /v1/control-plane/events`
- `GET /v1/gui/cluster`
- `GET /v1/gui/events`

## Runtime Node

`RuntimeNode` behavior is intentionally smaller:

- Joins cluster through leader using bootstrap token
- Validates leader key from join response
- Polls `/v1/state/current` from control-plane endpoints
- Keeps local state fresh for runtime operations
- Does not expose an inbound HTTP endpoint

Runtime nodes do not mutate membership and do not emit control-plane sync events.
Code layout uses package modules:

- `src/xenage/nodes/control_plane/control_plane_api/*` for control-plane API routing/views/logic
- `src/xenage/nodes/runtime/main.py` for `RuntimeNode`

## Identity and Trust

All node-to-node requests are signed with Ed25519 keys. Request verification checks:

- Timestamp skew window
- Nonce replay protection
- Signature validity over method/path/body digest
- Optional signer key consistency with known `GroupState`
