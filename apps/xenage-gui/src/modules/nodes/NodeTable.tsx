import { useMemo } from "react";
import type { ManifestTable } from "../../types/controlPlane";
import type { GuiClusterSnapshot } from "../../types/guiConnection";
import { formatTimeAgo } from "../app/utils";
import { SchemaDataTable } from "../table/SchemaDataTable";
import { rowsToSchemaTableRows, schemaColumnsToTableColumns, sortSchemaRows } from "../table/schemaAdapter";

type NodeRow = GuiClusterSnapshot["nodes"][number];

function statusClassName(statusValue: string): string {
  const lowered = statusValue.toLowerCase();
  if (lowered.includes("unavailable") || lowered.includes("not-ready") || lowered.includes("broken")) {
    return "schema-table__cell--status-bad";
  }
  if (lowered.includes("leader")) {
    return "schema-table__cell--status-leader";
  }
  if (
    lowered.includes("ready")
    || lowered.includes("synced")
    || lowered.includes("connected")
    || lowered.includes("available")
    || lowered.includes("leader")
  ) {
    return "schema-table__cell--status-good";
  }
  return "schema-table__cell--status-muted";
}

export function NodeTable({
  rows,
  searchTerm,
  tableSchema,
}: {
  rows: NodeRow[];
  searchTerm: string;
  tableSchema: ManifestTable;
}) {
  const orderedRows = useMemo(
    () => sortSchemaRows(rows, tableSchema.defaultSort),
    [rows, tableSchema.defaultSort],
  );

  const displayRows = useMemo(
    () =>
      orderedRows.map((row) => {
        const age = formatTimeAgo(row.age ?? "");
        const lastPollAt = formatTimeAgo(row.last_poll_at ?? "");
        return {
          ...row,
          age: age === "-" ? (row.age?.trim() || "-") : age,
          last_poll_at: lastPollAt === "-" ? (row.last_poll_at?.trim() || "-") : lastPollAt,
        };
      }),
    [orderedRows],
  );

  const tableRows = useMemo(
    () => rowsToSchemaTableRows(tableSchema, displayRows),
    [displayRows, tableSchema],
  );

  const columns = useMemo(
    () => schemaColumnsToTableColumns(tableSchema.columns),
    [tableSchema.columns],
  );

  return (
    <SchemaDataTable
      cellClassName={(row, columnKey) =>
        columnKey === "status" ? statusClassName(row.values.status ?? "") : ""
      }
      columns={columns}
      filterQuery={searchTerm}
      rows={tableRows}
    />
  );
}
