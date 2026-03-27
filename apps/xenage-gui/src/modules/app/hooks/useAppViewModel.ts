import { useMemo } from "react";
import type { StoredClusterConnection } from "../../../services/clusterConnection";
import type { ManifestResource, ManifestTable, NavigationLeaf } from "../../../types/controlPlane";
import type { GuiClusterSnapshot } from "../../../types/guiConnection";
import type { OpenTab } from "../../tabs/types";
import {
  SETTINGS_TAB_ID,
  SETUP_TAB_ID,
  controlPlane,
} from "../constants";
import type { ClusterEntry } from "../types";
import { extractClusterUserId } from "../utils";

type UseAppViewModelArgs = {
  activeClusterId: string;
  activeTabId: string;
  clusterSnapshotErrors: Record<string, string>;
  clusterSnapshotLoading: Record<string, boolean>;
  clusterSnapshots: Record<string, GuiClusterSnapshot>;
  clusters: ClusterEntry[];
  connectionConfigs: StoredClusterConnection[];
  openTabs: OpenTab[];
  search: string;
};

type UseAppViewModelResult = {
  activeClusterInconsistency: string | null;
  activeClusterUserId: string | null;
  activeKind: string;
  activeKindNeedsSnapshot: boolean;
  activeKindUsesSnapshot: boolean;
  activeResource: ManifestResource | null;
  activeSnapshot: GuiClusterSnapshot | undefined;
  activeSnapshotError: string | null;
  activeSnapshotLoading: boolean;
  activeTableSchema: ManifestTable | null;
  filteredItemsByCluster: Record<string, NavigationLeaf[]>;
  hasStoredConnections: boolean;
  resolvedClusterId: string;
  resourcesByKind: Map<string, ManifestResource>;
  settingsTabActive: boolean;
  setupTabActive: boolean;
  useLiveSnapshotTable: boolean;
  visibleClusters: ClusterEntry[];
};

export function useAppViewModel({
  activeClusterId,
  activeTabId,
  clusterSnapshotErrors,
  clusterSnapshotLoading,
  clusterSnapshots,
  clusters,
  connectionConfigs,
  openTabs,
  search,
}: UseAppViewModelArgs): UseAppViewModelResult {
  const resourcesByKind = useMemo(
    () => new Map(controlPlane.resources.map((resource) => [resource.kind, resource])),
    [],
  );

  const tablesByKind = useMemo(
    () => new Map(controlPlane.tables.map((table) => [table.kind, table])),
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

  const normalizedSearch = useMemo(() => search.trim().toLowerCase(), [search]);

  const filteredItemsByCluster = useMemo(
    () =>
      clusters.reduce<Record<string, NavigationLeaf[]>>((acc, cluster) => {
        const items = itemsByCluster[cluster.id] ?? [];
        acc[cluster.id] = !normalizedSearch
          ? items
          : items.filter((item) => item.label.toLowerCase().includes(normalizedSearch));
        return acc;
      }, {}),
    [clusters, itemsByCluster, normalizedSearch],
  );

  const visibleClusters = useMemo(() => {
    return clusters.filter((cluster) => {
      if (!normalizedSearch) {
        return true;
      }
      const matchesCluster = cluster.name.toLowerCase().includes(normalizedSearch);
      const matchingItems = filteredItemsByCluster[cluster.id] ?? [];
      return matchesCluster || matchingItems.length > 0;
    });
  }, [clusters, filteredItemsByCluster, normalizedSearch]);

  const activeTab = openTabs.find((tab) => tab.id === activeTabId) ?? openTabs[0];
  const setupTabActive = activeTab?.id === SETUP_TAB_ID;
  const settingsTabActive = activeTab?.id === SETTINGS_TAB_ID;
  const activeKind = activeTab?.kind ?? "Node";
  const resolvedClusterId = activeTab?.clusterId || activeClusterId || clusters[0]?.id || "";
  const activeResource = settingsTabActive || setupTabActive
    ? null
    : resourcesByKind.get(activeKind) ?? controlPlane.resources[0];
  const activeTableSchema: ManifestTable | null = settingsTabActive || setupTabActive
    ? null
    : tablesByKind.get(activeKind) ?? null;
  const activeKindUsesSnapshot = activeTableSchema?.source.startsWith("snapshot.") ?? false;
  const activeKindNeedsSnapshot = activeKindUsesSnapshot || activeKind === "Event";
  const hasStoredConnections = clusters.length > 0;
  const activeSnapshot = clusterSnapshots[resolvedClusterId];
  const activeSnapshotError = clusterSnapshotErrors[resolvedClusterId] ?? null;
  const activeSnapshotLoading = clusterSnapshotLoading[resolvedClusterId] ?? false;
  const activeClusterInconsistency = useMemo(() => {
    if (!activeSnapshot) {
      return null;
    }
    const value = activeSnapshot.group_config.find((item) => item.key === "control_plane_sync_reason")?.value
      ?? activeSnapshot.group_config.find((item) => item.key === "user_state_sync_inconsistency_reason")?.value
      ?? "";
    if (!value || value === "-") {
      return null;
    }
    return value;
  }, [activeSnapshot]);

  const activeClusterUserId = useMemo(() => {
    const activeConnection = connectionConfigs.find((item) => item.id === resolvedClusterId);
    if (!activeConnection) {
      return null;
    }
    return extractClusterUserId(activeConnection.yaml);
  }, [connectionConfigs, resolvedClusterId]);

  const useLiveSnapshotTable = Boolean(activeSnapshot && activeKindUsesSnapshot && activeTableSchema);

  return {
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
  };
}
