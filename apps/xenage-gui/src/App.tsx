import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { OverlayScrollbarsComponent } from "overlayscrollbars-react";
import type { OverlayScrollbarsComponentRef } from "overlayscrollbars-react";
import "overlayscrollbars/overlayscrollbars.css";
import manifest from "./generated/control-plane-release.json";
import "./App.css";
import { getLogLevel, logger, setLogLevel } from "./services/logger";
import { UpdateService } from "./services/update";
import type { LogLevel } from "./services/logger";
import type { UpdateChannel, UpdateLogEvent } from "./services/update";
import type { PartialOptions } from "overlayscrollbars";
import type {
  ControlPlaneManifest,
  ManifestField,
  ManifestResource,
  NavigationLeaf,
} from "./types/controlPlane";

const controlPlane = manifest as ControlPlaneManifest;
const SETTINGS_TAB_ID = "app:settings";
const SETTINGS_KIND = "Settings";

type ClusterEntry = {
  id: string;
  name: string;
  status: "connected" | "warning";
  accent: string;
};

type OpenTab = {
  id: string;
  kind: string;
  clusterId: string;
};

const clusters: ClusterEntry[] = [
  { id: "main-current", name: "MAIN_CURRENT", status: "connected", accent: "#22c55e" },
  { id: "remote-test", name: "REMOTE_TEST", status: "warning", accent: "#f59e0b" },
];

function formatLabel(value: string) {
  return value.replace(/([a-z0-9])([A-Z])/g, "$1 $2");
}

function prettyValue(value: unknown): string {
  if (typeof value === "boolean") {
    return value ? "true" : "false";
  }

  if (Array.isArray(value)) {
    return value.length === 0 ? "[]" : value.join(", ");
  }

  if (value && typeof value === "object") {
    return JSON.stringify(value, null, 2);
  }

  return String(value);
}

function getHighlights(resource: ManifestResource) {
  return Object.entries(resource.sample.status ?? {})
    .slice(0, 4)
    .map(([label, value]) => ({ label: formatLabel(label), value: prettyValue(value) }));
}

function getSectionPreview(
  resource: ManifestResource,
  section: "metadata" | "spec" | "status",
  fields: ManifestField[],
) {
  const data = resource.sample[section] ?? {};

  return fields.slice(0, 4).map((field) => ({
    name: field.name,
    type: `${field.type}${field.isArray ? "[]" : ""}`,
    value: field.name in data ? prettyValue(data[field.name]) : "n/a",
  }));
}

