import { OverlayScrollbarsComponent } from "overlayscrollbars-react";
import type { PartialOptions } from "overlayscrollbars";
import { EventTable } from "../../events/EventTable";
import { GroupConfigTable } from "../../group-config/GroupConfigTable";
import { NodeTable } from "../../nodes/NodeTable";
import { Icon } from "../../../components/Icon";
import type { ManifestTable } from "../../../types/controlPlane";
import type { GuiClusterSnapshot } from "../../../types/guiConnection";
import type { ClusterEventCache } from "../types";
import { ApiFetchStateTable, ApiUnavailableTable } from "./ApiStateTables";
import { SettingsView } from "./SettingsView";
import { SetupGuideView } from "./SetupGuideView";
import type { LogLevel } from "../../../services/logger";
import type { StandaloneStatus } from "../../../services/standalone";
import type { UpdateChannel } from "../../../services/update";

type WorkspaceContentProps = {
  activeKind: string;
  activeResourceKind: string;
  activeSnapshot: GuiClusterSnapshot | undefined;
  activeSnapshotError: string | null;
  activeSnapshotLoading: boolean;
  channel: UpdateChannel;
  checkingUpdates: boolean;
  clusterEvents: Record<string, ClusterEventCache>;
  connectingGui: boolean;
  guiConnectionStatus: string | null;
  guiConnectionYaml: string;
  logLevel: LogLevel;
  managingStandalone: boolean;
  onChannelChange: (channel: UpdateChannel) => void;
  onCheckUpdates: () => Promise<void>;
  onConnectGui: () => Promise<void>;
  onForceUpdate: () => Promise<void>;
  onInstallStandaloneBundle: () => Promise<void>;
  onInstallStandaloneServices: () => Promise<void>;
  onInstallUpdate: () => Promise<void>;
  onLoadMoreEvents: () => void;
  onLogLevelChange: (level: LogLevel) => void;
  onRefreshStandaloneStatus: () => Promise<StandaloneStatus | null>;
  onRetrySnapshot: () => void;
  onRuntimeArgsChange: (value: string) => void;
  onSetControlPlaneArgs: (value: string) => void;
  onStartStandaloneServices: () => Promise<void>;
  onStopStandaloneServices: () => Promise<void>;
  onTableSearchChange: (value: string) => void;
  onYamlChange: (value: string) => void;
  overlayScrollbarOptions: PartialOptions;
  resolvedClusterId: string;
  settingsTabActive: boolean;
  setupTabActive: boolean;
  standaloneControlPlaneArgs: string;
  standaloneRuntimeArgs: string;
  standaloneStatus: StandaloneStatus | null;
  standaloneStatusMessage: string | null;
  tableSearch: string;
  tableSchema: ManifestTable | null;
  updateStatus: string | null;
  useLiveSnapshotTable: boolean;
  usesSnapshotSource: boolean;
  warningMessage: string | null;
};

