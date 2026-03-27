# Node Sync

This document explains how Xenage keeps control-plane and runtime nodes aligned.

## Control-Plane Event Sync

Follower control-plane nodes sync from the leader through `GET /v1/control-plane/events`.

High-level loop:

1. Follower sets local sync status to `syncing`.
2. Follower requests pages with `after_event_id`.
3. Follower applies each event strictly in sequence.
4. Follower repeats while `has_more=true`.
5. Follower marks status `synced` when complete.

### Ordering guarantees

- Events must be contiguous (`event_id` gap is rejected).
- Duplicate/old events are ignored (`event_id <= local_last`).
- If follower history is ahead of leader (`local_last > leader.last_event_id`), node is marked `broken`.

## Sync Status Model

`GroupNodeSyncStatus.status` values:

- `unknown`: no reliable status yet
- `syncing`: node is currently catching up
- `synced`: node reported fully aligned with leader
- `broken`: divergence or unrecoverable sync condition

The leader aggregates reported statuses into `GroupState.node_statuses` used by GUI snapshots.

## Failover-driven Sync

During failover checks, non-leader control-plane nodes:

1. Probe leader heartbeat endpoints.
2. Attempt event sync from leader/candidate URLs.
3. Promote to leader only when TTL is expired and candidate selection points to self.

Leader promotion creates a new state with incremented `leader_epoch` and appends a `group.leader_promoted` sync event.

## Runtime State Sync

Runtime nodes do not consume event pages. They periodically call:

- `GET /v1/state/current`

Then they replace local state only if incoming `GroupState.version` is newer.
Runtime nodes do not expose inbound endpoints; liveness is inferred from recent signed polls.

State pull order prefers:

1. Current leader endpoints
2. Other control-plane endpoints

This keeps runtime nodes converged without participating in control-plane event replication.
