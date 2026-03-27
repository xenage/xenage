import { fireEvent, render, screen } from "@testing-library/react";
import { vi } from "vitest";
import App from "./App";

vi.mock("./modules/tabs/windowState", () => ({
  parseInitialWindowTab: () => null,
  parseInitialHorizontalWindowTab: () => null,
}));

vi.mock("./modules/app/hooks/useClusterConnections", () => ({
  useClusterConnections: () => ({
    activeClusterId: "cluster-1",
    clusterDraftAccent: "#22c55e",
    clusterDraftName: "main",
    clusters: [{ id: "cluster-1", name: "main", accent: "#22c55e" }],
    connectGui: vi.fn(async () => null),
    connectingGui: false,
    connectionConfigs: [{ id: "cluster-1", name: "main", yaml: "cluster: main" }],
    deleteClusterFromEditor: vi.fn(async () => null),
    editingClusterId: null,
    expandedClusters: { "cluster-1": true },
    guiConnectionStatus: null,
    guiConnectionYaml: "cluster: main",
    openClusterConfigEditor: vi.fn(),
    saveClusterConfigEditor: vi.fn(async () => {}),
    setActiveClusterId: vi.fn(),
    setClusterDraftAccent: vi.fn(),
    setClusterDraftName: vi.fn(),
    setConnectionConfigs: vi.fn(),
    setEditingClusterId: vi.fn(),
    setExpandedClusters: vi.fn(),
    setGuiConnectionYaml: vi.fn(),
    shareClusterConfigFromEditor: vi.fn(async () => {}),
    shareCopyNotice: null,
  }),
}));

vi.mock("./modules/app/hooks/useTabManager", () => ({
  useTabManager: () => ({
    activateTab: vi.fn(),
    activeTabId: "cluster-1:Role",
    closeTab: vi.fn(),
    handleTabDragEnd: vi.fn(),
    handleTabWheel: vi.fn(),
    openResource: vi.fn(),
    openSettingsTab: vi.fn(),
    openSetupTab: vi.fn(),
    openTabs: [{ id: "cluster-1:Role", kind: "Role", clusterId: "cluster-1" }],
    setActiveTabId: vi.fn(),
    setOpenTabs: vi.fn(),
    tabBarRef: { current: null },
    tabSensors: [],
    tabStripRef: { current: null },
  }),
}));

vi.mock("./modules/app/hooks/useClusterData", () => ({
  useClusterData: () => ({
    clearClusterData: vi.fn(),
    clusterEvents: {},
    clusterSnapshotErrors: {},
    clusterSnapshotLoading: {},
    clusterSnapshots: {},
    fetchEventPageForCluster: vi.fn(async () => true),
    fetchSnapshotForCluster: vi.fn(async () => true),
    hasDataFetchError: false,
    isDataFetching: false,
    setClusterEvents: vi.fn(),
    setClusterSnapshotErrors: vi.fn(),
    setClusterSnapshots: vi.fn(),
  }),
}));

vi.mock("./modules/app/hooks/useMaintenanceSettings", () => ({
  useMaintenanceSettings: () => ({
    channel: "main",
    checkingUpdates: false,
    controlPlaneArgs: "",
    handleChannelChange: vi.fn(),
    handleCheckUpdates: vi.fn(async () => {}),
    handleForceUpdate: vi.fn(async () => {}),
    handleInstallStandaloneBundle: vi.fn(async () => {}),
    handleInstallStandaloneServices: vi.fn(async () => {}),
    handleInstallUpdate: vi.fn(async () => {}),
    handleLogLevelChange: vi.fn(),
    handleStartStandaloneServices: vi.fn(async () => {}),
    handleStopStandaloneServices: vi.fn(async () => {}),
    logLevel: "info",
    managingStandalone: false,
    refreshStandaloneStatus: vi.fn(async () => null),
    runtimeArgs: "",
    setControlPlaneArgs: vi.fn(),
    setRuntimeArgs: vi.fn(),
    standaloneStatus: null,
    standaloneStatusMessage: null,
    updateStatus: null,
  }),
}));

