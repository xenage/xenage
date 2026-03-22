import { useCallback, useEffect, useMemo, useState } from "react";
import type { ManifestTable } from "../../types/controlPlane";
import { ClusterConnectionService } from "../../services/clusterConnection";
import type { RbacYamlResourceEntry } from "../../services/clusterConnection";
import { logger } from "../../services/logger";
import type { IdeTableRow } from "../table/SchemaDataTable";
import { SchemaDataTable } from "../table/SchemaDataTable";
import { rowsToSchemaTableRows, schemaColumnsToTableColumns, sortSchemaRows } from "../table/schemaAdapter";

type RbacYamlEditorProps = {
  activeKind: string;
  onOpenEditorTab: (payload: {
    clusterId: string;
    clusterYaml: string;
    kind: string;
    resourceName: string | null;
    yaml: string;
  }) => void;
  resolvedClusterId: string;
  searchTerm: string;
  tableSchema: ManifestTable;
};

type ResourceTableRow = {
  name: string;
  engine?: string;
  enabled?: boolean;
  public_key?: string;
  rule_count?: number;
  role?: string;
  subject_count?: number;
};

function defaultYamlForKind(kind: string): string {
  if (kind === "User") {
    return [
      "apiVersion: xenage.dev/v1",
      "kind: ServiceAccount",
      "metadata:",
      "  name: new-user",
      "spec:",
      "  engine: gui/v1",
      "  publicKey: <base64-public-key>",
      "  enabled: true",
      "",
    ].join("\n");
  }
  if (kind === "Role") {
    return [
      "apiVersion: rbac.authorization.xenage.dev/v1",
      "kind: Role",
      "metadata:",
      "  name: new-role",
      "rules:",
      "  - apiGroups: [\"\"]",
      "    namespaces: [\"cluster\"]",
      "    resources: [\"nodes\"]",
      "    verbs: [\"get\", \"list\"]",
      "",
    ].join("\n");
  }
  return [
    "apiVersion: rbac.authorization.xenage.dev/v1",
    "kind: RoleBinding",
    "metadata:",
    "  name: new-rolebinding",
    "subjects:",
    "  - kind: ServiceAccount",
    "    name: new-user",
    "roleRef:",
    "  apiGroup: rbac.authorization.xenage.dev",
    "  kind: Role",
    "  name: new-role",
    "",
  ].join("\n");
}

function isRbacKind(kind: string): boolean {
  return kind === "User" || kind === "Role" || kind === "RoleBinding";
}

function toRecord(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return {};
  }
  return value as Record<string, unknown>;
}

function toArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function toUserRow(entry: RbacYamlResourceEntry): ResourceTableRow {
  const manifest = toRecord(entry.manifest);
  const metadata = toRecord(manifest.metadata);
  const spec = toRecord(manifest.spec);
  return {
    name: String(metadata.name ?? entry.name),
    engine: String(spec.engine ?? ""),
    enabled: Boolean(spec.enabled ?? false),
    public_key: String(spec.publicKey ?? ""),
  };
}

function toRoleRow(entry: RbacYamlResourceEntry): ResourceTableRow {
  const manifest = toRecord(entry.manifest);
  const metadata = toRecord(manifest.metadata);
  const rules = toArray(manifest.rules);
  return {
    name: String(metadata.name ?? entry.name),
    rule_count: rules.length,
  };
}

function toRoleBindingRow(entry: RbacYamlResourceEntry): ResourceTableRow {
  const manifest = toRecord(entry.manifest);
  const metadata = toRecord(manifest.metadata);
  const roleRef = toRecord(manifest.roleRef);
  const subjects = toArray(manifest.subjects);
  return {
    name: String(metadata.name ?? entry.name),
    role: String(roleRef.name ?? ""),
    subject_count: subjects.length,
  };
}

function toTableRows(activeKind: string, entries: RbacYamlResourceEntry[]): ResourceTableRow[] {
  if (activeKind === "User") {
    return entries.map(toUserRow);
  }
  if (activeKind === "Role") {
    return entries.map(toRoleRow);
  }
  return entries.map(toRoleBindingRow);
}

