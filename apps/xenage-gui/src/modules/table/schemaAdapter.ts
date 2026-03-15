import type { ManifestSort, ManifestTable, ManifestTableColumn } from "../../types/controlPlane";
import type { IdeTableColumn, IdeTableRow } from "./SchemaDataTable";

type JsonRecord = Record<string, unknown>;

function valueAtPath(record: unknown, path: string): unknown {
  const segments = path.split(".").filter(Boolean);
  let current: unknown = record;
  for (const segment of segments) {
    if (!current || typeof current !== "object") {
      return undefined;
    }
    current = (current as JsonRecord)[segment];
  }
  return current;
}

function stringifyCell(value: unknown): string {
  if (value === null || value === undefined) {
    return "-";
  }
  if (typeof value === "string") {
    return value.length > 0 ? value : "-";
  }
  if (typeof value === "number" || typeof value === "boolean" || typeof value === "bigint") {
    return String(value);
  }
  if (Array.isArray(value)) {
    if (value.length === 0) {
      return "-";
    }
    return value.map((item) => stringifyCell(item)).join(", ");
  }
  if (typeof value === "object") {
    const objectValue = value as JsonRecord;
    if (Object.keys(objectValue).length === 0) {
      return "{}";
    }
    return JSON.stringify(value);
  }
  return String(value);
}

export function schemaColumnsToTableColumns(columns: ManifestTableColumn[]): IdeTableColumn[] {
  return columns
    .filter((column) => !column.displayOnly)
    .map((column) => ({
      key: column.key,
      label: column.label,
      width: column.width,
      minWidth: column.minWidth,
    }));
}

export function sortSchemaRows<T extends object>(rows: T[], sort: ManifestSort): T[] {
  const direction = sort.direction === "desc" ? -1 : 1;
  const getComparable = (value: unknown): string | number => {
    if (typeof value === "number") {
      return value;
    }
    if (typeof value === "boolean") {
      return value ? 1 : 0;
    }
    if (typeof value === "string") {
      const numeric = Number(value);
      if (!Number.isNaN(numeric) && value.trim().length > 0) {
        return numeric;
      }
      return value.toLowerCase();
    }
    return stringifyCell(value).toLowerCase();
  };

  return [...rows].sort((left, right) => {
    const leftValue = getComparable(valueAtPath(left, sort.field));
    const rightValue = getComparable(valueAtPath(right, sort.field));
    if (typeof leftValue === "number" && typeof rightValue === "number") {
      return (leftValue - rightValue) * direction;
    }
    return String(leftValue).localeCompare(String(rightValue)) * direction;
  });
}

export function rowsToSchemaTableRows<T extends object>(tableSchema: ManifestTable, rows: T[]): IdeTableRow[] {
  return rows.map((row, index) => {
    const keyValue = valueAtPath(row, tableSchema.rowKey);
    const key = keyValue !== null && keyValue !== undefined && String(keyValue) !== ""
      ? String(keyValue)
      : `${tableSchema.kind.toLowerCase()}-${index}`;
    const values = tableSchema.columns.reduce<Record<string, string>>((acc, column) => {
      const path = column.path || column.key;
      acc[column.key] = stringifyCell(valueAtPath(row, path));
      return acc;
    }, {});
    return {
      key,
      values,
      raw: row,
    };
  });
}
