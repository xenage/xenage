import { useEffect, useMemo, useRef, useState } from "react";
import type { ManifestTable } from "../../types/controlPlane";
import type { EventLogEntry } from "../../types/guiConnection";
import { Icon } from "../../components/Icon";
import { SchemaDataTable } from "../table/SchemaDataTable";
import { rowsToSchemaTableRows, schemaColumnsToTableColumns, sortSchemaRows } from "../table/schemaAdapter";

export function EventTable({
  hasMore,
  loadingMore,
  onLoadMore,
  rows,
  searchTerm,
  tableSchema,
}: {
  hasMore: boolean;
  loadingMore: boolean;
  onLoadMore: () => void;
  rows: EventLogEntry[];
  searchTerm: string;
  tableSchema: ManifestTable;
}) {
  const [activeEventId, setActiveEventId] = useState<string | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [detailWidth, setDetailWidth] = useState(420);
  const detailResizeRef = useRef<{ startX: number; startWidth: number } | null>(null);

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

  const activeEvent = useMemo(
    () => orderedRows.find((row) => String(row.sequence) === activeEventId) ?? null,
    [activeEventId, orderedRows],
  );

  useEffect(() => {
    const onMove = (event: MouseEvent) => {
      const activeResize = detailResizeRef.current;
      if (!activeResize) {
        return;
      }
      const next = Math.max(260, Math.min(900, activeResize.startWidth + activeResize.startX - event.clientX));
      setDetailWidth(next);
    };

    const onUp = () => {
      detailResizeRef.current = null;
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
    if (!activeEventId) {
      return;
    }
    if (!orderedRows.some((row) => String(row.sequence) === activeEventId)) {
      setActiveEventId(null);
      setDetailOpen(false);
    }
  }, [activeEventId, orderedRows]);

  return (
    <div
      className={`event-layout ${detailOpen ? "event-layout--detail-open" : ""}`}
      style={{ ["--event-detail-width" as string]: `${detailWidth}px` }}
    >
      <div className="event-layout__table">
        <SchemaDataTable
          activeRowKey={activeEventId}
          className="schema-table--event"
          columns={columns}
          filterQuery={searchTerm}
          onReachEnd={() => {
            if (hasMore && !loadingMore) {
              onLoadMore();
            }
          }}
          onRowClick={(row) => {
            setActiveEventId(row.key);
            setDetailOpen(true);
          }}
          rows={tableRows}
          selectable={false}
        />
        {hasMore ? <div className="event-layout__pager">{loadingMore ? "Loading..." : "Scroll to load more..."}</div> : null}
      </div>
      {detailOpen ? (
        <aside className="event-layout__detail">
          <div
            className="event-layout__resize"
            onMouseDown={(event) => {
              event.preventDefault();
              detailResizeRef.current = { startX: event.clientX, startWidth: detailWidth };
              document.body.style.userSelect = "none";
            }}
            role="separator"
          />
          <div className="event-layout__title">
            <span>{activeEvent ? `Event #${activeEvent.sequence}` : "Event details"}</span>
            <button
              className="event-layout__close"
              onClick={() => setDetailOpen(false)}
              type="button"
            >
              <Icon name="close" />
            </button>
          </div>
          {activeEvent ? (
            <pre className="event-layout__json">{JSON.stringify(activeEvent, null, 2)}</pre>
          ) : (
            <div className="event-layout__empty">Select an event row to inspect full details.</div>
          )}
        </aside>
      ) : null}
    </div>
  );
}