function App() {
  const tabStripRef = useRef<OverlayScrollbarsComponentRef<"div"> | null>(null);
  const [search, setSearch] = useState("");
  const [checkingUpdates, setCheckingUpdates] = useState(false);
  const [updateStatus, setUpdateStatus] = useState<string | null>(null);
  const [channel, setChannel] = useState<UpdateChannel>(UpdateService.getChannel());
  const [logLevel, setAppLogLevel] = useState<LogLevel>(getLogLevel());
  const [activeClusterId, setActiveClusterId] = useState(clusters[0].id);
  const [expandedClusters, setExpandedClusters] = useState<Record<string, boolean>>({
    "main-current": true,
    "remote-test": false,
  });
  const [openTabs, setOpenTabs] = useState<OpenTab[]>([
    { id: "main-current:Cluster", kind: "Cluster", clusterId: "main-current" },
  ]);
  const [activeTabId, setActiveTabId] = useState<string>("main-current:Cluster");

  const resourcesByKind = useMemo(
    () => new Map(controlPlane.resources.map((resource) => [resource.kind, resource])),
    [],
  );

  const itemsByCluster = useMemo(
    () =>
      clusters.reduce<Record<string, NavigationLeaf[]>>((acc, cluster) => {
        acc[cluster.id] = controlPlane.navigation.children;
        return acc;
      }, {}),
    [],
  );

  const visibleClusters = useMemo(() => {
    const term = search.trim().toLowerCase();
    return clusters.filter((cluster) => {
      const matchesCluster = cluster.name.toLowerCase().includes(term);
      const matchingItems = itemsByCluster[cluster.id].filter((item) => item.label.toLowerCase().includes(term));
      return !term || matchesCluster || matchingItems.length > 0;
    });
  }, [itemsByCluster, search]);

  const activeTab = openTabs.find((tab) => tab.id === activeTabId) ?? openTabs[0];
  const settingsTabActive = activeTab?.id === SETTINGS_TAB_ID;
  const activeKind = activeTab?.kind ?? "Cluster";
  const resolvedClusterId = activeTab?.clusterId ?? activeClusterId;
  const activeResource = settingsTabActive
    ? null
    : resourcesByKind.get(activeKind) ?? controlPlane.resources[0];
  const activeCluster = clusters.find((cluster) => cluster.id === resolvedClusterId) ?? clusters[0];
  const highlights = activeResource ? getHighlights(activeResource) : [];
  const overlayScrollbarOptions = useMemo<PartialOptions>(
    () => ({
      scrollbars: {
        autoHide: "leave",
        autoHideDelay: 120,
        clickScroll: true,
        dragScroll: true,
        theme: "os-theme-xenage",
      },
    }),
    [],
  );
  const tabScrollbarOptions = useMemo<PartialOptions>(
    () => ({
      overflow: {
        x: "scroll",
        y: "hidden",
      },
      scrollbars: {
        autoHide: "leave",
        autoHideDelay: 120,
        clickScroll: true,
        dragScroll: true,
        theme: "os-theme-xenage os-theme-xenage-tabs",
      },
    }),
    [],
  );

  const activateTab = useCallback((tabId: string, clusterId: string) => {
    logger.debug("Activating tab", { tabId, clusterId });
    setActiveTabId(tabId);
    setActiveClusterId(clusterId);
  }, []);

  const openResource = useCallback((kind: string, clusterId: string) => {
    const tabId = `${clusterId}:${kind}`;
    logger.info("Opening resource tab", { kind, clusterId, tabId });
    setOpenTabs((current) => {
      if (current.some((tab) => tab.id === tabId)) {
        logger.debug("Resource tab already open", { tabId });
        return current;
      }

      const next = [...current, { id: tabId, kind, clusterId }];
      logger.debug("Resource tab appended", { tabId, openTabCount: next.length });
      return next;
    });
    activateTab(tabId, clusterId);
  }, [activateTab]);

  const openSettingsTab = useCallback(() => {
    logger.info("Opening settings tab");
    setOpenTabs((current) => {
      if (current.some((tab) => tab.id === SETTINGS_TAB_ID)) {
        logger.debug("Settings tab already open");
        return current;
      }

      const next = [...current, { id: SETTINGS_TAB_ID, kind: SETTINGS_KIND, clusterId: clusters[0].id }];
      logger.debug("Settings tab appended", { openTabCount: next.length });
      return next;
    });
    activateTab(SETTINGS_TAB_ID, clusters[0].id);
  }, [activateTab]);

  const closeTab = useCallback((tabId: string) => {
    let nextActiveTabId: string | null = null;

    setOpenTabs((current) => {
      const closingIndex = current.findIndex((item) => item.id === tabId);
      if (closingIndex === -1) {
        logger.warn("Attempted to close missing tab", { tabId });
        return current;
      }

      if (current.length === 1) {
        logger.warn("Refused to close the last remaining tab", { tabId });
        nextActiveTabId = current[0].id;
        return current;
      }

      const next = current.filter((item) => item.id !== tabId);
      const fallbackTab = next[Math.max(0, closingIndex - 1)] ?? next[0];
      nextActiveTabId = fallbackTab?.id ?? null;
      logger.info("Closing tab", { tabId, nextActiveTabId, openTabCount: next.length });
      return next;
    });

    setActiveTabId((currentActiveTabId) => {
      if (currentActiveTabId !== tabId) {
        return currentActiveTabId;
      }

      return nextActiveTabId ?? currentActiveTabId;
    });
  }, []);

  useEffect(() => {
    logger.info("App mounted", {
      clusterCount: clusters.length,
      resourceCount: controlPlane.resources.length,
      logLevel,
    });
  }, [logLevel]);

  useEffect(() => {
    logger.debug("Navigation search changed", { search });
  }, [search]);

  useEffect(() => {
    logger.debug("Active tab changed", { activeTabId });
  }, [activeTabId]);

  useEffect(() => {
    const hostElement = tabStripRef.current?.getElement();
    if (!hostElement) {
      return;
    }

    const activeTabElement = hostElement.querySelector<HTMLElement>(`[data-tab-id="${CSS.escape(activeTabId)}"]`);
    if (!activeTabElement) {
      logger.debug("Active tab element not found for visibility sync", { activeTabId });
      return;
    }

    logger.debug("Ensuring active tab is visible", { activeTabId });
    activeTabElement.scrollIntoView({
      behavior: "smooth",
      block: "nearest",
      inline: "nearest",
    });
    activeTabElement.focus({ preventScroll: true });
  }, [activeTabId, openTabs]);

  useEffect(() => {
    logger.debug("Open tabs changed", { openTabs: openTabs.map((tab) => tab.id) });
  }, [openTabs]);

  useEffect(() => {
    let mounted = true;
    let unlisten: (() => void) | undefined;

    logger.debug("Subscribing to updater logs");
    void UpdateService.subscribeToLogs((event: UpdateLogEvent) => {
      if (mounted) {
        logger.debug("Updater event bridged to UI", event);
        setUpdateStatus(event.message);
      }
    }).then((dispose) => {
      unlisten = dispose;
    });

    return () => {
      mounted = false;
      logger.debug("Unsubscribing from updater logs");
      unlisten?.();
    };
  }, []);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "q" && openTabs.length > 1) {
        event.preventDefault();
        logger.debug("Keyboard shortcut close tab", { activeTabId });
        closeTab(activeTabId);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [activeTabId, closeTab, openTabs.length]);

  const handleTabWheel = (event: React.WheelEvent<HTMLDivElement>) => {
    const element = tabStripRef.current?.osInstance()?.elements().scrollOffsetElement;
    if (!element) {
      return;
    }

    if (Math.abs(event.deltaY) > Math.abs(event.deltaX)) {
      event.preventDefault();
      element.scrollLeft += event.deltaY;
      logger.debug("Horizontal tab scroll", {
        deltaX: event.deltaX,
        deltaY: event.deltaY,
        nextScrollLeft: element.scrollLeft,
      });
    }
  };

  const handleChannelChange = (nextChannel: UpdateChannel) => {
    logger.info("Changing update channel", { from: channel, to: nextChannel });
    setChannel(nextChannel);
    UpdateService.setChannel(nextChannel);
    setUpdateStatus(`Switched to ${nextChannel} channel.`);
  };

  const handleLogLevelChange = (nextLevel: LogLevel) => {
    setLogLevel(nextLevel);
    setAppLogLevel(nextLevel);
    logger.info("Application log level changed", { level: nextLevel });
    setUpdateStatus(`Log level changed to ${nextLevel}.`);
  };

  const handleCheckUpdates = async () => {
    setCheckingUpdates(true);
    setUpdateStatus("Checking GitHub releases...");
    logger.info("Manual update check requested");
    try {
      const update = await UpdateService.checkForUpdates();
      setUpdateStatus(update ? `Update available: ${update.version}` : "No updates available.");
    } finally {
      setCheckingUpdates(false);
    }
  };

  const handleInstallUpdate = async () => {
    setCheckingUpdates(true);
    setUpdateStatus("Downloading and installing update...");
    logger.info("Manual install update requested");
    try {
      const success = await UpdateService.downloadUpdate();
      setUpdateStatus(success ? "Update installed. Restarting application..." : "No update installed.");
    } finally {
      setCheckingUpdates(false);
    }
  };

  const handleForceUpdate = async () => {
    setCheckingUpdates(true);
    setUpdateStatus("Forcing dev update...");
    logger.warn("Force dev update requested");
    try {
      const success = await UpdateService.forceUpdateDev();
      setUpdateStatus(success ? "Dev update installed. Restarting application..." : "No dev update installed.");
    } finally {
      setCheckingUpdates(false);
    }
  };

  return (
    <main className="ide-shell">
      <aside className="navigator">
        <div className="navigator__header">
          <button
            className="navigator__settings"
            onClick={openSettingsTab}
            type="button"
            title="Open settings tab"
          >
            <Icon name="settings" />
          </button>
          <div className="navigator__title">xenage</div>
        </div>

        <div className="navigator__toolbar">
          <label className="search-box search-box--toolbar">
            <span className="search-box__icon">
              <Icon name="search" />
            </span>
            <input
              aria-label="Search navigation"
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search"
              value={search}
            />
          </label>
          <button className="icon-button" type="button" title="Add cluster">
            <Icon name="plus" />
          </button>
        </div>

        <div className="tree-panel">
          <OverlayScrollbarsComponent
            className="tree-panel__body scroll-host scroll-host--sidebar"
            options={overlayScrollbarOptions}
          >
            <div className="tree-group__clusters">
              {visibleClusters.map((cluster) => (
                <ClusterTree
                  activeClusterId={resolvedClusterId}
                  activeKind={activeKind}
                  cluster={cluster}
                  expanded={expandedClusters[cluster.id] ?? false}
                  items={itemsByCluster[cluster.id].filter((item) => {
                    const term = search.trim().toLowerCase();
                    return !term || cluster.name.toLowerCase().includes(term) || item.label.toLowerCase().includes(term);
                  })}
                  key={cluster.id}
                  onOpen={openResource}
                  onSelectCluster={(clusterId) => {
                    logger.debug("Selecting cluster", { clusterId });
                    setActiveClusterId(clusterId);
                  }}
                  onToggle={() => {
                    logger.debug("Toggling cluster expansion", { clusterId: cluster.id });
                    setExpandedClusters((current) => ({ ...current, [cluster.id]: !current[cluster.id] }));
                  }}
                />
              ))}
            </div>
          </OverlayScrollbarsComponent>
        </div>
      </aside>

      <section className="workspace">
        <header className="workspace__bar">
          <div className="tab-bar">
            <OverlayScrollbarsComponent
              className="tab-strip scroll-host scroll-host--tabs"
              onWheel={handleTabWheel}
              options={tabScrollbarOptions}
              ref={tabStripRef}
            >
              <div className="tab-strip__inner">
                {openTabs.map((tab) => {
                  const resource = resourcesByKind.get(tab.kind);
                  const active = tab.id === activeTabId;
                  const closable = openTabs.length > 1;
                  const cluster = clusters.find((item) => item.id === tab.clusterId) ?? clusters[0];
                  const title = tab.id === SETTINGS_TAB_ID ? SETTINGS_KIND : resource?.title ?? tab.kind;

                  return (
                    <div
                      aria-selected={active}
                      className={`tab ${active ? "tab--active" : ""}`}
                      data-tab-id={tab.id}
                      key={tab.id}
                      onClick={() => activateTab(tab.id, tab.clusterId)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          activateTab(tab.id, tab.clusterId);
                        }
                      }}
                      role="tab"
                      style={{ ["--tab-accent" as string]: cluster.accent }}
                      tabIndex={0}
                    >
                      <span className="tab__icon">
                        <Icon name={tab.id === SETTINGS_TAB_ID ? "settings" : iconNameForItem(tab.kind)} />
                      </span>
                      <span className="tab__title">{title}</span>
                      <button
                        aria-label={`Close ${title}`}
                        className={`tab__close ${!closable ? "tab__close--disabled" : ""}`}
                        disabled={!closable}
                        onClick={(event) => {
                          event.preventDefault();
                          event.stopPropagation();
                          logger.debug("Close button clicked", { tabId: tab.id, closable });
                          if (closable) {
                            closeTab(tab.id);
                          }
                        }}
                        onMouseDown={(event) => {
                          event.preventDefault();
                          event.stopPropagation();
                        }}
                        type="button"
                      >
                        <Icon name="close" />
                      </button>
                    </div>
                  );
                })}
              </div>
            </OverlayScrollbarsComponent>
          </div>
        </header>

        <OverlayScrollbarsComponent className="workspace__content scroll-host" options={overlayScrollbarOptions}>
          {settingsTabActive ? (
            <SettingsView
              channel={channel}
              checkingUpdates={checkingUpdates}
              logLevel={logLevel}
              onChannelChange={handleChannelChange}
              onCheckUpdates={handleCheckUpdates}
              onForceUpdate={handleForceUpdate}
              onInstallUpdate={handleInstallUpdate}
              onLogLevelChange={handleLogLevelChange}
              updateStatus={updateStatus}
            />
          ) : (
            <>
              <div className="editor-header">
                <div>
                  <div className="editor-header__title">{activeResource?.title}</div>
                  <div className="editor-header__subtitle">
                    {activeCluster.name} / {activeResource?.kind} / {controlPlane.apiVersion}
                  </div>
                </div>
                <div className="editor-header__pills">
                  <span className="pill">{activeCluster.status}</span>
                  <span className="pill pill--muted">
                    {String(activeResource?.sample.metadata?.name ?? "resource")}
                  </span>
                </div>
              </div>

              <section className="hero-bar">
                {highlights.map((item) => (
                  <article className="hero-stat" key={item.label}>
                    <span>{item.label}</span>
                    <strong>{item.value}</strong>
                  </article>
                ))}
              </section>

              <section className="workspace-grid">
                <SchemaSection
                  description="Identity and placement fields."
                  rows={getSectionPreview(activeResource!, "metadata", activeResource!.sections.metadata)}
                  title="Metadata"
                />
                <SchemaSection
                  description="Desired state and user intent."
                  rows={getSectionPreview(activeResource!, "spec", activeResource!.sections.spec)}
                  title="Spec"
                />
                <SchemaSection
                  description="Observed state from runtime."
                  rows={getSectionPreview(activeResource!, "status", activeResource!.sections.status)}
                  title="Status"
                />
              </section>

              <section className="detail-layout">
                <article className="panel">
                  <div className="panel__header">
                    <h3>Fields</h3>
                    <span className="pill pill--muted">{activeResource!.fields.length} root fields</span>
                  </div>
                  <div className="schema-table">
                    <div className="schema-table__head">
                      <span>Field</span>
                      <span>Type</span>
                      <span>Req</span>
                    </div>
                    {activeResource!.fields.map((field) => (
                      <div className="schema-table__row" key={field.name}>
                        <span>{field.name}</span>
                        <span>
                          {field.type}
                          {field.isArray ? "[]" : ""}
                        </span>
                        <span>{field.required ? "yes" : "no"}</span>
                      </div>
                    ))}
                  </div>
                </article>

                <article className="panel">
                  <div className="panel__header">
                    <h3>Resource Payload</h3>
                    <span className="pill">{activeResource!.kind}</span>
                  </div>
                  <pre className="json-viewer">{JSON.stringify(activeResource!.sample, null, 2)}</pre>
                </article>
              </section>
            </>
          )}
        </OverlayScrollbarsComponent>
      </section>
    </main>
  );
}