export function RbacYamlEditor({
  activeKind,
  onOpenEditorTab,
  resolvedClusterId,
  searchTerm,
  tableSchema,
}: RbacYamlEditorProps) {
  const [clusterYaml, setClusterYaml] = useState("");
  const [resources, setResources] = useState<RbacYamlResourceEntry[]>([]);
  const [activeRowKey, setActiveRowKey] = useState<string | null>(null);
  const [selectedRows, setSelectedRows] = useState<IdeTableRow[]>([]);
  const [selectionResetToken, setSelectionResetToken] = useState(0);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState<string | null>(null);

  const templateYaml = useMemo(() => defaultYamlForKind(activeKind), [activeKind]);

  const loadResources = useCallback(async () => {
    if (!isRbacKind(activeKind) || !resolvedClusterId) {
      setResources([]);
      setActiveRowKey(null);
      return;
    }
    setLoading(true);
    setStatus(null);
    try {
      const connections = await ClusterConnectionService.listConnectionYamls();
      const connection = connections.find((item) => item.id === resolvedClusterId);
      if (!connection) {
        setStatus("Cluster connection is not available.");
        setResources([]);
        setActiveRowKey(null);
        setClusterYaml("");
        return;
      }
      setClusterYaml(connection.yaml);
      const nextResources = await ClusterConnectionService.listRbacYamlResources(connection.yaml, activeKind);
      setResources(nextResources);
      if (nextResources.length === 0) {
        setActiveRowKey(null);
        setStatus(`No ${activeKind} resources yet.`);
      } else {
        setActiveRowKey(nextResources[0].name || null);
      }
      setSelectionResetToken((current) => current + 1);
    } catch (error) {
      logger.error("Failed to load RBAC yaml resources", { activeKind, resolvedClusterId, error });
      setResources([]);
      setActiveRowKey(null);
      setStatus(error instanceof Error ? error.message : "Failed to load RBAC resources.");
    } finally {
      setLoading(false);
    }
  }, [activeKind, resolvedClusterId]);

  useEffect(() => {
    void loadResources();
  }, [activeKind, loadResources]);

  const resourceRows = useMemo(
    () => sortSchemaRows(toTableRows(activeKind, resources), tableSchema.defaultSort),
    [activeKind, resources, tableSchema.defaultSort],
  );
  const tableRows = useMemo(
    () => rowsToSchemaTableRows(tableSchema, resourceRows),
    [resourceRows, tableSchema],
  );
  const columns = useMemo(
    () => schemaColumnsToTableColumns(tableSchema.columns),
    [tableSchema.columns],
  );

  const handleOpenExisting = useCallback((row: IdeTableRow) => {
    const selected = resources.find((item) => item.name === row.key);
    if (!selected) {
      return;
    }
    setActiveRowKey(selected.name);
    if (!clusterYaml.trim()) {
      setStatus("Cluster connection is not available.");
      return;
    }
    onOpenEditorTab({
      clusterId: resolvedClusterId,
      clusterYaml,
      kind: activeKind,
      resourceName: selected.name,
      yaml: selected.yaml,
    });
    setStatus(null);
  }, [activeKind, clusterYaml, onOpenEditorTab, resolvedClusterId, resources]);

  const handleCreate = useCallback(() => {
    if (!clusterYaml.trim()) {
      setStatus("Cluster connection is not available.");
      return;
    }
    onOpenEditorTab({
      clusterId: resolvedClusterId,
      clusterYaml,
      kind: activeKind,
      resourceName: null,
      yaml: templateYaml,
    });
    setStatus(null);
  }, [activeKind, clusterYaml, onOpenEditorTab, resolvedClusterId, templateYaml]);

  const handleDeleteSelected = useCallback(async () => {
    if (!clusterYaml.trim()) {
      setStatus("Cluster connection is not available.");
      return;
    }
    if (selectedRows.length === 0) {
      setStatus("Select at least one resource to delete.");
      return;
    }
    setSaving(true);
    setStatus(null);
    try {
      for (const selectedRow of selectedRows) {
        const target = resources.find((item) => item.name === selectedRow.key);
        if (!target) {
          continue;
        }
        await ClusterConnectionService.applyRbacYamlResource(clusterYaml, target.yaml, true);
      }
      setStatus(`Deleted ${selectedRows.length} resource(s).`);
      await loadResources();
    } catch (error) {
      logger.error("Failed to delete selected RBAC resources", { activeKind, error });
      setStatus(error instanceof Error ? error.message : "Failed to delete selected resources.");
    } finally {
      setSaving(false);
    }
  }, [activeKind, clusterYaml, loadResources, resources, selectedRows]);

  if (!isRbacKind(activeKind)) {
    return (
      <div className="schema-table schema-table--live">
        <div className="schema-table__empty">Unsupported RBAC kind: {activeKind}</div>
      </div>
    );
  }

  return (
    <div className="rbac-workspace">
      <div className="rbac-workspace__table">
        <SchemaDataTable
          activeRowKey={activeRowKey}
          columns={columns}
          filterQuery={searchTerm}
          onRowClick={handleOpenExisting}
          onSelectionChange={setSelectedRows}
          rows={tableRows}
          selectionResetToken={selectionResetToken}
        />
        <div className="rbac-floating-actions">
          {selectedRows.length > 0 ? (
            <button
              aria-label="Delete selected RBAC resources"
              className="rbac-fab rbac-fab--danger"
              disabled={saving}
              onClick={() => void handleDeleteSelected()}
              type="button"
            >
              -
            </button>
          ) : null}
          <button
            aria-label="Create RBAC resource"
            className="rbac-fab"
            onClick={handleCreate}
            type="button"
          >
            +
          </button>
        </div>
        {loading ? <div className="event-layout__pager">Loading {activeKind}...</div> : null}
        {status ? <div className="event-layout__pager">{status}</div> : null}
      </div>
    </div>
  );
}
