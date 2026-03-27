import { useMemo } from "react";
import type { ManifestTable } from "../../types/controlPlane";
import type { GuiClusterSnapshot } from "../../types/guiConnection";
import { SchemaDataTable } from "../table/SchemaDataTable";
import { rowsToSchemaTableRows, schemaColumnsToTableColumns, sortSchemaRows } from "../table/schemaAdapter";

type GroupConfigRow = GuiClusterSnapshot["group_config"][number];

export function GroupConfigTable({
  rows,
  searchTerm,
  tableSchema,
}: {
  rows: GroupConfigRow[];
  searchTerm: string;
  tableSchema: ManifestTable;
}) {
  const orderedRows = useMemo(
    () => sortSchemaRows(rows, tableSchema.defaultSort),
    [rows, tableSchema.defaultSort],
  );

  const tableRows = useMemo(
    () => rowsToSchemaTableRows(tableSchema, orderedRows),
    [orderedRows, tableSchema],
  );

  const columns = useMemo(
    () => schemaColumnsToTableColumns(tableSchema.columns),
    [tableSchema.columns],
  );

  return (
    <SchemaDataTable
      columns={columns}
      filterQuery={searchTerm}
      rows={tableRows}
    />
  );
}
