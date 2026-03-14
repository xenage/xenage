import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { OverlayScrollbarsComponent } from "overlayscrollbars-react";
import type { OverlayScrollbarsComponentRef } from "overlayscrollbars-react";
import "overlayscrollbars/overlayscrollbars.css";
import manifest from "./generated/control-plane-release.json";
import "./App.css";
import { ClusterConnectionService } from "./services/clusterConnection";
import type { StoredClusterConnection, StoredClusterUiPrefs } from "./services/clusterConnection";
import { getLogLevel, logger, setLogLevel } from "./services/logger";
import { StandaloneService } from "./services/standalone";
import { UpdateService } from "./services/update";
import type { LogLevel } from "./services/logger";
import type { StandaloneStatus } from "./services/standalone";
import type { UpdateChannel, UpdateLogEvent } from "./services/update";
import type { PartialOptions } from "overlayscrollbars";
import type {
  ControlPlaneManifest,
  NavigationLeaf,
} from "./types/controlPlane";
import type { GuiClusterSnapshot } from "./types/guiConnection";

const controlPlane = manifest as ControlPlaneManifest;
const SETUP_TAB_ID = "app:setup-guide";
const SETUP_KIND = "SetupGuide";
const SETTINGS_TAB_ID = "app:settings";
const SETTINGS_KIND = "Settings";
const DEFAULT_CONTROL_PLANE_ARGS = `--node-id
cp-local
--data-dir
/tmp/xenage/cp-local
--endpoint
http://127.0.0.1:8734
serve
--host
127.0.0.1
--port
8734`;
const DEFAULT_RUNTIME_ARGS = `--node-id
rt-local
--data-dir
/tmp/xenage/rt-local
--endpoint
http://127.0.0.1:8735
serve
--host
127.0.0.1
--port
8735`;
const DEFAULT_GUI_CONNECTION_YAML = `apiVersion: xenage.io/v1alpha1
kind: ClusterConnection
metadata:
  name: demo-admin
spec:
  clusterName: demo
  controlPlaneUrls:
    - http://127.0.0.1:8734
  user:
    id: admin
    role: admin
    publicKey: REPLACE_WITH_GENERATED_PUBLIC_KEY
    privateKey: REPLACE_WITH_GENERATED_PRIVATE_KEY`;

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

type ClusterUiPrefs = {
  name: string;
  accent: string;
};