function ClusterTree({
  activeClusterId,
  activeKind,
  cluster,
  expanded,
  items,
  onOpen,
  onSelectCluster,
  onToggle,
}: {
  activeClusterId: string;
  activeKind: string;
  cluster: ClusterEntry;
  expanded: boolean;
  items: NavigationLeaf[];
  onOpen: (kind: string, clusterId: string) => void;
  onSelectCluster: (clusterId: string) => void;
  onToggle: () => void;
}) {
  return (
    <div className="cluster-node">
      <button
        className={`cluster-node__header ${activeClusterId === cluster.id ? "cluster-node__header--active" : ""}`}
        onClick={() => {
          onSelectCluster(cluster.id);
          onToggle();
        }}
        type="button"
      >
        <span className={`caret ${expanded ? "caret--open" : ""}`}>
          <Icon name="chevron" />
        </span>
        <span className="cluster-node__icon" style={{ color: cluster.accent }}>
          <Icon name="cluster" />
        </span>
        <span className="cluster-node__name">{cluster.name}</span>
        <span className={`status-dot status-dot--${cluster.status}`} />
      </button>

      {expanded && (
        <div className="cluster-node__children">
          {items.map((item) => (
            <button
              className={`resource-link ${activeClusterId === cluster.id && activeKind === item.kind ? "resource-link--active" : ""}`}
              key={`${cluster.id}-${item.kind}`}
              onClick={() => onOpen(item.kind, cluster.id)}
              type="button"
            >
              <span className="resource-link__glyph">
                <Icon name={iconNameForItem(item.kind)} />
              </span>
              <span>{item.label}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function SettingsView({
  channel,
  checkingUpdates,
  logLevel,
  onChannelChange,
  onCheckUpdates,
  onForceUpdate,
  onInstallUpdate,
  onLogLevelChange,
  updateStatus,
}: {
  channel: UpdateChannel;
  checkingUpdates: boolean;
  logLevel: LogLevel;
  onChannelChange: (channel: UpdateChannel) => void;
  onCheckUpdates: () => Promise<void>;
  onForceUpdate: () => Promise<void>;
  onInstallUpdate: () => Promise<void>;
  onLogLevelChange: (level: LogLevel) => void;
  updateStatus: string | null;
}) {
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
            {channel === "dev" && (
              <button
                className="settings-button settings-button--muted"
                disabled={checkingUpdates}
                onClick={onForceUpdate}
                type="button"
              >
                Force dev update
              </button>
            )}
          </div>

          <div className="settings-status">
            <strong>Status</strong>
            <span>{updateStatus ?? "No update action yet."}</span>
          </div>
        </article>
      </section>
    </section>
  );
}

function iconNameForItem(kind: string): IconName {
  const icons: Record<string, IconName> = {
    Cluster: "overview",
    Node: "nodes",
    Agent: "agent",
    Run: "run",
    Session: "session",
    Tool: "tool",
    MCP: "mcp",
    Job: "job",
    Event: "event",
    Log: "log",
    ResourceType: "resourceType",
    CustomResource: "customResource",
    ExecutionEnvironment: "environment",
    Secret: "secret",
    AccessControl: "access",
    Interface: "interface",
    Model: "model",
    APIAccess: "api",
    ConfigHistory: "history",
    Alert: "alert",
    Usage: "usage",
  };

  return icons[kind] ?? "overview";
}

type IconName =
  | "access"
  | "agent"
  | "alert"
  | "api"
  | "close"
  | "cluster"
  | "chevron"
  | "customResource"
  | "environment"
  | "event"
  | "history"
  | "interface"
  | "job"
  | "log"
  | "mcp"
  | "model"
  | "nodes"
  | "overview"
  | "panel"
  | "plus"
  | "resourceType"
  | "run"
  | "search"
  | "secret"
  | "settings"
  | "session"
  | "tool"
  | "usage";

function Icon({ name }: { name: IconName }) {
  const common = {
    viewBox: "0 0 16 16",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "1.5",
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    className: "ui-icon",
    "aria-hidden": true,
  };

  const icons: Record<IconName, ReactNode> = {
    access: <path d="M8 2.5 12 4v3c0 2.5-1.4 4.2-4 5.5C5.4 11.2 4 9.5 4 7V4l4-1.5Z" />,
    agent: <><circle cx="8" cy="8" r="2.2" /><path d="M8 1.8v2.1M8 12.1v2.1M1.8 8h2.1M12.1 8h2.1M3.5 3.5l1.5 1.5M11 11l1.5 1.5M12.5 3.5 11 5M5 11 3.5 12.5" /></>,
    alert: <><path d="M8 2.2 13.2 12H2.8L8 2.2Z" /><path d="M8 6v2.8M8 11.3h.01" /></>,
    api: <><path d="M4 5.5h8M4 10.5h8" /><path d="M6 3.5 4 5.5l2 2M10 8.5l2 2-2 2" /></>,
    chevron: <path d="m6 3.5 4 4.5-4 4.5" />,
    close: <path d="m4 4 8 8M12 4 4 12" />,
    cluster: <><path d="M8 2.2 12.8 5v6L8 13.8 3.2 11V5L8 2.2Z" /><path d="M8 2.2V8m0 0 4.8-3M8 8 3.2 5M8 8v5.8" /></>,
    customResource: <><path d="M8 3v10M3 8h10" /><path d="M4.5 4.5h7v7h-7z" /></>,
    environment: <><path d="M8 2.2 12.8 5v6L8 13.8 3.2 11V5L8 2.2Z" /><path d="M5.5 8h5" /></>,
    event: <><circle cx="8" cy="8" r="5.5" /><path d="M8 5v3l2 1.2" /></>,
    history: <><path d="M3 8a5 5 0 1 0 1.2-3.2" /><path d="M3 3.8v3h3" /></>,
    interface: <><rect x="3" y="3.5" width="10" height="7" rx="1.5" /><path d="M6 12.5h4" /></>,
    job: <><rect x="3.2" y="4" width="9.6" height="8.2" rx="1.8" /><path d="M5.5 2.8v2.1M10.5 2.8v2.1M5.5 7.4h5" /></>,
    log: <><path d="M4 4.2h8M4 8h8M4 11.8h5" /></>,
    mcp: <><circle cx="5" cy="8" r="2" /><circle cx="11" cy="5" r="2" /><circle cx="11" cy="11" r="2" /><path d="M6.7 7 9.3 5.9M6.7 9l2.6 1.1" /></>,
    model: <><ellipse cx="8" cy="8" rx="4.8" ry="5.5" /><circle cx="8" cy="8" r="1.5" /></>,
    nodes: <><rect x="2.8" y="3.2" width="4.2" height="4.2" rx="1" /><rect x="9" y="3.2" width="4.2" height="4.2" rx="1" /><rect x="5.9" y="8.6" width="4.2" height="4.2" rx="1" /><path d="M8 7.4v1.2M7 9.2h2" /></>,
    overview: <><rect x="3" y="3" width="4" height="4" rx="1" /><rect x="9" y="3" width="4" height="4" rx="1" /><rect x="3" y="9" width="4" height="4" rx="1" /><rect x="9" y="9" width="4" height="4" rx="1" /></>,
    panel: <><path d="M3 4h10M3 8h10M3 12h10" /></>,
    plus: <path d="M8 3v10M3 8h10" />,
    resourceType: <><path d="M8 2.5 12.5 5 8 7.5 3.5 5 8 2.5ZM3.5 8 8 10.5 12.5 8M3.5 11 8 13.5 12.5 11" /></>,
    run: <><path d="M5 4.2v7.6L11.5 8 5 4.2Z" /></>,
    search: <><circle cx="7" cy="7" r="3.8" /><path d="m10 10 2.8 2.8" /></>,
    secret: <><circle cx="6.2" cy="8" r="2.2" /><path d="M8.2 8H13M11 8v2M9.5 8v1.2" /></>,
    settings: <>
      <path d="M8 1.7 9 2.2l1.1-.2.8.8-.2 1.1.5 1 .9.6v1.2l-.9.6-.5 1 .2 1.1-.8.8-1.1-.2-1 .5-.6.9H7.2l-.6-.9-1-.5-1.1.2-.8-.8.2-1.1-.5-1-.9-.6V6.7l.9-.6.5-1-.2-1.1.8-.8 1.1.2 1-.5.6-.9h1.2Z" />
      <circle cx="8" cy="8" r="2.1" />
    </>,
    session: <><rect x="3" y="3.5" width="10" height="7" rx="1.5" /><path d="M5.5 12.5 8 10.5l2.5 2" /></>,
    tool: <><path d="m9.2 4.2 2.6 2.6M10.4 3a2 2 0 0 0-2.6 2.6l-4.6 4.6a1.2 1.2 0 1 0 1.6 1.6l4.6-4.6A2 2 0 0 0 12 4.6" /></>,
    usage: <><path d="M3 11.5 6 8.5l2 2L13 5.5" /><path d="M10.5 5.5H13v2.5" /></>,
  };

  return <svg {...common}>{icons[name]}</svg>;
}

function SchemaSection({
  title,
  description,
  rows,
}: {
  title: string;
  description: string;
  rows: Array<{ name: string; type: string; value: string }>;
}) {
  return (
    <article className="panel panel--compact">
      <div className="panel__header panel__header--stacked">
        <h3>{title}</h3>
        <p>{description}</p>
      </div>

      <div className="section-rows">
        {rows.map((row) => (
          <div className="section-row" key={row.name}>
            <div>
              <strong>{row.name}</strong>
              <span>{row.type}</span>
            </div>
            <code>{row.value}</code>
          </div>
        ))}
      </div>
    </article>
  );
}

export default App;
