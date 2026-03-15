import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { OverlayScrollbarsComponent } from "overlayscrollbars-react";
import type { OverlayScrollbarsComponentRef } from "overlayscrollbars-react";
import type { PartialOptions } from "overlayscrollbars";

export type IdeTableColumn = {
  key: string;
  label: string;
  width: number;
  minWidth?: number;
};

export type IdeTableRow = {
  key: string;
  values: Record<string, string>;
  raw?: unknown;
};

type SortDirection = "asc" | "desc";

function normalizeNumber(value: string): number | null {
  const compact = value.replace(/,/g, "");
  if (!/^-?\d+(?:\.\d+)?$/.test(compact)) {
    return null;
  }
  const numeric = Number(compact);
  return Number.isFinite(numeric) ? numeric : null;
}

function normalizeDate(value: string): number | null {
  const looksLikeDate = value.includes("-") || value.includes("/") || value.includes(":") || value.includes("T");
  if (!looksLikeDate) {
    return null;
  }
  const parsed = Date.parse(value);
  return Number.isNaN(parsed) ? null : parsed;
}

function compareCellValues(left: string, right: string, collator: Intl.Collator): number {
  const leftTrimmed = left.trim();
  const rightTrimmed = right.trim();
  const leftEmpty = leftTrimmed.length === 0 || leftTrimmed === "-";
  const rightEmpty = rightTrimmed.length === 0 || rightTrimmed === "-";
  if (leftEmpty && rightEmpty) {
    return 0;
  }
  if (leftEmpty) {
    return 1;
  }
  if (rightEmpty) {
    return -1;
  }

  const leftNumber = normalizeNumber(leftTrimmed);
  const rightNumber = normalizeNumber(rightTrimmed);
  if (leftNumber !== null && rightNumber !== null) {
    return leftNumber - rightNumber;
  }

  const leftDate = normalizeDate(leftTrimmed);
  const rightDate = normalizeDate(rightTrimmed);
  if (leftDate !== null && rightDate !== null) {
    return leftDate - rightDate;
  }

  return collator.compare(leftTrimmed, rightTrimmed);
}