function App() {
  const tabStripRef = useRef<OverlayScrollbarsComponentRef<"div"> | null>(null);
  const sidebarResizeRef = useRef<{ startX: number; startWidth: number } | null>(null);
  const [search, setSearch] = useState("");
  const [checkingUpdates, setCheckingUpdates] = useState(false);
  const [managingStandalone, setManagingStandalone] = useState(false);
  const [updateStatus, setUpdateStatus] = useState<string | null>(null);
  const [standaloneStatusMessage, setStandaloneStatusMessage] = useState<string | null>(null);
  const [channel, setChannel] = useState<UpdateChannel>(UpdateService.getChannel());
  const [standaloneStatus, setStandaloneStatus] = useState<StandaloneStatus | null>(null);
  const [controlPlaneArgs, setControlPlaneArgs] = useState(DEFAULT_CONTROL_PLANE_ARGS);
  const [runtimeArgs, setRuntimeArgs] = useState(DEFAULT_RUNTIME_ARGS);
  const [logLevel, setAppLogLevel] = useState<LogLevel>(getLogLevel());
  const [guiConnectionYaml, setGuiConnectionYaml] = useState(DEFAULT_GUI_CONNECTION_YAML);
  const [clusterSnapshots, setClusterSnapshots] = useState<Record<string, GuiClusterSnapshot>>({});
  const [clusterSnapshotErrors, setClusterSnapshotErrors] = useState<Record<string, string>>({});
  const [clusterSnapshotLoading, setClusterSnapshotLoading] = useState<Record<string, boolean>>({});
  const [guiConnectionStatus, setGuiConnectionStatus] = useState<string | null>(null);
  const [connectingGui, setConnectingGui] = useState(false);
  const [connectionConfigs, setConnectionConfigs] = useState<StoredClusterConnection[]>([]);
  const [clusterUiPrefs, setClusterUiPrefs] = useState<Record<string, ClusterUiPrefs>>({});
  const [activeClusterId, setActiveClusterId] = useState("");
  const [expandedClusters, setExpandedClusters] = useState<Record<string, boolean>>({});
  const [openTabs, setOpenTabs] = useState<OpenTab[]>([
    { id: SETUP_TAB_ID, kind: SETUP_KIND, clusterId: "" },
  ]);
  const [activeTabId, setActiveTabId] = useState<string>(SETUP_TAB_ID);
  const [draggingTabId, setDraggingTabId] = useState<string | null>(null);
  const [sidebarVisible, setSidebarVisible] = useState(true);
  const [sidebarWidth, setSidebarWidth] = useState(286);
  const [editingClusterId, setEditingClusterId] = useState<string | null>(null);
  const [clusterDraftName, setClusterDraftName] = useState("");
  const [clusterDraftAccent, setClusterDraftAccent] = useState("#22c55e");
  const clusters = useMemo(
    () =>
      connectionConfigs.map((item) => ({
        id: item.id,
        name: clusterUiPrefs[item.id]?.name || item.name,
        status: "connected" as const,
        accent: clusterUiPrefs[item.id]?.accent || "#22c55e",
      })),
    [clusterUiPrefs, connectionConfigs],
  );

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
    [clusters],
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
  const setupTabActive = activeTab?.id === SETUP_TAB_ID;
  const settingsTabActive = activeTab?.id === SETTINGS_TAB_ID;
  const activeKind = activeTab?.kind ?? "Node";
  const resolvedClusterId = activeTab?.clusterId || activeClusterId || clusters[0]?.id || "";
  const activeResource = settingsTabActive || setupTabActive
    ? null
    : resourcesByKind.get(activeKind) ?? controlPlane.resources[0];
  const apiTableKinds = useMemo(() => new Set(["Node", "GroupConfig", "Event"]), []);
  const activeKindIsApiTable = apiTableKinds.has(activeKind);
  const hasStoredConnections = clusters.length > 0;
  const showSidebar = hasStoredConnections && sidebarVisible;
  const activeSnapshot = clusterSnapshots[resolvedClusterId];
  const activeSnapshotError = clusterSnapshotErrors[resolvedClusterId] ?? null;
  const activeSnapshotLoading = clusterSnapshotLoading[resolvedClusterId] ?? false;
  const useLiveTable = Boolean(activeSnapshot && activeKindIsApiTable);
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

  const openSetupTab = useCallback(() => {
    const clusterId = activeClusterId || clusters[0]?.id || "";
    const clusterConfig = connectionConfigs.find((item) => item.id === clusterId) ?? connectionConfigs[0];
    if (clusterConfig?.yaml) {
      setGuiConnectionYaml(clusterConfig.yaml);
    }
    logger.info("Opening setup guide tab");
    setOpenTabs((current) => {
      if (current.some((tab) => tab.id === SETUP_TAB_ID)) {
        return current;
      }
      return [...current, { id: SETUP_TAB_ID, kind: SETUP_KIND, clusterId }];
    });
    activateTab(SETUP_TAB_ID, clusterId);
  }, [activateTab, activeClusterId, clusters, connectionConfigs]);

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

  const moveTab = useCallback((sourceId: string, targetId: string) => {
    if (!sourceId || !targetId || sourceId === targetId) {
      return;
    }

    setOpenTabs((current) => {
      const sourceIndex = current.findIndex((tab) => tab.id === sourceId);
      const targetIndex = current.findIndex((tab) => tab.id === targetId);
      if (sourceIndex === -1 || targetIndex === -1) {
        return current;
      }

      const next = [...current];
      const [moved] = next.splice(sourceIndex, 1);
      next.splice(targetIndex, 0, moved);
      return next;
    });
  }, []);

  const fetchSnapshotForCluster = useCallback(async (clusterId: string) => {
    if (!clusterId) {
      return;
    }
    const connection = connectionConfigs.find((item) => item.id === clusterId);
    if (!connection) {
      return;
    }

    setClusterSnapshotLoading((current) => ({ ...current, [clusterId]: true }));
    setClusterSnapshotErrors((current) => ({ ...current, [clusterId]: "" }));
    try {
      const snapshot = await ClusterConnectionService.fetchSnapshotFromYaml(connection.yaml);
      setClusterSnapshots((current) => ({ ...current, [clusterId]: snapshot }));
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to fetch cluster snapshot.";
      setClusterSnapshotErrors((current) => ({ ...current, [clusterId]: message }));
      logger.error("Failed to fetch cluster snapshot", { clusterId, error });
    } finally {
      setClusterSnapshotLoading((current) => ({ ...current, [clusterId]: false }));
    }
  }, [connectionConfigs]);

  const loadConnections = useCallback(async () => {
    try {
      const [saved, prefs] = await Promise.all([
        ClusterConnectionService.listConnectionYamls(),
        ClusterConnectionService.listClusterUiPrefs(),
      ]);
      setConnectionConfigs(saved);
      setClusterUiPrefs(
        prefs.reduce<Record<string, ClusterUiPrefs>>((acc, item: StoredClusterUiPrefs) => {
          acc[item.connection_id] = {
            name: item.name,
            accent: item.accent,
          };
          return acc;
        }, {}),
      );
      if (saved.length > 0) {
        setActiveClusterId((current) => current || saved[0].id);
        setExpandedClusters((current) => {
          if (Object.keys(current).length > 0) {
            return current;
          }
          return saved.reduce<Record<string, boolean>>((acc, item, index) => {
            acc[item.id] = index === 0;
            return acc;
          }, {});
        });
        setGuiConnectionYaml((current) => (current === DEFAULT_GUI_CONNECTION_YAML ? saved[0].yaml : current));
      }
    } catch (error) {
      logger.error("Failed to load saved cluster configs", error);
    }
  }, []);

  useEffect(() => {
    void loadConnections();
  }, [loadConnections]);

  useEffect(() => {
    logger.info("App mounted", {
      clusterCount: clusters.length,
      resourceCount: controlPlane.resources.length,
      logLevel,
    });
  }, [clusters.length, logLevel]);

  useEffect(() => {
    if (!hasStoredConnections && activeTabId !== SETUP_TAB_ID && activeTabId !== SETTINGS_TAB_ID) {
      setActiveTabId(SETUP_TAB_ID);
    }
  }, [activeTabId, hasStoredConnections]);

  useEffect(() => {
    logger.debug("Navigation search changed", { search });
  }, [search]);

  useEffect(() => {
    logger.debug("Active tab changed", { activeTabId });
  }, [activeTabId]);

  useEffect(() => {
    if (!activeKindIsApiTable || !resolvedClusterId) {
      return;
    }
    if (clusterSnapshots[resolvedClusterId] || clusterSnapshotLoading[resolvedClusterId]) {
      return;
    }
    void fetchSnapshotForCluster(resolvedClusterId);
  }, [
    activeKindIsApiTable,
    clusterSnapshotLoading,
    clusterSnapshots,
    fetchSnapshotForCluster,
    resolvedClusterId,
  ]);

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
    let mounted = true;
    let unlisten: (() => void) | undefined;

    logger.debug("Subscribing to standalone logs");
    void StandaloneService.subscribeToLogs((event) => {
      if (mounted) {
        setStandaloneStatusMessage(event.message);
      }
    }).then((dispose) => {
      unlisten = dispose;
    });

    return () => {
      mounted = false;
      logger.debug("Unsubscribing from standalone logs");
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

  useEffect(() => {
    const onMove = (event: MouseEvent) => {
      const activeResize = sidebarResizeRef.current;
      if (!activeResize) {
        return;
      }
      const nextWidth = Math.max(220, Math.min(520, activeResize.startWidth + event.clientX - activeResize.startX));
      setSidebarWidth(nextWidth);
    };

    const onUp = () => {
      sidebarResizeRef.current = null;
      document.body.style.userSelect = "";
    };

    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, []);

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

  const parseArgsList = (raw: string): string[] =>
    raw
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean);

  const refreshStandaloneStatus = useCallback(async () => {
    try {
      const status = await StandaloneService.status();
      setStandaloneStatus(status);
      return status;
    } catch (error) {
      logger.error("Failed to fetch standalone status", error);
      setStandaloneStatusMessage("Failed to fetch standalone status.");
      return null;
    }
  }, []);

  useEffect(() => {
    void refreshStandaloneStatus();
  }, [refreshStandaloneStatus]);

  const handleInstallStandaloneBundle = async () => {
    setManagingStandalone(true);
    setStandaloneStatusMessage("Downloading standalone package...");
    try {
      const result = await StandaloneService.installBundle(channel);
      setStandaloneStatusMessage(`Installed standalone ${result.version} to ${result.install_dir}`);
      await refreshStandaloneStatus();
    } catch (error) {
      logger.error("Failed to install standalone package", error);
      setStandaloneStatusMessage("Standalone package installation failed.");
    } finally {
      setManagingStandalone(false);
    }
  };

  const handleInstallStandaloneServices = async () => {
    setManagingStandalone(true);
    setStandaloneStatusMessage("Installing node services...");
    try {
      const cpArgs = parseArgsList(controlPlaneArgs);
      const rtArgs = parseArgsList(runtimeArgs);
      await StandaloneService.installNodeService("control-plane", cpArgs);
      await StandaloneService.installNodeService("runtime", rtArgs);
      setStandaloneStatusMessage("Node services installed.");
      await refreshStandaloneStatus();
    } catch (error) {
      logger.error("Failed to install standalone services", error);
      setStandaloneStatusMessage("Service installation failed. Check arguments and permissions.");
    } finally {
      setManagingStandalone(false);
    }
  };

  const handleStartStandaloneServices = async () => {
    setManagingStandalone(true);
    setStandaloneStatusMessage("Starting node services...");
    try {
      await StandaloneService.startNodeService("control-plane");
      await StandaloneService.startNodeService("runtime");
      setStandaloneStatusMessage("Node services started.");
      await refreshStandaloneStatus();
    } catch (error) {
      logger.error("Failed to start standalone services", error);
      setStandaloneStatusMessage("Failed to start services. Check service privileges.");
    } finally {
      setManagingStandalone(false);
    }
  };

  const handleStopStandaloneServices = async () => {
    setManagingStandalone(true);
    setStandaloneStatusMessage("Stopping node services...");
    try {
      await StandaloneService.stopNodeService("control-plane");
      await StandaloneService.stopNodeService("runtime");
      setStandaloneStatusMessage("Node services stopped.");
      await refreshStandaloneStatus();
    } catch (error) {
      logger.error("Failed to stop standalone services", error);
      setStandaloneStatusMessage("Failed to stop services.");
    } finally {
      setManagingStandalone(false);
    }
  };

  const handleConnectGui = async () => {
    setConnectingGui(true);
    setGuiConnectionStatus("Connecting to control-plane...");
    try {
      const snapshot = await ClusterConnectionService.fetchSnapshotFromYaml(guiConnectionYaml);
      const saved = await ClusterConnectionService.saveConnectionYaml(guiConnectionYaml);
      const allSaved = await ClusterConnectionService.listConnectionYamls();
      setConnectionConfigs(allSaved);
      setActiveClusterId(saved.id);
      setExpandedClusters((current) => ({ ...current, [saved.id]: true }));
      setClusterSnapshots((current) => ({ ...current, [saved.id]: snapshot }));
      setClusterSnapshotErrors((current) => ({ ...current, [saved.id]: "" }));
      setGuiConnectionStatus(
        `Connected to ${snapshot.group_id} (state ${snapshot.state_version}, epoch ${snapshot.leader_epoch}).`,
      );
    } catch (error) {
      logger.error("Failed to connect GUI to cluster", error);
      setGuiConnectionStatus(
        error instanceof Error ? error.message : "Failed to connect using provided YAML config.",
      );
    } finally {
      setConnectingGui(false);
    }
  };

  const openClusterConfigEditor = useCallback((clusterId: string) => {
    const connection = connectionConfigs.find((item) => item.id === clusterId);
    if (!connection) {
      return;
    }
    const prefs = clusterUiPrefs[clusterId];
    setClusterDraftName(prefs?.name || connection.name);
    setClusterDraftAccent(prefs?.accent || "#22c55e");
    setEditingClusterId(clusterId);
  }, [clusterUiPrefs, connectionConfigs]);

  const saveClusterConfigEditor = useCallback(async () => {
    if (!editingClusterId) {
      return;
    }
    try {
      const saved = await ClusterConnectionService.saveClusterUiPrefsEntry(
        editingClusterId,
        clusterDraftName,
        clusterDraftAccent,
      );
      setClusterUiPrefs((current) => ({
        ...current,
        [saved.connection_id]: {
          name: saved.name,
          accent: saved.accent,
        },
      }));
      setEditingClusterId(null);
    } catch (error) {
      logger.error("Failed to save cluster UI prefs", error);
    }
  }, [clusterDraftAccent, clusterDraftName, editingClusterId]);

  const deleteClusterFromEditor = useCallback(async () => {
    if (!editingClusterId) {
      return;
    }
    try {
      await ClusterConnectionService.deleteClusterConnection(editingClusterId);
      let deletedActiveTab = false;
      setOpenTabs((current) => {
        deletedActiveTab = current.some((tab) => tab.id === activeTabId && tab.clusterId === editingClusterId);
        const filtered = current.filter((tab) => tab.clusterId !== editingClusterId);
        return filtered.length > 0 ? filtered : [{ id: SETUP_TAB_ID, kind: SETUP_KIND, clusterId: "" }];
      });
      if (deletedActiveTab) {
        setActiveTabId(SETUP_TAB_ID);
      }
      setClusterSnapshots((current) => {
        const next = { ...current };
        delete next[editingClusterId];
        return next;
      });
      setClusterSnapshotErrors((current) => {
        const next = { ...current };
        delete next[editingClusterId];
        return next;
      });
      setClusterUiPrefs((current) => {
        const next = { ...current };
        delete next[editingClusterId];
        return next;
      });
      setEditingClusterId(null);
      await loadConnections();
    } catch (error) {
      logger.error("Failed to delete cluster connection", error);
    }
  }, [activeTabId, editingClusterId, loadConnections]);

  const shareClusterConfigFromEditor = useCallback(async () => {
    if (!editingClusterId) {
      return;
    }
    const config = connectionConfigs.find((item) => item.id === editingClusterId);
    if (!config) {
      return;
    }
    try {
      await navigator.clipboard.writeText(config.yaml);
      setGuiConnectionStatus(`Cluster config copied to clipboard (${config.name}).`);
    } catch (error) {
      logger.error("Failed to copy cluster yaml to clipboard", error);
      setGuiConnectionStatus("Failed to copy cluster config to clipboard.");
    }
  }, [connectionConfigs, editingClusterId]);

  return (
    <main
      className={`ide-shell ${showSidebar ? "" : "ide-shell--no-sidebar"}`}
      style={{ ["--sidebar-width" as string]: `${sidebarWidth}px` }}
    >
      {showSidebar ? (
      <aside className="navigator">
        <div className="navigator__header">
          <button
            className="navigator__settings"
            onClick={() => setSidebarVisible(false)}
            type="button"
            title="Hide sidebar"
          >
            <Icon name="close" />
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
          <button className="icon-button" onClick={openSetupTab} type="button" title="Open setup guide">
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
                  onEditCluster={openClusterConfigEditor}
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
        {editingClusterId ? (
          <div className="cluster-editor">
            <div className="cluster-editor__header">
              <div className="cluster-editor__title">Cluster Config</div>
              <button
                className="cluster-editor__icon"
                onClick={() => void shareClusterConfigFromEditor()}
                title="Share config (copy YAML)"
                type="button"
              >
                <Icon name="api" />
              </button>
            </div>
            <label className="cluster-editor__field">
              <span>Name</span>
              <input
                onChange={(event) => setClusterDraftName(event.target.value)}
                value={clusterDraftName}
              />
            </label>
            <label className="cluster-editor__field">
              <span>Color</span>
              <input
                onChange={(event) => setClusterDraftAccent(event.target.value)}
                type="color"
                value={clusterDraftAccent}
              />
            </label>
            <div className="cluster-editor__actions">
              <button className="cluster-editor__button" onClick={() => void saveClusterConfigEditor()} type="button">Save</button>
              <button className="cluster-editor__button cluster-editor__button--danger" onClick={() => void deleteClusterFromEditor()} type="button">Delete</button>
              <button className="cluster-editor__button cluster-editor__button--muted" onClick={() => setEditingClusterId(null)} type="button">Cancel</button>
            </div>
          </div>
        ) : null}
        <div
          className="navigator__resize-handle"
          onMouseDown={(event) => {
            event.preventDefault();
            sidebarResizeRef.current = { startX: event.clientX, startWidth: sidebarWidth };
            document.body.style.userSelect = "none";
          }}
          role="separator"
          aria-label="Resize sidebar"
        />
      </aside>
      ) : null}

      <section className="workspace">
        <header className="workspace__bar">
          {!showSidebar && hasStoredConnections ? (
            <button
              className="workspace__sidebar-toggle"
              onClick={() => setSidebarVisible(true)}
              title="Show sidebar"
              type="button"
            >
              <Icon name="panel" />
            </button>
          ) : null}
          <div className="tab-bar">
            <OverlayScrollbarsComponent
              className="tab-strip scroll-host scroll-host--tabs"
              onWheel={handleTabWheel}
              options={tabScrollbarOptions}
              ref={tabStripRef}
            >
              <div
                className="tab-strip__inner"
                onDragOver={(event) => {
                  if (!draggingTabId) {
                    return;
                  }
                  event.preventDefault();
                }}
                onDrop={(event) => {
                  if (!draggingTabId) {
                    return;
                  }
                  event.preventDefault();
                  setOpenTabs((current) => {
                    const sourceIndex = current.findIndex((tab) => tab.id === draggingTabId);
                    if (sourceIndex === -1) {
                      return current;
                    }
                    const next = [...current];
                    const [moved] = next.splice(sourceIndex, 1);
                    next.push(moved);
                    return next;
                  });
                  setDraggingTabId(null);
                }}
              >
                {openTabs.map((tab) => {
                  const resource = resourcesByKind.get(tab.kind);
                  const active = tab.id === activeTabId;
                  const closable = openTabs.length > 1;
                  const cluster = clusters.find((item) => item.id === tab.clusterId) ?? {
                    id: "local",
                    name: "LOCAL",
                    status: "connected" as const,
                    accent: "#22c55e",
                  };
                  const tabLabel = tab.id === SETTINGS_TAB_ID ? SETTINGS_KIND : tab.id === SETUP_TAB_ID ? "Setup Guide" : resource?.title ?? tab.kind;
                  const title = cluster.name ? `${tabLabel} · ${cluster.name}` : tabLabel;

                  return (
                    <div
                      aria-selected={active}
                      className={`tab ${active ? "tab--active" : ""} ${draggingTabId === tab.id ? "tab--dragging" : ""}`}
                      data-tab-id={tab.id}
                      draggable
                      key={tab.id}
                      onClick={() => activateTab(tab.id, tab.clusterId)}
                      onDragEnd={() => setDraggingTabId(null)}
                      onDragOver={(event) => {
                        if (!draggingTabId || draggingTabId === tab.id) {
                          return;
                        }
                        event.preventDefault();
                      }}
                      onDragStart={(event) => {
                        event.dataTransfer.effectAllowed = "move";
                        event.dataTransfer.setData("text/plain", tab.id);
                        setDraggingTabId(tab.id);
                      }}
                      onDrop={(event) => {
                        event.preventDefault();
                        const sourceId = event.dataTransfer.getData("text/plain") || draggingTabId;
                        if (sourceId) {
                          moveTab(sourceId, tab.id);
                        }
                        setDraggingTabId(null);
                      }}
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
                        <Icon name={tab.id === SETTINGS_TAB_ID || tab.id === SETUP_TAB_ID ? "settings" : iconNameForItem(tab.kind)} />
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

        <OverlayScrollbarsComponent
          className={`workspace__content scroll-host ${!settingsTabActive && !setupTabActive ? "workspace__content--compact" : ""}`}
          options={overlayScrollbarOptions}
        >
          {settingsTabActive ? (
            <SettingsView
              channel={channel}
              checkingUpdates={checkingUpdates}
              logLevel={logLevel}
              onChannelChange={handleChannelChange}
              onCheckUpdates={handleCheckUpdates}
              onForceUpdate={handleForceUpdate}
              onInstallUpdate={handleInstallUpdate}
              onInstallStandaloneBundle={handleInstallStandaloneBundle}
              onInstallStandaloneServices={handleInstallStandaloneServices}
              onLogLevelChange={handleLogLevelChange}
              onRefreshStandaloneStatus={refreshStandaloneStatus}
              onStartStandaloneServices={handleStartStandaloneServices}
              onStopStandaloneServices={handleStopStandaloneServices}
              onUpdateControlPlaneArgs={setControlPlaneArgs}
              onUpdateRuntimeArgs={setRuntimeArgs}
              standaloneBusy={managingStandalone}
              standaloneControlPlaneArgs={controlPlaneArgs}
              standaloneRuntimeArgs={runtimeArgs}
              standaloneStatus={standaloneStatus}
              standaloneStatusMessage={standaloneStatusMessage}
              updateStatus={updateStatus}
            />
          ) : setupTabActive ? (
            <SetupGuideView
              connectingGui={connectingGui}
              guiConnectionStatus={guiConnectionStatus}
              guiConnectionYaml={guiConnectionYaml}
              onConnect={handleConnectGui}
              onYamlChange={setGuiConnectionYaml}
            />
          ) : (
            <div className="resource-pane">
              {useLiveTable ? (
                activeKind === "Node" ? (
                  <LiveNodeTable rows={activeSnapshot!.nodes} />
                ) : activeKind === "GroupConfig" ? (
                  <LiveGroupConfigTable rows={activeSnapshot!.group_config} />
                ) : (
                  <LiveEventLogTable rows={activeSnapshot!.event_log} />
                )
              ) : activeKindIsApiTable ? (
                <ApiFetchStateTable
                  error={activeSnapshotError}
                  kind={activeKind}
                  loading={activeSnapshotLoading}
                  onRetry={() => void fetchSnapshotForCluster(resolvedClusterId)}
                />
              ) : (
                <ApiUnavailableTable kind={activeResource?.kind ?? activeKind} />
              )}
            </div>
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
  onEditCluster,
  onOpen,
  onSelectCluster,
  onToggle,
}: {
  activeClusterId: string;
  activeKind: string;
  cluster: ClusterEntry;
  expanded: boolean;
  items: NavigationLeaf[];
  onEditCluster: (clusterId: string) => void;
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
        <span
          className="cluster-node__edit"
          onClick={(event) => {
            event.preventDefault();
            event.stopPropagation();
            onEditCluster(cluster.id);
          }}
          onKeyDown={(event) => {
            if (event.key === "Enter" || event.key === " ") {
              event.preventDefault();
              event.stopPropagation();
              onEditCluster(cluster.id);
            }
          }}
          role="button"
          tabIndex={0}
          title="Cluster config"
        >
          <Icon name="settings" />
        </span>
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

type IdeTableColumn = {
  key: string;
  label: string;
  width: number;
  minWidth?: number;
};

type IdeTableRow = {
  key: string;
  values: Record<string, string>;
};

function IdeDataTable({
  columns,
  emptyLabel = "No rows",
  rows,
}: {
  columns: IdeTableColumn[];
  emptyLabel?: string;
  rows: IdeTableRow[];
}) {
  const [columnWidths, setColumnWidths] = useState<Record<string, number>>(() =>
    columns.reduce<Record<string, number>>((acc, column) => {
      acc[column.key] = column.width;
      return acc;
    }, {}),
  );
  const resizingRef = useRef<{ columnKey: string; minWidth: number; startX: number; startWidth: number } | null>(null);

  useEffect(() => {
    setColumnWidths(
      columns.reduce<Record<string, number>>((acc, column) => {
        acc[column.key] = column.width;
        return acc;
      }, {}),
    );
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

  const templateColumns = columns.map((column) => `${columnWidths[column.key] ?? column.width}px`).join(" ");

  return (
    <div className="schema-table schema-table--live">
      <div className="schema-table__head" style={{ gridTemplateColumns: templateColumns }}>
        {columns.map((column) => (
          <div className="schema-table__cell schema-table__cell--head" key={column.key}>
            <span>{column.label}</span>
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
      {rows.length === 0 ? (
        <div className="schema-table__empty">{emptyLabel}</div>
      ) : (
        rows.map((row) => (
          <div className="schema-table__row" key={row.key} style={{ gridTemplateColumns: templateColumns }}>
            {columns.map((column) => (
              <span className="schema-table__cell" key={column.key}>
                {row.values[column.key] ?? "-"}
              </span>
            ))}
          </div>
        ))
      )}
    </div>
  );
}

function ApiUnavailableTable({ kind }: { kind: string }) {
  return (
    <div className="schema-table schema-table--live">
      <div className="schema-table__empty">
        API table is available only for Node, Event, and Group Config. No schema fallback for {kind}.
      </div>
    </div>
  );
}

function ApiFetchStateTable({
  error,
  kind,
  loading,
  onRetry,
}: {
  error: string | null;
  kind: string;
  loading: boolean;
  onRetry: () => void;
}) {
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

function LiveNodeTable({ rows }: { rows: GuiClusterSnapshot["nodes"] }) {
  const getRawString = (row: GuiClusterSnapshot["nodes"][number], keys: string[]): string | null => {
    const source = row as unknown as Record<string, unknown>;
    for (const key of keys) {
      const value = source[key];
      if (typeof value === "string" && value.trim().length > 0) {
        return value.trim();
      }
    }
    return null;
  };

  const getRawBool = (row: GuiClusterSnapshot["nodes"][number], keys: string[]): boolean | null => {
    const source = row as unknown as Record<string, unknown>;
    for (const key of keys) {
      const value = source[key];
      if (typeof value === "boolean") {
        return value;
      }
    }
    return null;
  };

  const formatDuration = (milliseconds: number): string => {
    const totalSeconds = Math.max(0, Math.floor(milliseconds / 1000));
    if (totalSeconds < 60) {
      return `${totalSeconds}s`;
    }
    const totalMinutes = Math.floor(totalSeconds / 60);
    if (totalMinutes < 60) {
      return `${totalMinutes}m`;
    }
    const totalHours = Math.floor(totalMinutes / 60);
    if (totalHours < 24) {
      return `${totalHours}h`;
    }
    const totalDays = Math.floor(totalHours / 24);
    return `${totalDays}d`;
  };

  const endpointList = (row: GuiClusterSnapshot["nodes"][number]): string[] => {
    const source = (row as { endpoints?: unknown; endpoint?: unknown }).endpoints ?? (row as { endpoint?: unknown }).endpoint;
    if (Array.isArray(source)) {
      return source.filter((item): item is string => typeof item === "string");
    }
    if (typeof source === "string" && source.length > 0) {
      return [source];
    }
    return [];
  };

  const primaryIp = (row: GuiClusterSnapshot["nodes"][number]): string => {
    const first = endpointList(row)[0];
    if (!first) {
      return "-";
    }
    try {
      return new URL(first).hostname;
    } catch {
      return first;
    }
  };

  const nodeType = (row: GuiClusterSnapshot["nodes"][number]): string =>
    row.leader && row.role === "control-plane" ? "control-plane (leader)" : row.role;

  const nodeVersion = (row: GuiClusterSnapshot["nodes"][number]): string =>
    getRawString(row, ["xenage_version", "version", "agent_version", "binary_version"]) ?? "-";

  const nodeAge = (row: GuiClusterSnapshot["nodes"][number]): string => {
    const ageDirect = getRawString(row, ["age", "uptime"]);
    if (ageDirect) {
      return ageDirect;
    }
    const timestamp = getRawString(row, ["started_at", "created_at", "first_seen_at", "registered_at"]);
    if (!timestamp) {
      return "-";
    }
    const parsed = Date.parse(timestamp);
    if (Number.isNaN(parsed)) {
      return timestamp;
    }
    return formatDuration(Date.now() - parsed);
  };

  const nodeStatus = (row: GuiClusterSnapshot["nodes"][number]): string => {
    const statusTokens: string[] = [];
    if (row.leader) {
      statusTokens.push("leader");
    }
    const ready = getRawBool(row, ["ready", "is_ready"]);
    if (ready !== null) {
      statusTokens.push(ready ? "ready" : "not-ready");
    }
    const extraStatus = getRawString(row, ["status", "state", "health"]);
    if (extraStatus && !statusTokens.includes(extraStatus)) {
      statusTokens.push(extraStatus);
    }
    return statusTokens.join(", ") || "-";
  };

  return (
    <IdeDataTable
      columns={[
        { key: "ip", label: "IP", width: 220, minWidth: 110 },
        { key: "name", label: "Name", width: 300, minWidth: 150 },
        { key: "type", label: "Type", width: 220, minWidth: 120 },
        { key: "version", label: "Version", width: 130, minWidth: 90 },
        { key: "age", label: "Age", width: 90, minWidth: 70 },
        { key: "status", label: "Status", width: 220, minWidth: 150 },
        { key: "endpoint", label: "Endpoint", width: 520, minWidth: 240 },
      ]}
      rows={rows.map((row) => ({
        key: row.node_id,
        values: {
          ip: primaryIp(row),
          name: row.node_id,
          type: nodeType(row),
          version: nodeVersion(row),
          age: nodeAge(row),
          status: nodeStatus(row),
          endpoint: endpointList(row).join(", ") || "-",
        },
      }))}
    />
  );
}

function LiveGroupConfigTable({ rows }: { rows: GuiClusterSnapshot["group_config"] }) {
  return (
    <IdeDataTable
      columns={[
        { key: "key", label: "Key", width: 320, minWidth: 140 },
        { key: "value", label: "Value", width: 760, minWidth: 220 },
      ]}
      rows={rows.map((row) => ({
        key: row.key,
        values: {
          key: row.key,
          value: row.value,
        },
      }))}
    />
  );
}

function LiveEventLogTable({ rows }: { rows: GuiClusterSnapshot["event_log"] }) {
  return (
    <IdeDataTable
      columns={[
        { key: "sequence", label: "#", width: 80, minWidth: 60 },
        { key: "happenedAt", label: "At", width: 300, minWidth: 170 },
        { key: "actor", label: "Actor", width: 280, minWidth: 130 },
        { key: "action", label: "Action", width: 560, minWidth: 200 },
      ]}
      rows={rows.map((row) => ({
        key: String(row.sequence),
        values: {
          sequence: String(row.sequence),
          happenedAt: row.happened_at,
          actor: `${row.actor_type}/${row.actor_id}`,
          action: row.action,
        },
      }))}
    />
  );
}

function SetupGuideView({
  connectingGui,
  guiConnectionStatus,
  guiConnectionYaml,
  onConnect,
  onYamlChange,
}: {
  connectingGui: boolean;
  guiConnectionStatus: string | null;
  guiConnectionYaml: string;
  onConnect: () => Promise<void>;
  onYamlChange: (value: string) => void;
}) {
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

function SettingsView({
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
}: {
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
            <button className="settings-button settings-button--muted" disabled={standaloneBusy} onClick={() => void onRefreshStandaloneStatus()} type="button">
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

export default App;
