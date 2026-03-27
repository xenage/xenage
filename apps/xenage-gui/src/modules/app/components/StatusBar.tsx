type StatusBarProps = {
  activeClusterUserId: string | null;
  clockTime: string;
  hasDataFetchError: boolean;
  isDataFetching: boolean;
};

export function StatusBar({
  activeClusterUserId,
  clockTime,
  hasDataFetchError,
  isDataFetching,
}: StatusBarProps) {
  const statusLabel = isDataFetching ? "fetch" : hasDataFetchError ? "error" : "ready";
  const statusClassName = isDataFetching
    ? "statusbar__dot--fetching"
    : hasDataFetchError
      ? "statusbar__dot--error"
      : "statusbar__dot--ready";

  return (
    <footer className="statusbar" role="status">
      <div className="statusbar__section">
        <span className={`statusbar__dot ${statusClassName}`} />
        <span className="statusbar__label">{statusLabel}</span>
        {activeClusterUserId ? <span className="statusbar__user">{activeClusterUserId}</span> : null}
      </div>
      <div className="statusbar__section statusbar__section--clock">
        <span className="statusbar__label">time</span>
        <span className="statusbar__time">{clockTime}</span>
      </div>
    </footer>
  );
}
