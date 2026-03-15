import { fireEvent, render, screen } from "@testing-library/react";
import type { ComponentProps } from "react";
import { vi } from "vitest";
import type { ManifestTable } from "../../../types/controlPlane";
import { WorkspaceContent } from "./WorkspaceContent";

vi.mock("../../events/EventTable", () => ({
  EventTable: ({ searchTerm }: { searchTerm: string }) => (
    <div data-testid="event-table">event-table:{searchTerm}</div>
  ),
}));

vi.mock("../../nodes/NodeTable", () => ({
  NodeTable: ({ searchTerm }: { searchTerm: string }) => (
    <div data-testid="node-table">node-table:{searchTerm}</div>
  ),
}));

vi.mock("../../group-config/GroupConfigTable", () => ({
  GroupConfigTable: ({ searchTerm }: { searchTerm: string }) => (
    <div data-testid="group-config-table">group-config-table:{searchTerm}</div>
  ),
}));

vi.mock("./SettingsView", () => ({
  SettingsView: ({ channel }: { channel: string }) => (
    <div data-testid="settings-view">settings-view:{channel}</div>
  ),
}));

vi.mock("./SetupGuideView", () => ({
  SetupGuideView: ({ guiConnectionStatus }: { guiConnectionStatus: string | null }) => (
    <div data-testid="setup-guide-view">setup-guide:{guiConnectionStatus ?? "none"}</div>
  ),
}));

const defaultTableSchema: ManifestTable = {
  kind: "Node",
  title: "Node",
  source: "snapshot.nodes",
  rowKind: "Node",
  rowKey: "node_id",
  defaultSort: {
    field: "node_id",
    direction: "asc",
  },
  columns: [
    {
      key: "node_id",
      label: "Node ID",
      path: "node_id",
      type: "str",
      isArray: false,
      width: 180,
      minWidth: 120,
      displayOnly: false,
    },
  ],
  sample: {},
};

function createProps(
  overrides: Partial<ComponentProps<typeof WorkspaceContent>> = {},
): ComponentProps<typeof WorkspaceContent> {
  return {
    activeKind: "Node",
    activeResourceKind: "Node",
    activeSnapshot: {
      group_id: "group-1",
      state_version: 1,
      leader_epoch: 1,
      nodes: [
        {
          node_id: "cp-1",
          role: "control-plane",
          leader: true,
          public_key: "pub-1",
          endpoints: ["http://127.0.0.1:8734"],
          status: "Connected",
        },
      ],
      group_config: [
        {
          key: "control_plane_sync_reason",
          value: "-",
        },
      ],
      users: [],
    },
    activeSnapshotError: null,
    activeSnapshotLoading: false,
    channel: "main",
    checkingUpdates: false,
    clusterEvents: {
      "cluster-1": {
        hasMore: true,
        items: [],
        loading: false,
        oldestSequence: null,
      },
    },
    connectingGui: false,
    guiConnectionStatus: null,
    guiConnectionYaml: "",
    logLevel: "info",
    managingStandalone: false,
    onChannelChange: vi.fn(),
    onCheckUpdates: vi.fn(async () => {}),
    onConnectGui: vi.fn(async () => {}),
    onForceUpdate: vi.fn(async () => {}),
    onInstallStandaloneBundle: vi.fn(async () => {}),
    onInstallStandaloneServices: vi.fn(async () => {}),
    onInstallUpdate: vi.fn(async () => {}),
    onLoadMoreEvents: vi.fn(),
    onLogLevelChange: vi.fn(),
    onRefreshStandaloneStatus: vi.fn(async () => null),
    onRetrySnapshot: vi.fn(),
    onRuntimeArgsChange: vi.fn(),
    onSetControlPlaneArgs: vi.fn(),
    onStartStandaloneServices: vi.fn(async () => {}),
    onStopStandaloneServices: vi.fn(async () => {}),
    onTableSearchChange: vi.fn(),
    onYamlChange: vi.fn(),
    overlayScrollbarOptions: {},
    resolvedClusterId: "cluster-1",
    settingsTabActive: false,
    setupTabActive: false,
    standaloneControlPlaneArgs: "",
    standaloneRuntimeArgs: "",
    standaloneStatus: null,
    standaloneStatusMessage: null,
    tableSearch: "",
    tableSchema: defaultTableSchema,
    updateStatus: null,
    useLiveSnapshotTable: true,
    usesSnapshotSource: true,
    warningMessage: null,
    ...overrides,
  };
}

describe("WorkspaceContent", () => {
  it("renders settings page when settings tab is active", () => {
    render(<WorkspaceContent {...createProps({ settingsTabActive: true })} />);

    expect(screen.getByTestId("settings-view")).toBeInTheDocument();
    expect(screen.queryByTestId("setup-guide-view")).not.toBeInTheDocument();
  });

  it("renders setup page when setup tab is active", () => {
    render(
      <WorkspaceContent
        {...createProps({
          setupTabActive: true,
          guiConnectionStatus: "Paste config",
        })}
      />,
    );

    expect(screen.getByTestId("setup-guide-view")).toHaveTextContent("setup-guide:Paste config");
    expect(screen.queryByTestId("settings-view")).not.toBeInTheDocument();
  });

  it("renders event page and updates table search input", () => {
    const props = createProps({
      activeKind: "Event",
      tableSearch: "initial",
      warningMessage: "Detected state inconsistency",
    });

    render(<WorkspaceContent {...props} />);

    expect(screen.getByTestId("event-table")).toHaveTextContent("event-table:initial");
    expect(screen.getByText("Detected state inconsistency")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Filter table rows"), { target: { value: "error" } });
    expect(props.onTableSearchChange).toHaveBeenCalledWith("error");
  });

  it("renders live snapshot node page", () => {
    render(<WorkspaceContent {...createProps({ activeKind: "Node" })} />);

    expect(screen.getByTestId("node-table")).toBeInTheDocument();
  });

  it("renders live snapshot group config page", () => {
    render(<WorkspaceContent {...createProps({ activeKind: "GroupConfig" })} />);

    expect(screen.getByTestId("group-config-table")).toBeInTheDocument();
  });

  it("shows unavailable table when live snapshot kind is unsupported", () => {
    render(<WorkspaceContent {...createProps({ activeKind: "User" })} />);

    expect(screen.getByText(/No schema fallback for User/)).toBeInTheDocument();
  });

  it("shows API loading state when snapshot data is still fetching", () => {
    render(
      <WorkspaceContent
        {...createProps({
          useLiveSnapshotTable: false,
          usesSnapshotSource: true,
          activeSnapshotLoading: true,
        })}
      />,
    );

    expect(screen.getByText("Loading Node from API...")).toBeInTheDocument();
  });

  it("shows API error state and allows retry", () => {
    const props = createProps({
      useLiveSnapshotTable: false,
      usesSnapshotSource: true,
      activeSnapshotLoading: false,
      activeSnapshotError: "network timeout",
    });

    render(<WorkspaceContent {...props} />);

    expect(screen.getByText("API error: network timeout")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retry API" }));
    expect(props.onRetrySnapshot).toHaveBeenCalledTimes(1);
  });

  it("shows resource fallback when tab does not use snapshot source", () => {
    render(
      <WorkspaceContent
        {...createProps({
          useLiveSnapshotTable: false,
          usesSnapshotSource: false,
          activeKind: "Dashboard",
          activeResourceKind: "CustomResource",
        })}
      />,
    );

    expect(screen.getByText(/No schema fallback for CustomResource/)).toBeInTheDocument();
  });
});
