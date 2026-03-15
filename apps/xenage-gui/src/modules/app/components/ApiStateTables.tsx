type ApiUnavailableTableProps = {
  kind: string;
};

export function ApiUnavailableTable({ kind }: ApiUnavailableTableProps) {
  return (
    <div className="schema-table schema-table--live">
      <div className="schema-table__empty">
        API table is available only for Node, Event, and Group Config. No schema fallback for {kind}.
      </div>
    </div>
  );
}

type ApiFetchStateTableProps = {
  error: string | null;
  kind: string;
  loading: boolean;
  onRetry: () => void;
};

export function ApiFetchStateTable({
  error,
  kind,
  loading,
  onRetry,
}: ApiFetchStateTableProps) {
  if (loading) {
    return (
      <div className="schema-table schema-table--live">
        <div className="schema-table__empty">Loading {kind} from API...</div>
      </div>
    );
  }

  return (
    <div className="schema-table schema-table--live">
      <div className="schema-table__empty">
        {error ? `API error: ${error}` : `No API data returned for ${kind}.`}
      </div>
      <div className="schema-table__empty">
        <button className="cluster-editor__button" onClick={onRetry} type="button">Retry API</button>
      </div>
    </div>
  );
}
