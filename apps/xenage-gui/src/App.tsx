import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { arrayMove } from "@dnd-kit/sortable";
import "overlayscrollbars/overlayscrollbars.css";
import "./App.css";
import { parseInitialHorizontalWindowTab, parseInitialWindowTab } from "./modules/tabs/windowState";
import { logger } from "./services/logger";
import {
  SETUP_KIND,
  OVERLAY_SCROLLBAR_OPTIONS,
  TAB_SCROLLBAR_OPTIONS,
  SETUP_TAB_ID,
  controlPlane,
} from "./modules/app/constants";
import { formatClockTime } from "./modules/app/utils";
import { useMaintenanceSettings } from "./modules/app/hooks/useMaintenanceSettings";
import { useClusterConnections } from "./modules/app/hooks/useClusterConnections";
import { useClusterData } from "./modules/app/hooks/useClusterData";
import { useTabManager } from "./modules/app/hooks/useTabManager";
import { useAppEffects } from "./modules/app/hooks/useAppEffects";
import { useAppViewModel } from "./modules/app/hooks/useAppViewModel";
import { NavigatorSidebar } from "./modules/app/components/NavigatorSidebar";
import { WorkspaceHeader } from "./modules/app/components/WorkspaceHeader";
import { WorkspaceContent } from "./modules/app/components/WorkspaceContent";
import { StatusBar } from "./modules/app/components/StatusBar";
import { AgentConsole } from "./modules/app/components/AgentConsole";
import { HorizontalSubWindow } from "./modules/app/components/HorizontalSubWindow";
import type { HorizontalTab } from "./modules/app/components/HorizontalSubWindow";
import { iconNameForItem } from "./components/Icon";
import { ClusterConnectionService } from "./services/clusterConnection";
import { RbacEditorTabContent } from "./modules/rbac/RbacEditorTabContent";
import { WindowService } from "./services/window";

type ConsoleSubWindowTab = HorizontalTab & {
  kind: "console";
};

type RbacSubWindowTab = HorizontalTab & {
  kind: "rbac-editor";
  payload: {
    clusterId: string;
    clusterYaml: string;
    kind: string;
    resourceName: string | null;
    yaml: string;
  };
  status: string | null;
};

type SubWindowTab = ConsoleSubWindowTab | RbacSubWindowTab;