export function WorkspaceContent({
  activeKind,
  activeResourceKind,
  activeSnapshot,
  activeSnapshotError,
  activeSnapshotLoading,
  channel,
  checkingUpdates,
  clusterEvents,
  connectingGui,
  guiConnectionStatus,
  guiConnectionYaml,
  logLevel,
  managingStandalone,
  onChannelChange,
  onCheckUpdates,
  onConnectGui,
  onForceUpdate,
  onInstallStandaloneBundle,
  onInstallStandaloneServices,
  onInstallUpdate,
  onLoadMoreEvents,
  onLogLevelChange,
  onRefreshStandaloneStatus,
  onRetrySnapshot,
  onRuntimeArgsChange,
  onSetControlPlaneArgs,
  onStartStandaloneServices,
  onStopStandaloneServices,
  onTableSearchChange,
  onYamlChange,
  overlayScrollbarOptions,
  resolvedClusterId,
  settingsTabActive,
  setupTabActive,
  standaloneControlPlaneArgs,
  standaloneRuntimeArgs,
  standaloneStatus,
  standaloneStatusMessage,
  tableSearch,
  tableSchema,
  updateStatus,
  useLiveSnapshotTable,
  usesSnapshotSource,
  warningMessage,
}: WorkspaceContentProps) {
  return (
    <OverlayScrollbarsComponent
      className={`workspace__content scroll-host ${!settingsTabActive && !setupTabActive ? "workspace__content--compact" : ""}`}
      options={overlayScrollbarOptions}
    >
      {settingsTabActive ? (
        <SettingsView
          channel={channel}
          checkingUpdates={checkingUpdates}
          logLevel={logLevel}
          onChannelChange={onChannelChange}
          onCheckUpdates={onCheckUpdates}
          onForceUpdate={onForceUpdate}
          onInstallStandaloneBundle={onInstallStandaloneBundle}
          onInstallStandaloneServices={onInstallStandaloneServices}
          onInstallUpdate={onInstallUpdate}
          onLogLevelChange={onLogLevelChange}
          onRefreshStandaloneStatus={onRefreshStandaloneStatus}
          onStartStandaloneServices={onStartStandaloneServices}
          onStopStandaloneServices={onStopStandaloneServices}
          onUpdateControlPlaneArgs={onSetControlPlaneArgs}
          onUpdateRuntimeArgs={onRuntimeArgsChange}
          standaloneBusy={managingStandalone}
          standaloneControlPlaneArgs={standaloneControlPlaneArgs}
          standaloneRuntimeArgs={standaloneRuntimeArgs}
          standaloneStatus={standaloneStatus}
          standaloneStatusMessage={standaloneStatusMessage}
          updateStatus={updateStatus}
        />
      ) : setupTabActive ? (
        <SetupGuideView
          connectingGui={connectingGui}
          guiConnectionStatus={guiConnectionStatus}
          guiConnectionYaml={guiConnectionYaml}
          onConnect={onConnectGui}
          onYamlChange={onYamlChange}
        />
      ) : (
        <div className="resource-pane">
          <div className="workspace__table-toolbar">
            <label className="search-box search-box--table">
              <span className="search-box__icon">
                <Icon name="search" />
              </span>
              <input
                aria-label="Filter table rows"
                onChange={(event) => onTableSearchChange(event.target.value)}
                placeholder="Filter rows"
                value={tableSearch}
              />
            </label>
          </div>
          {warningMessage ? (
            <div className="workspace__warning">{warningMessage}</div>
          ) : null}
          {activeKind === "Event" && tableSchema ? (
            <EventTable
              hasMore={clusterEvents[resolvedClusterId]?.hasMore ?? false}
              loadingMore={clusterEvents[resolvedClusterId]?.loading ?? false}
              onLoadMore={onLoadMoreEvents}
              rows={clusterEvents[resolvedClusterId]?.items ?? []}
              searchTerm={tableSearch}
              tableSchema={tableSchema}
            />
          ) : useLiveSnapshotTable ? (
            activeKind === "Node" ? (
              <NodeTable
                rows={activeSnapshot!.nodes}
                searchTerm={tableSearch}
                tableSchema={tableSchema!}
              />
            ) : activeKind === "GroupConfig" ? (
              <GroupConfigTable
                rows={activeSnapshot!.group_config}
                searchTerm={tableSearch}
                tableSchema={tableSchema!}
              />
            ) : (
              <ApiUnavailableTable kind={activeKind} />
            )
          ) : usesSnapshotSource ? (
            <ApiFetchStateTable
              error={activeSnapshotError}
              kind={activeKind}
              loading={activeSnapshotLoading}
              onRetry={onRetrySnapshot}
            />
          ) : (
            <ApiUnavailableTable kind={activeResourceKind} />
          )}
        </div>
      )}
    </OverlayScrollbarsComponent>
  );
}