vi.mock("./modules/app/hooks/useAppEffects", () => ({
  useAppEffects: vi.fn(),
}));

vi.mock("./modules/app/hooks/useAppViewModel", () => ({
  useAppViewModel: () => ({
    activeClusterInconsistency: null,
    activeClusterUserId: "user-1",
    activeKind: "Role",
    activeKindNeedsSnapshot: false,
    activeKindUsesSnapshot: false,
    activeResource: { kind: "Role" },
    activeSnapshot: undefined,
    activeSnapshotError: null,
    activeSnapshotLoading: false,
    activeTableSchema: {
      kind: "Role",
      title: "Role",
      source: "rbac.roles",
      rowKind: "Role",
      rowKey: "name",
      defaultSort: { field: "name", direction: "asc" },
      columns: [],
      sample: {},
    },
    filteredItemsByCluster: { "cluster-1": [] },
    hasStoredConnections: true,
    resolvedClusterId: "cluster-1",
    resourcesByKind: new Map(),
    settingsTabActive: false,
    setupTabActive: false,
    useLiveSnapshotTable: false,
    visibleClusters: [{ id: "cluster-1", name: "main", accent: "#22c55e" }],
  }),
}));

vi.mock("./modules/app/components/NavigatorSidebar", () => ({
  NavigatorSidebar: () => <div data-testid="navigator-sidebar" />,
}));

vi.mock("./modules/app/components/WorkspaceHeader", () => ({
  WorkspaceHeader: () => <div data-testid="workspace-header" />,
}));

vi.mock("./modules/app/components/WorkspaceContent", () => ({
  WorkspaceContent: ({
    onOpenRbacEditorTab,
  }: {
    onOpenRbacEditorTab: (payload: {
      clusterId: string;
      clusterYaml: string;
      kind: string;
      resourceName: string | null;
      yaml: string;
    }) => void;
  }) => (
    <div>
      <button
        onClick={() => onOpenRbacEditorTab({
          clusterId: "cluster-1",
          clusterYaml: "cluster: main",
          kind: "Role",
          resourceName: "viewer",
          yaml: "kind: Role\nmetadata:\n  name: viewer\n",
        })}
        type="button"
      >
        Open Role Editor
      </button>
      <button
        onClick={() => onOpenRbacEditorTab({
          clusterId: "cluster-1",
          clusterYaml: "cluster: main",
          kind: "User",
          resourceName: "alice",
          yaml: "kind: ServiceAccount\nmetadata:\n  name: alice\n",
        })}
        type="button"
      >
        Open User Editor
      </button>
    </div>
  ),
}));

vi.mock("./modules/app/components/StatusBar", () => ({
  StatusBar: () => <div data-testid="status-bar" />,
}));

vi.mock("./modules/app/components/AgentConsole", () => ({
  AgentConsole: () => <div data-testid="agent-console">console body</div>,
}));

vi.mock("./modules/rbac/RbacEditorTabContent", () => ({
  RbacEditorTabContent: ({ yaml }: { yaml: string }) => <div data-testid="rbac-editor-content">{yaml}</div>,
}));

describe("App horizontal subwindow", () => {
  it("keeps one subwindow and preserves tabs across RBAC resource switches", () => {
    const { container } = render(<App />);

    fireEvent.keyDown(window, { code: "Backquote", key: "`" });
    fireEvent.click(screen.getByRole("button", { name: "Open Role Editor" }));
    fireEvent.click(screen.getByRole("button", { name: "Open User Editor" }));

    const subwindows = container.querySelectorAll(".horizontal-subwindow");
    expect(subwindows).toHaveLength(1);

    const tabs = container.querySelectorAll(".horizontal-subwindow__tab");
    expect(tabs).toHaveLength(3);

    expect(screen.getByText("Console")).toBeInTheDocument();
    expect(screen.getByText("viewer")).toBeInTheDocument();
    expect(screen.getByText("alice")).toBeInTheDocument();
  });
});