function App() {
  const initialWindowTab = useMemo(() => parseInitialWindowTab(window.location.href), []);
  const initialHorizontalWindowTab = useMemo(
    () => parseInitialHorizontalWindowTab(window.location.href),
    [],
  );

  const {
    activeClusterId,
    clusterDraftAccent,
    clusterDraftName,
    clusters,
    connectGui,
    connectingGui,
    connectionConfigs,
    deleteClusterFromEditor,
    editingClusterId,
    expandedClusters,
    guiConnectionStatus,
    guiConnectionYaml,
    openClusterConfigEditor,
    saveClusterConfigEditor,
    setActiveClusterId,
    setClusterDraftAccent,
    setClusterDraftName,
    setConnectionConfigs,
    setEditingClusterId,
    setExpandedClusters,
    setGuiConnectionYaml,
    shareClusterConfigFromEditor,
    shareCopyNotice,
  } = useClusterConnections({ initialClusterId: initialWindowTab?.clusterId });

  const {
    activateTab,
    activeTabId,
    closeTab,
    handleTabDragEnd,
    handleTabWheel,
    openResource,
    openSettingsTab,
    openSetupTab,
    openTabs,
    setActiveTabId,
    setOpenTabs,
    tabBarRef,
    tabSensors,
    tabStripRef,
  } = useTabManager({
    activeClusterId,
    clusters,
    connectionConfigs,
    initialWindowTab,
    setActiveClusterId,
    setGuiConnectionYaml,
  });

  const eventPageSize = useMemo(
    () => controlPlane.tables.find((table) => table.kind === "Event")?.pageSize ?? 200,
    [],
  );

  const {
    clearClusterData,
    clusterEvents,
    clusterSnapshotErrors,
    clusterSnapshotLoading,
    clusterSnapshots,
    fetchEventPageForCluster,
    fetchSnapshotForCluster,
    hasDataFetchError,
    isDataFetching,
    setClusterEvents,
    setClusterSnapshotErrors,
    setClusterSnapshots,
  } = useClusterData({
    connectionConfigs,
    eventPageSize,
    setConnectionConfigs,
  });

  const {
    channel,
    checkingUpdates,
    controlPlaneArgs,
    handleChannelChange,
    handleCheckUpdates,
    handleForceUpdate,
    handleInstallStandaloneBundle,
    handleInstallStandaloneServices,
    handleInstallUpdate,
    handleLogLevelChange,
    handleStartStandaloneServices,
    handleStopStandaloneServices,
    logLevel,
    managingStandalone,
    refreshStandaloneStatus,
    runtimeArgs,
    setControlPlaneArgs,
    setRuntimeArgs,
    standaloneStatus,
    standaloneStatusMessage,
    updateStatus,
  } = useMaintenanceSettings();

  const sidebarResizeRef = useRef<{ startX: number; startWidth: number } | null>(null);
  const [search, setSearch] = useState("");
  const [horizontalTabs, setHorizontalTabs] = useState<SubWindowTab[]>(() => {
    if (!initialHorizontalWindowTab) {
      return [];
    }
    if (initialHorizontalWindowTab.kind === "console") {
      return [
        {
          id: initialHorizontalWindowTab.id,
          title: initialHorizontalWindowTab.title,
          icon: initialHorizontalWindowTab.icon,
          kind: "console",
        },
      ];
    }
    if (!initialHorizontalWindowTab.payload) {
      return [];
    }
    return [
      {
        id: initialHorizontalWindowTab.id,
        title: initialHorizontalWindowTab.title,
        icon: initialHorizontalWindowTab.icon,
        kind: "rbac-editor",
        payload: initialHorizontalWindowTab.payload,
        status: null,
      },
    ];
  });
  const [activeHorizontalTabId, setActiveHorizontalTabId] = useState(
    initialHorizontalWindowTab?.id ?? "",
  );
  const [applyingSubWindowTabId, setApplyingSubWindowTabId] = useState("");
  const [tableSearch, setTableSearch] = useState("");
  const [sidebarVisible, setSidebarVisible] = useState(true);
  const [sidebarWidth, setSidebarWidth] = useState(286);
  const [clockTime, setClockTime] = useState(() => formatClockTime(Date.now()));
  const {
    activeClusterInconsistency,
    activeClusterUserId,
    activeKind,
    activeKindNeedsSnapshot,
    activeKindUsesSnapshot,
    activeResource,
    activeSnapshot,
    activeSnapshotError,
    activeSnapshotLoading,
    activeTableSchema,
    filteredItemsByCluster,
    hasStoredConnections,
    resolvedClusterId,
    resourcesByKind,
    settingsTabActive,
    setupTabActive,
    useLiveSnapshotTable,
    visibleClusters,
  } = useAppViewModel({
    activeClusterId,
    activeTabId,
    clusterSnapshotErrors,
    clusterSnapshotLoading,
    clusterSnapshots,
    clusters,
    connectionConfigs,
    openTabs,
    search,
  });
  const showSidebar = hasStoredConnections && sidebarVisible;

  const refreshActiveTabFromServer = useCallback(() => {
    if (!resolvedClusterId) {
      return;
    }
    const requests: Array<Promise<boolean>> = [];
    if (activeKindNeedsSnapshot) {
      requests.push(fetchSnapshotForCluster(resolvedClusterId));
    }
    if (activeKind === "Event") {
      requests.push(fetchEventPageForCluster(resolvedClusterId, "refresh"));
    }
    if (requests.length === 0) {
      return;
    }
    logger.debug("Manual tab refresh requested", { activeTabId, activeKind, clusterId: resolvedClusterId });
    void Promise.all(requests);
  }, [
    activeKind,
    activeKindNeedsSnapshot,
    activeTabId,
    fetchEventPageForCluster,
    fetchSnapshotForCluster,
    resolvedClusterId,
  ]);

  const handleConnectGui = useCallback(async () => {
    const connected = await connectGui();
    if (!connected) {
      return;
    }
    const { saved, snapshot } = connected;
    setClusterSnapshots((current) => ({ ...current, [saved.id]: snapshot }));
    setClusterSnapshotErrors((current) => ({ ...current, [saved.id]: "" }));
    setClusterEvents((current) => ({
      ...current,
      [saved.id]: {
        hasMore: true,
        items: [],
        loading: false,
        oldestSequence: null,
      },
    }));

    const nodeTabId = `${saved.id}:Node`;
    setOpenTabs((current) => {
      const withoutSetup = current.filter((tab) => tab.id !== SETUP_TAB_ID);
      if (withoutSetup.some((tab) => tab.id === nodeTabId)) {
        return withoutSetup;
      }
      return [...withoutSetup, { id: nodeTabId, kind: "Node", clusterId: saved.id }];
    });
    setActiveTabId(nodeTabId);
  }, [connectGui, setActiveTabId, setClusterEvents, setClusterSnapshotErrors, setClusterSnapshots, setOpenTabs]);

  const handleDeleteClusterFromEditor = useCallback(async () => {
    const deletedClusterId = await deleteClusterFromEditor();
    if (!deletedClusterId) {
      return;
    }

    let deletedActiveTab = false;
    setOpenTabs((current) => {
      deletedActiveTab = current.some((tab) => tab.id === activeTabId && tab.clusterId === deletedClusterId);
      const filtered = current.filter((tab) => tab.clusterId !== deletedClusterId);
      return filtered.length > 0 ? filtered : [{ id: SETUP_TAB_ID, kind: SETUP_KIND, clusterId: "" }];
    });
    if (deletedActiveTab) {
      setActiveTabId(SETUP_TAB_ID);
    }
    clearClusterData(deletedClusterId);
  }, [activeTabId, clearClusterData, deleteClusterFromEditor, setActiveTabId, setOpenTabs]);

  useAppEffects({
    activateTab,
    activeKind,
    activeKindNeedsSnapshot,
    activeTabId,
    closeTab,
    clusterEvents,
    clusterSnapshotLoading,
    clusterSnapshots,
    fetchEventPageForCluster,
    fetchSnapshotForCluster,
    hasStoredConnections,
    initialWindowTab,
    openTabs,
    refreshActiveTabFromServer,
    resolvedClusterId,
    setActiveTabId,
    setClockTime,
    setSidebarWidth,
    sidebarResizeRef,
    tabStripRef,
  });

  useEffect(() => {
    logger.info("App mounted", {
      clusterCount: clusters.length,
      resourceCount: controlPlane.resources.length,
      logLevel,
    });
  }, [clusters.length, logLevel]);

  useEffect(() => {
    const isEditableTarget = (target: EventTarget | null): boolean => {
      if (!(target instanceof HTMLElement)) {
        return false;
      }
      const tag = target.tagName.toLowerCase();
      if (tag === "input" || tag === "textarea" || tag === "select") {
        return true;
      }
      return target.isContentEditable;
    };

    const openConsoleTab = () => {
      const consoleTab: ConsoleSubWindowTab = { id: "console", title: "Console", icon: "session", kind: "console" };
      setHorizontalTabs((current) => (current.some((item) => item.id === consoleTab.id) ? current : [...current, consoleTab]));
      setActiveHorizontalTabId("console");
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      const key = event.key;
      const isBackquoteKey = event.code === "Backquote" || key === "`" || key === "~" || key === "ё" || key === "Ё";
      if (!isBackquoteKey) {
        return;
      }
      if (isEditableTarget(event.target)) {
        return;
      }
      event.preventDefault();
      openConsoleTab();
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  const openRbacEditorTab = useCallback((payload: {
    clusterId: string;
    clusterYaml: string;
    kind: string;
    resourceName: string | null;
    yaml: string;
  }) => {
    const resourcePart = payload.resourceName ?? `new-${Date.now()}`;
    const tabId = `rbac:${payload.clusterId}:${payload.kind}:${resourcePart}`;
    const title = payload.resourceName ? payload.resourceName : `Create ${payload.kind}`;
    const icon = iconNameForItem(payload.kind);
    setHorizontalTabs((current) => {
      const existing = current.find((item) => item.id === tabId);
      if (existing) {
        return current;
      }
      const nextTab: RbacSubWindowTab = {
        id: tabId,
        title,
        icon,
        kind: "rbac-editor",
        payload,
        status: null,
      };
      return [...current, nextTab];
    });
    setActiveHorizontalTabId(tabId);
  }, []);

  const reorderHorizontalTabs = useCallback((sourceTabId: string, targetTabId: string) => {
    setHorizontalTabs((current) => {
      const sourceIndex = current.findIndex((tab) => tab.id === sourceTabId);
      const targetIndex = current.findIndex((tab) => tab.id === targetTabId);
      if (sourceIndex === -1 || targetIndex === -1 || sourceIndex === targetIndex) {
        return current;
      }
      return arrayMove(current, sourceIndex, targetIndex);
    });
  }, []);

  const detachHorizontalTab = useCallback(async (tabId: string) => {
    const tab = horizontalTabs.find((item) => item.id === tabId);
    if (!tab) {
      return;
    }
    const tabClusterId = tab.kind === "rbac-editor" ? tab.payload.clusterId : resolvedClusterId;
    const clusterLabel = clusters.find((cluster) => cluster.id === tabClusterId)?.name ?? "";
    const request = tab.kind === "console"
      ? {
          sourceUrl: window.location.href,
          subWindowKind: "console" as const,
          tabIcon: tab.icon,
          tabId: tab.id,
          tabTitle: tab.title,
          clusterId: tabClusterId,
          clusterLabel,
        }
      : {
          sourceUrl: window.location.href,
          subWindowKind: "rbac-editor" as const,
          tabIcon: tab.icon,
          tabId: tab.id,
          tabTitle: tab.title,
          clusterId: tab.payload.clusterId,
          clusterLabel,
          clusterYaml: tab.payload.clusterYaml,
          resourceKind: tab.payload.kind,
          resourceName: tab.payload.resourceName ?? "",
          yaml: tab.payload.yaml,
        };
    try {
      await WindowService.openDetachedHorizontalTabWindow(request);
      setHorizontalTabs((current) => {
        const remaining = current.filter((item) => item.id !== tabId);
        setActiveHorizontalTabId((currentActiveId) => {
          if (currentActiveId !== tabId) {
            return currentActiveId;
          }
          return remaining[remaining.length - 1]?.id ?? "";
        });
        return remaining;
      });
    } catch (error) {
      logger.error("Failed to detach horizontal subwindow tab", { tabId, error });
    }
  }, [clusters, resolvedClusterId]);

  const activeSubWindowTab = horizontalTabs.find((item) => item.id === activeHorizontalTabId) ?? null;

  return (
    <main
      className={`ide-shell ${showSidebar ? "" : "ide-shell--no-sidebar"}`}
      style={{ ["--sidebar-width" as string]: `${sidebarWidth}px` }}
    >
      {showSidebar ? (
        <NavigatorSidebar
          activeClusterId={resolvedClusterId}
          activeKind={activeKind}
          clusterDraftAccent={clusterDraftAccent}
          clusterDraftName={clusterDraftName}
          editingClusterId={editingClusterId}
          expandedClusters={expandedClusters}
          itemsByCluster={filteredItemsByCluster}
          onCloseEditor={() => setEditingClusterId(null)}
          onDeleteCluster={handleDeleteClusterFromEditor}
          onDraftAccentChange={setClusterDraftAccent}
          onDraftNameChange={setClusterDraftName}
          onEditCluster={openClusterConfigEditor}
          onOpenResource={openResource}
          onOpenSettings={openSettingsTab}
          onOpenSetupGuide={openSetupTab}
          onResizeStart={(event) => {
            event.preventDefault();
            sidebarResizeRef.current = { startX: event.clientX, startWidth: sidebarWidth };
            document.body.style.userSelect = "none";
          }}
          onSaveCluster={saveClusterConfigEditor}
          onSearchChange={setSearch}
          onSelectCluster={setActiveClusterId}
          onShareCluster={shareClusterConfigFromEditor}
          onSidebarHide={() => setSidebarVisible(false)}
          onToggleCluster={(clusterId) => {
            logger.debug("Toggling cluster expansion", { clusterId });
            setExpandedClusters((current) => ({ ...current, [clusterId]: !current[clusterId] }));
          }}
          overlayScrollbarOptions={OVERLAY_SCROLLBAR_OPTIONS}
          search={search}
          shareCopyNotice={shareCopyNotice}
          visibleClusters={visibleClusters}
        />
      ) : null}

      <section className="workspace">
        <WorkspaceHeader
          activeTabId={activeTabId}
          clusters={clusters}
          hasStoredConnections={hasStoredConnections}
          onActivateTab={activateTab}
          onCloseTab={closeTab}
          onDragEnd={handleTabDragEnd}
          onShowSidebar={() => setSidebarVisible(true)}
          onTabWheel={handleTabWheel}
          openTabs={openTabs}
          resourcesByKind={resourcesByKind}
          showSidebar={showSidebar}
          tabBarRef={tabBarRef}
          tabSensors={tabSensors}
          tabScrollbarOptions={TAB_SCROLLBAR_OPTIONS}
          tabStripRef={tabStripRef}
        />

        <WorkspaceContent
          activeKind={activeKind}
          activeResourceKind={activeResource?.kind ?? activeKind}
          activeSnapshot={activeSnapshot}
          activeSnapshotError={activeSnapshotError}
          activeSnapshotLoading={activeSnapshotLoading}
          channel={channel}
          checkingUpdates={checkingUpdates}
          clusterEvents={clusterEvents}
          connectingGui={connectingGui}
          guiConnectionStatus={guiConnectionStatus}
          guiConnectionYaml={guiConnectionYaml}
          logLevel={logLevel}
          managingStandalone={managingStandalone}
          onChannelChange={handleChannelChange}
          onCheckUpdates={handleCheckUpdates}
          onConnectGui={handleConnectGui}
          onForceUpdate={handleForceUpdate}
          onInstallStandaloneBundle={handleInstallStandaloneBundle}
          onInstallStandaloneServices={handleInstallStandaloneServices}
          onInstallUpdate={handleInstallUpdate}
          onLoadMoreEvents={() => {
            void fetchEventPageForCluster(resolvedClusterId, "older");
          }}
          onLogLevelChange={handleLogLevelChange}
          onRefreshStandaloneStatus={refreshStandaloneStatus}
          onRetrySnapshot={() => {
            void fetchSnapshotForCluster(resolvedClusterId);
          }}
          onRuntimeArgsChange={setRuntimeArgs}
          onSetControlPlaneArgs={setControlPlaneArgs}
          onOpenRbacEditorTab={openRbacEditorTab}
          onStartStandaloneServices={handleStartStandaloneServices}
          onStopStandaloneServices={handleStopStandaloneServices}
          onTableSearchChange={setTableSearch}
          onYamlChange={setGuiConnectionYaml}
          overlayScrollbarOptions={OVERLAY_SCROLLBAR_OPTIONS}
          resolvedClusterId={resolvedClusterId}
          settingsTabActive={settingsTabActive}
          setupTabActive={setupTabActive}
          standaloneControlPlaneArgs={controlPlaneArgs}
          standaloneRuntimeArgs={runtimeArgs}
          standaloneStatus={standaloneStatus}
          standaloneStatusMessage={standaloneStatusMessage}
          tableSearch={tableSearch}
          tableSchema={activeTableSchema}
          updateStatus={updateStatus}
          useLiveSnapshotTable={useLiveSnapshotTable}
          usesSnapshotSource={activeKindUsesSnapshot}
          warningMessage={activeClusterInconsistency}
        />
        <HorizontalSubWindow
          activeTabId={activeHorizontalTabId}
          onActivateTab={setActiveHorizontalTabId}
          onCloseTab={(tabId) => {
            setHorizontalTabs((current) => {
              const next = current.filter((item) => item.id !== tabId);
              if (activeHorizontalTabId === tabId) {
                setActiveHorizontalTabId(next[next.length - 1]?.id ?? "");
              }
              return next;
            });
          }}
          onDetachTab={(tabId) => {
            void detachHorizontalTab(tabId);
          }}
          onReorderTabs={reorderHorizontalTabs}
          tabs={horizontalTabs}
        >
          {activeSubWindowTab?.kind === "console" ? <AgentConsole /> : null}
          {activeSubWindowTab?.kind === "rbac-editor" ? (
            <RbacEditorTabContent
              applying={applyingSubWindowTabId === activeSubWindowTab.id}
              onApply={() => {
                const tabId = activeSubWindowTab.id;
                const payload = activeSubWindowTab.payload;
                setApplyingSubWindowTabId(tabId);
                setHorizontalTabs((current) =>
                  current.map((item) => (item.id === tabId && item.kind === "rbac-editor" ? { ...item, status: null } : item)),
                );
                void ClusterConnectionService.applyRbacYamlResource(payload.clusterYaml, payload.yaml, false)
                  .then(() => {
                    setHorizontalTabs((current) =>
                      current.map((item) => (
                        item.id === tabId && item.kind === "rbac-editor"
                          ? { ...item, status: "Applied YAML successfully." }
                          : item
                      )),
                    );
                  })
                  .catch((error: unknown) => {
                    const message = error instanceof Error ? error.message : "Failed to apply YAML.";
                    setHorizontalTabs((current) =>
                      current.map((item) => (
                        item.id === tabId && item.kind === "rbac-editor"
                          ? { ...item, status: message }
                          : item
                      )),
                    );
                  })
                  .finally(() => {
                    setApplyingSubWindowTabId("");
                  });
              }}
              onYamlChange={(value) => {
                const tabId = activeSubWindowTab.id;
                setHorizontalTabs((current) =>
                  current.map((item) => (
                    item.id === tabId && item.kind === "rbac-editor"
                      ? { ...item, payload: { ...item.payload, yaml: value } }
                      : item
                  )),
                );
              }}
              status={activeSubWindowTab.status}
              yaml={activeSubWindowTab.payload.yaml}
            />
          ) : null}
        </HorizontalSubWindow>
      </section>

      <StatusBar
        activeClusterUserId={activeClusterUserId}
        clockTime={clockTime}
        hasDataFetchError={hasDataFetchError}
        isDataFetching={isDataFetching}
      />
    </main>
  );
}

export default App;
