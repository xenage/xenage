# RBAC Guide

This guide explains how to create users and permissions in Xenage RBAC using YAML manifests.

## Resource Types

Xenage RBAC uses three resource types:

1. `ServiceAccount` (`apiVersion: xenage.dev/v1`) for user identity.
2. `Role` (`apiVersion: rbac.authorization.xenage.dev/v1`) for permissions.
3. `RoleBinding` (`apiVersion: rbac.authorization.xenage.dev/v1`) to bind a role to a service account.

## User Identity Format

Service accounts are cluster-wide and authenticate by `metadata.name`.

Example: service account `agent-runner` authenticates as `agent-runner`.

## Minimal Flow (Create User + Permissions)

1. Create `ServiceAccount` with `spec.publicKey`.
2. Create `Role` with rules (`resources`, `verbs`).
3. Create `RoleBinding` that references the role and subject.
4. Verify with `xenage can-i`.

## YAML Example (Single Multi-Doc File)

Use [agent-runner.yaml](examples/rbac/agent-runner.yaml).

Apply it:

```bash
xenage --config ~/.xenage/config.yaml apply -f docs/examples/rbac/agent-runner.yaml
```

Verify access:

```bash
xenage --config ~/.xenage/config.yaml can-i get nodes --namespace ai
xenage --config ~/.xenage/config.yaml can-i list nodes --namespace ai
xenage --config ~/.xenage/config.yaml can-i delete nodes --namespace ai
```

## Read-Only Viewer Example

Use [viewer-readonly.yaml](examples/rbac/viewer-readonly.yaml).

This example grants read-only access (`get`, `list`) to `nodes` and `events` in the `cluster` scope.

## Inspect Applied RBAC Objects

```bash
xenage --config ~/.xenage/config.yaml get serviceaccounts -o yaml
xenage --config ~/.xenage/config.yaml get roles -o yaml
xenage --config ~/.xenage/config.yaml get rolebindings -o yaml
```

## YAML Field Reference

### `ServiceAccount`

```yaml
apiVersion: xenage.dev/v1
kind: ServiceAccount
metadata:
  name: agent-runner
spec:
  engine: runtime/v1
  publicKey: BASE64_PUBLIC_KEY
  enabled: true
```

### `Role`

```yaml
apiVersion: rbac.authorization.xenage.dev/v1
kind: Role
metadata:
  name: agent-runner-role
rules:
  - apiGroups: [""]
    namespaces: ["ai"]
    resources: ["nodes"]
    verbs: ["get", "list"]
```

### `RoleBinding`

```yaml
apiVersion: rbac.authorization.xenage.dev/v1
kind: RoleBinding
metadata:
  name: agent-runner-binding
subjects:
  - kind: ServiceAccount
    name: agent-runner
roleRef:
  apiGroup: rbac.authorization.xenage.dev
  kind: Role
  name: agent-runner-role
```

## Important Constraints

- `RoleBinding.roleRef.name` must reference an existing role (cluster-wide).
- Service account `publicKey` is immutable for the same `metadata.name`.
- Scope is configured in `Role.rules[].namespaces` (for example: `["ai"]`, `["prod"]`, `["cluster"]`, `["*"]`).
- `POST /v1/resources/apply` and resource list/read flows are protected by signed requests and RBAC checks.
