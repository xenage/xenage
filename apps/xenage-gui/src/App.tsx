import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import "overlayscrollbars/overlayscrollbars.css";
import "./App.css";
import { parseInitialWindowTab } from "./modules/tabs/windowState";
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

function App() {
  const initialWindowTab = useMemo(() => parseInitialWindowTab(window.location.href), []);

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
