type SetupGuideViewProps = {
  connectingGui: boolean;
  guiConnectionStatus: string | null;
  guiConnectionYaml: string;
  onConnect: () => Promise<void>;
  onYamlChange: (value: string) => void;
};

export function SetupGuideView({
  connectingGui,
  guiConnectionStatus,
  guiConnectionYaml,
  onConnect,
  onYamlChange,
}: SetupGuideViewProps) {
  return (
    <section className="settings-view">
      <div className="editor-header">
        <div>
          <div className="editor-header__title">Setup Guide</div>
          <div className="editor-header__subtitle">Paste GUI connection YAML and connect to the docker-compose control-plane.</div>
        </div>
        <div className="editor-header__pills">
          <span className="pill">onboarding</span>
          <span className="pill pill--muted">admin</span>
        </div>
      </div>

      <section className="connection-panel">
        <div className="connection-panel__header">
          <h3>Cluster Connection (YAML)</h3>
          <button className="settings-button" disabled={connectingGui} onClick={() => void onConnect()} type="button">
            {connectingGui ? "Connecting..." : "Connect"}
          </button>
        </div>
        <textarea
          className="connection-panel__editor"
          onChange={(event) => onYamlChange(event.target.value)}
          spellCheck={false}
          value={guiConnectionYaml}
        />
        {guiConnectionStatus ? <div className="connection-panel__status">{guiConnectionStatus}</div> : null}
      </section>
    </section>
  );
}