export function SchemaDataTable({
  activeRowKey,
  cellClassName,
  className,
  columns,
  emptyLabel = "No rows",
  filterQuery = "",
  onReachEnd,
  onRowClick,
  rows,
  selectable = true,
}: {
  activeRowKey?: string | null;
  cellClassName?: (row: IdeTableRow, columnKey: string) => string;
  className?: string;
  columns: IdeTableColumn[];
  emptyLabel?: string;
  filterQuery?: string;
  onReachEnd?: () => void;
  onRowClick?: (row: IdeTableRow) => void;
  rows: IdeTableRow[];
  selectable?: boolean;
}) {
  const tableScrollRef = useRef<OverlayScrollbarsComponentRef<"div"> | null>(null);
  const [columnWidths, setColumnWidths] = useState<Record<string, number>>(() =>
    columns.reduce<Record<string, number>>((acc, column) => {
      acc[column.key] = column.width;
      return acc;
    }, {}),
  );
  const [sortState, setSortState] = useState<{ key: string; direction: SortDirection } | null>(null);
  const [selectedRowKeys, setSelectedRowKeys] = useState<Record<string, boolean>>({});
  const selectionAnchorRowKeyRef = useRef<string | null>(null);
  const rowSelectionShiftPressedRef = useRef(false);
  const resizingRef = useRef<{ columnKey: string; minWidth: number; startX: number; startWidth: number } | null>(null);
  const textSortCollator = useMemo(
    () =>
      new Intl.Collator(undefined, {
        numeric: true,
        sensitivity: "base",
      }),
    [],
  );

  const normalizedFilter = filterQuery.trim().toLowerCase();
  const filteredRows = useMemo(
    () =>
      normalizedFilter
        ? rows.filter((row) =>
            Object.values(row.values).some((value) => value.toLowerCase().includes(normalizedFilter)),
          )
        : rows,
    [normalizedFilter, rows],
  );
  const visibleRows = useMemo(() => {
    if (!sortState) {
      return filteredRows;
    }
    const direction = sortState.direction === "asc" ? 1 : -1;
    return filteredRows
      .map((row, index) => ({ index, row }))
      .sort((left, right) => {
        const leftValue = left.row.values[sortState.key] ?? "-";
        const rightValue = right.row.values[sortState.key] ?? "-";
        const compared = compareCellValues(leftValue, rightValue, textSortCollator);
        if (compared === 0) {
          return left.index - right.index;
        }
        return compared * direction;
      })
      .map((item) => item.row);
  }, [filteredRows, sortState, textSortCollator]);

  useEffect(() => {
    setColumnWidths((current) => {
      let changed = false;
      const next: Record<string, number> = {};
      for (const column of columns) {
        const existingWidth = current[column.key];
        if (existingWidth === undefined) {
          next[column.key] = column.width;
          changed = true;
        } else {
          next[column.key] = existingWidth;
        }
      }
      if (Object.keys(current).length !== columns.length) {
        changed = true;
      }
      return changed ? next : current;
    });
  }, [columns]);

  useEffect(() => {
    const onMove = (event: MouseEvent) => {
      const activeResize = resizingRef.current;
      if (!activeResize) {
        return;
      }
      const nextWidth = Math.max(activeResize.minWidth, activeResize.startWidth + event.clientX - activeResize.startX);
      setColumnWidths((current) => ({
        ...current,
        [activeResize.columnKey]: nextWidth,
      }));
    };

    const onUp = () => {
      resizingRef.current = null;
      document.body.style.userSelect = "";
    };

    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, []);

  useEffect(() => {
    setSelectedRowKeys((current) => {
      const next: Record<string, boolean> = {};
      for (const row of rows) {
        if (current[row.key]) {
          next[row.key] = true;
        }
      }
      return next;
    });
    if (selectionAnchorRowKeyRef.current && !rows.some((row) => row.key === selectionAnchorRowKeyRef.current)) {
      selectionAnchorRowKeyRef.current = null;
    }
  }, [rows]);

  useEffect(() => {
    setSortState((current) => {
      if (!current) {
        return current;
      }
      return columns.some((column) => column.key === current.key) ? current : null;
    });
  }, [columns]);

  const updateRowSelection = useCallback((rowKey: string, checked: boolean, shiftPressed: boolean) => {
    const anchorRowKey = selectionAnchorRowKeyRef.current;
    setSelectedRowKeys((current) => {
      if (!shiftPressed || !anchorRowKey) {
        return {
          ...current,
          [rowKey]: checked,
        };
      }

      const anchorIndex = visibleRows.findIndex((row) => row.key === anchorRowKey);
      const targetIndex = visibleRows.findIndex((row) => row.key === rowKey);
      if (anchorIndex === -1 || targetIndex === -1) {
        return {
          ...current,
          [rowKey]: checked,
        };
      }

      const rangeStart = Math.min(anchorIndex, targetIndex);
      const rangeEnd = Math.max(anchorIndex, targetIndex);
      const next = { ...current };
      for (let index = rangeStart; index <= rangeEnd; index += 1) {
        const rangeRow = visibleRows[index];
        if (rangeRow) {
          next[rangeRow.key] = checked;
        }
      }
      return next;
    });
    selectionAnchorRowKeyRef.current = rowKey;
  }, [visibleRows]);

  const selectedVisibleCount = visibleRows.reduce((count, row) => count + (selectedRowKeys[row.key] ? 1 : 0), 0);
  const allVisibleSelected = visibleRows.length > 0 && selectedVisibleCount === visibleRows.length;
  const templateColumns = `${selectable ? "36px " : ""}${columns.map((column) => `${columnWidths[column.key] ?? column.width}px`).join(" ")}`;

  const tableScrollbarOptions = useMemo<PartialOptions>(
    () => ({
      overflow: {
        x: "scroll",
        y: "scroll",
      },
      scrollbars: {
        autoHide: "never",
        clickScroll: true,
        dragScroll: true,
        theme: "os-theme-xenage os-theme-xenage-table",
      },
    }),
    [],
  );

  const isNearBottom = useCallback((element: HTMLElement) => (
    element.scrollTop + element.clientHeight >= element.scrollHeight - 32
  ), []);

  useEffect(() => {
    if (!onReachEnd) {
      return;
    }
    let frameId = 0;
    let detach: (() => void) | null = null;

    const connect = () => {
      const scrollElement = tableScrollRef.current?.osInstance()?.elements().scrollOffsetElement;
      if (!scrollElement) {
        frameId = window.requestAnimationFrame(connect);
        return;
      }

      const handleScroll = () => {
        if (isNearBottom(scrollElement)) {
          onReachEnd();
        }
      };

      if (scrollElement.scrollHeight <= scrollElement.clientHeight + 2) {
        onReachEnd();
      } else {
        handleScroll();
      }

      scrollElement.addEventListener("scroll", handleScroll, { passive: true });
      detach = () => {
        scrollElement.removeEventListener("scroll", handleScroll);
      };
    };

    connect();

    return () => {
      if (frameId) {
        window.cancelAnimationFrame(frameId);
      }
      detach?.();
    };
  }, [isNearBottom, onReachEnd, visibleRows.length]);

  return (
    <OverlayScrollbarsComponent
      className={`schema-table schema-table--live scroll-host scroll-host--table ${className ?? ""}`.trim()}
      options={tableScrollbarOptions}
      ref={tableScrollRef}
    >
      <div className="schema-table__inner">
        <div className="schema-table__head" style={{ gridTemplateColumns: templateColumns }}>
          {selectable ? (
            <label className="schema-table__cell schema-table__cell--head schema-table__cell--checkbox">
              <input
                checked={allVisibleSelected}
                onChange={() => {
                  setSelectedRowKeys((current) => {
                    const next = { ...current };
                    for (const row of visibleRows) {
                      next[row.key] = !allVisibleSelected;
                    }
                    return next;
                  });
                }}
                type="checkbox"
              />
            </label>
          ) : null}
          {columns.map((column) => (
            <div
              aria-sort={
                sortState?.key === column.key
                  ? sortState.direction === "asc"
                    ? "ascending"
                    : "descending"
                  : "none"
              }
              className="schema-table__cell schema-table__cell--head"
              key={column.key}
            >
              <button
                className="schema-table__sort-button"
                onClick={() => {
                  setSortState((current) => {
                    if (!current || current.key !== column.key) {
                      return { key: column.key, direction: "asc" };
                    }
                    if (current.direction === "asc") {
                      return { key: column.key, direction: "desc" };
                    }
                    return null;
                  });
                }}
                type="button"
              >
                <span className="schema-table__sort-label">{column.label}</span>
                <span
                  aria-hidden
                  className={`schema-table__sort-indicator ${sortState?.key === column.key ? "schema-table__sort-indicator--active" : ""}`}
                >
                  {sortState?.key === column.key ? (sortState.direction === "asc" ? "▲" : "▼") : "↕"}
                </span>
              </button>
              <button
                aria-label={`Resize ${column.label} column`}
                className="schema-table__resizer"
                onMouseDown={(event) => {
                  event.preventDefault();
                  resizingRef.current = {
                    columnKey: column.key,
                    minWidth: column.minWidth ?? 80,
                    startWidth: columnWidths[column.key] ?? column.width,
                    startX: event.clientX,
                  };
                  document.body.style.userSelect = "none";
                }}
                type="button"
              />
            </div>
          ))}
        </div>
        {visibleRows.length === 0 ? (
          <div className="schema-table__empty">{emptyLabel}</div>
        ) : (
          visibleRows.map((row) => (
            <div
              className={`schema-table__row ${activeRowKey === row.key ? "schema-table__row--active" : ""}`}
              key={row.key}
              onClick={() => onRowClick?.(row)}
              style={{ gridTemplateColumns: templateColumns }}
            >
              {selectable ? (
                <label className="schema-table__cell schema-table__cell--checkbox">
                  <input
                    checked={Boolean(selectedRowKeys[row.key])}
                    onChange={(event) => {
                      const checked = event.target.checked;
                      const shiftPressed = rowSelectionShiftPressedRef.current;
                      rowSelectionShiftPressedRef.current = false;
                      updateRowSelection(row.key, checked, shiftPressed);
                    }}
                    onKeyDown={(event) => {
                      if (event.key === " " || event.key === "Enter") {
                        rowSelectionShiftPressedRef.current = event.shiftKey;
                      }
                    }}
                    onClick={(event) => {
                      rowSelectionShiftPressedRef.current = event.shiftKey;
                      event.stopPropagation();
                    }}
                    onMouseDown={(event) => {
                      rowSelectionShiftPressedRef.current = event.shiftKey;
                    }}
                    type="checkbox"
                  />
                </label>
              ) : null}
              {columns.map((column) => (
                <span
                  className={`schema-table__cell ${cellClassName?.(row, column.key) ?? ""}`}
                  key={column.key}
                >
                  {row.values[column.key] ?? "-"}
                </span>
              ))}
            </div>
          ))
        )}
      </div>
    </OverlayScrollbarsComponent>
  );
}
