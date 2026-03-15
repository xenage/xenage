# Events

Xenage has two event layers with different purposes.

## 1. Control-Plane Sync Events

Purpose: deterministic replication of membership/user-state changes across control-plane nodes.

- Stream type: `ControlPlaneEventLog.items`
- Ordering key: `event_id` (strictly increasing, gap-free)
- Read API: `GET /v1/control-plane/events`

### Event Types

| `event_type` tag | Meaning |
|---|---|
| `group_state.apply` | Replace group state snapshot |
| `user_state.apply` | Replace user-state snapshot |
| `group.node_joined` | Add or replace a node in membership |
| `group.node_revoked` | Remove node from membership |
| `group.endpoints_updated` | Update endpoint map for a node |
| `group.leader_promoted` | Leader changed due to failover/promotion |
| `user.upserted` | User record changed |
| `user.event_appended` | User/audit log entry appended |

## 2. Cluster Audit Events (User Event Log)

Purpose: human-readable audit trail and GUI timeline.

- Stream type: `UserState.event_log`
- Ordering key: `sequence`
- Read API: `GET /v1/gui/events`

Examples:

- `cluster.bootstrap`
- `cluster.node.joined`
- `cluster.node.revoked`
- `cluster.node.endpoints.updated`
- `cluster.failover.promoted`
- `rbac.admin.user.upsert`
- `gui.cluster.snapshot.read`

## How They Relate

When the leader performs a state mutation:

1. It updates state/user-state.
2. It emits a control-plane sync event for replication.
3. It appends an audit event to the user event log.

This separation keeps replication strict and machine-friendly while preserving a readable cluster timeline.
