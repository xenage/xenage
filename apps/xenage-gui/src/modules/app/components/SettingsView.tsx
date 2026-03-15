import type { LogLevel } from "../../../services/logger";
import type { StandaloneStatus } from "../../../services/standalone";
import type { UpdateChannel } from "../../../services/update";

type SettingsViewProps = {
  channel: UpdateChannel;
  checkingUpdates: boolean;
  logLevel: LogLevel;
  onChannelChange: (channel: UpdateChannel) => void;
  onCheckUpdates: () => Promise<void>;
  onForceUpdate: () => Promise<void>;
  onInstallStandaloneBundle: () => Promise<void>;
  onInstallStandaloneServices: () => Promise<void>;
  onInstallUpdate: () => Promise<void>;
  onLogLevelChange: (level: LogLevel) => void;
  onRefreshStandaloneStatus: () => Promise<StandaloneStatus | null>;
  onStartStandaloneServices: () => Promise<void>;
  onStopStandaloneServices: () => Promise<void>;
  onUpdateControlPlaneArgs: (value: string) => void;
  onUpdateRuntimeArgs: (value: string) => void;
  standaloneBusy: boolean;
  standaloneControlPlaneArgs: string;
  standaloneRuntimeArgs: string;
  standaloneStatus: StandaloneStatus | null;
  standaloneStatusMessage: string | null;
  updateStatus: string | null;
};

export function SettingsView({
  channel,
  checkingUpdates,
  logLevel,
  onChannelChange,
  onCheckUpdates,
  onForceUpdate,
  onInstallStandaloneBundle,
  onInstallStandaloneServices,
  onInstallUpdate,
  onLogLevelChange,
  onRefreshStandaloneStatus,
  onStartStandaloneServices,
  onStopStandaloneServices,
  onUpdateControlPlaneArgs,
  onUpdateRuntimeArgs,
  standaloneBusy,
  standaloneControlPlaneArgs,
  standaloneRuntimeArgs,
  standaloneStatus,
  standaloneStatusMessage,
  updateStatus,
}: SettingsViewProps) {
  return (
    <section className="settings-view">
      <div className="editor-header">
        <div>
          <div className="editor-header__title">Settings</div>
          <div className="editor-header__subtitle">Application diagnostics, update channel and runtime controls.</div>
        </div>
        <div className="editor-header__pills">
          <span className="pill">app</span>
          <span className="pill pill--muted">{logLevel}</span>
        </div>
      </div>

      <section className="settings-grid">
        <article className="panel settings-card">
          <div className="panel__header panel__header--stacked">
            <h3>Diagnostics</h3>
            <p>Choose how noisy the app should be in the developer console.</p>
          </div>

          <label className="settings-field">
            <span>Log level</span>
            <select value={logLevel} onChange={(event) => onLogLevelChange(event.target.value as LogLevel)}>
              <option value="debug">Debug</option>
              <option value="info">Info</option>
              <option value="warn">Warn</option>
              <option value="error">Error</option>
            </select>
          </label>

          <div className="settings-status">
            <strong>Console</strong>
            <span>Current level: {logLevel}</span>
          </div>
        </article>

        <article className="panel settings-card">
          <div className="panel__header panel__header--stacked">
            <h3>GitHub Updates</h3>
            <p>Check releases and install updates from the Tauri updater feed.</p>
          </div>

          <label className="settings-field">
            <span>Channel</span>
            <select value={channel} onChange={(event) => onChannelChange(event.target.value as UpdateChannel)}>
              <option value="main">Main</option>
              <option value="dev">Dev</option>
            </select>
          </label>

          <div className="settings-actions">
            <button className="settings-button" disabled={checkingUpdates} onClick={onCheckUpdates} type="button">
              {checkingUpdates ? "Checking..." : "Check version"}
            </button>
            <button className="settings-button" disabled={checkingUpdates} onClick={onInstallUpdate} type="button">
              Install update
            </button>
            {channel === "dev" ? (
              <button
                className="settings-button settings-button--muted"
                disabled={checkingUpdates}
                onClick={onForceUpdate}
                type="button"
              >
                Force dev update
              </button>
            ) : null}
          </div>

          <div className="settings-status">
            <strong>Status</strong>
            <span>{updateStatus ?? "No update action yet."}</span>
          </div>
        </article>

        <article className="panel settings-card settings-card--full">
          <div className="panel__header panel__header--stacked">
            <h3>Standalone Services</h3>
            <p>Install node binaries and run control-plane/runtime as OS-managed services.</p>
          </div>

          <div className="settings-actions">
            <button className="settings-button" disabled={standaloneBusy} onClick={onInstallStandaloneBundle} type="button">
              {standaloneBusy ? "Working..." : "Download binaries"}
            </button>
            <button className="settings-button" disabled={standaloneBusy} onClick={onInstallStandaloneServices} type="button">
              Install services
            </button>
            <button className="settings-button" disabled={standaloneBusy} onClick={onStartStandaloneServices} type="button">
              Start services
            </button>
            <button
              className="settings-button settings-button--muted"
              disabled={standaloneBusy}
              onClick={onStopStandaloneServices}
              type="button"
            >
              Stop services
            </button>
            <button
              className="settings-button settings-button--muted"
              disabled={standaloneBusy}
              onClick={() => void onRefreshStandaloneStatus()}
              type="button"
            >
              Refresh status
            </button>
          </div>

          <div className="settings-grid settings-grid--nested">
            <label className="settings-field">
              <span>Control Plane Args (one token per line)</span>
              <textarea
                className="settings-textarea"
                onChange={(event) => onUpdateControlPlaneArgs(event.target.value)}
                value={standaloneControlPlaneArgs}
              />
            </label>
            <label className="settings-field">
              <span>Runtime Args (one token per line)</span>
              <textarea
                className="settings-textarea"
                onChange={(event) => onUpdateRuntimeArgs(event.target.value)}
                value={standaloneRuntimeArgs}
              />
            </label>
          </div>

          <div className="settings-status">
            <strong>Standalone Bundle</strong>
            <span>Installed: {standaloneStatus?.installed ? "yes" : "no"}</span>
            <span>Version: {standaloneStatus?.version ?? "n/a"}</span>
            <span>Asset: {standaloneStatus?.asset_name ?? "n/a"}</span>
            <span>Location: {standaloneStatus?.install_dir ?? "n/a"}</span>
            <span>Control Plane Service: {standaloneStatus?.control_plane_service?.state ?? "unknown"}</span>
            <span>Runtime Service: {standaloneStatus?.runtime_service?.state ?? "unknown"}</span>
            <span>{standaloneStatusMessage ?? "No standalone action yet."}</span>
          </div>
        </article>
      </section>
    </section>
  );
}
