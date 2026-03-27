import { useCallback, useEffect, useRef, useState } from "react";
import type { Dispatch, SetStateAction } from "react";
import { ClusterConnectionService } from "../../../services/clusterConnection";
import type { StoredClusterConnection } from "../../../services/clusterConnection";
import { logger } from "../../../services/logger";
import type { GuiClusterSnapshot } from "../../../types/guiConnection";
import type { ClusterEventCache, EventFetchMode } from "../types";
import { controlPlaneUrlsFromSnapshot } from "../utils";
import { useDataFetchIndicator } from "./useDataFetchIndicator";

type UseClusterDataArgs = {
  connectionConfigs: StoredClusterConnection[];
  eventPageSize: number;
  setConnectionConfigs: Dispatch<SetStateAction<StoredClusterConnection[]>>;
};

type UseClusterDataResult = {
  clearClusterData: (clusterId: string) => void;
  clusterEvents: Record<string, ClusterEventCache>;
  clusterSnapshotErrors: Record<string, string>;
  clusterSnapshotLoading: Record<string, boolean>;
  clusterSnapshots: Record<string, GuiClusterSnapshot>;
  fetchEventPageForCluster: (clusterId: string, mode?: EventFetchMode) => Promise<boolean>;
  fetchSnapshotForCluster: (clusterId: string) => Promise<boolean>;
  hasDataFetchError: boolean;
  isDataFetching: boolean;
  setClusterEvents: Dispatch<SetStateAction<Record<string, ClusterEventCache>>>;
  setClusterSnapshotErrors: Dispatch<SetStateAction<Record<string, string>>>;
  setClusterSnapshots: Dispatch<SetStateAction<Record<string, GuiClusterSnapshot>>>;
};

export function useClusterData({
  connectionConfigs,
  eventPageSize,
  setConnectionConfigs,
}: UseClusterDataArgs): UseClusterDataResult {
  const clusterEventsRef = useRef<Record<string, ClusterEventCache>>({});
  const clusterEventLoadingRef = useRef<Record<string, boolean>>({});
  const [clusterSnapshots, setClusterSnapshots] = useState<Record<string, GuiClusterSnapshot>>({});
  const [clusterEvents, setClusterEvents] = useState<Record<string, ClusterEventCache>>({});
  const [clusterSnapshotErrors, setClusterSnapshotErrors] = useState<Record<string, string>>({});
  const [clusterSnapshotLoading, setClusterSnapshotLoading] = useState<Record<string, boolean>>({});
  const {
    beginDataFetch,
    endDataFetch,
    hasDataFetchError,
    isDataFetching,
    markDataFetchError,
  } = useDataFetchIndicator();

  useEffect(() => {
    clusterEventsRef.current = clusterEvents;
  }, [clusterEvents]);

  const syncClusterControlPlaneUrls = useCallback(async (clusterId: string, snapshot: GuiClusterSnapshot) => {
    const discoveredUrls = controlPlaneUrlsFromSnapshot(snapshot);
    if (discoveredUrls.length === 0) {
      return;
    }
    try {
      const updated = await ClusterConnectionService.syncControlPlaneUrls(clusterId, discoveredUrls);
      setConnectionConfigs((current) => {
        let changed = false;
        const next = current.map((item) => {
          if (item.id !== clusterId) {
            return item;
          }
          if (item.yaml === updated.yaml && item.name === updated.name) {
            return item;
          }
          changed = true;
          return updated;
        });
        return changed ? next : current;
      });
    } catch (error) {
      logger.warn("Failed to sync control plane URLs into cluster config", { clusterId, error });
    }
  }, [setConnectionConfigs]);

  const fetchSnapshotForCluster = useCallback(async (clusterId: string): Promise<boolean> => {
    if (!clusterId) {
      return false;
    }
    const connection = connectionConfigs.find((item) => item.id === clusterId);
    if (!connection) {
      return false;
    }

    setClusterSnapshotLoading((current) => ({ ...current, [clusterId]: true }));
    setClusterSnapshotErrors((current) => ({ ...current, [clusterId]: "" }));
    beginDataFetch();
    try {
      const snapshot = await ClusterConnectionService.fetchSnapshotFromYaml(connection.yaml);
      setClusterSnapshots((current) => ({ ...current, [clusterId]: snapshot }));
      void syncClusterControlPlaneUrls(clusterId, snapshot);
      return true;
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to fetch cluster snapshot.";
      setClusterSnapshotErrors((current) => ({ ...current, [clusterId]: message }));
      logger.error("Failed to fetch cluster snapshot", { clusterId, error });
      markDataFetchError();
      return false;
    } finally {
      setClusterSnapshotLoading((current) => ({ ...current, [clusterId]: false }));
      endDataFetch();
    }
  }, [
    beginDataFetch,
    connectionConfigs,
    endDataFetch,
    markDataFetchError,
    syncClusterControlPlaneUrls,
  ]);

  const fetchEventPageForCluster = useCallback(async (clusterId: string, mode: EventFetchMode = "older"): Promise<boolean> => {
    const connection = connectionConfigs.find((item) => item.id === clusterId);
    if (!connection) {
      return false;
    }
    if (clusterEventLoadingRef.current[clusterId]) {
      return false;
    }

    const currentCache = clusterEventsRef.current[clusterId];
    const beforeSequence = mode === "older" ? currentCache?.oldestSequence ?? undefined : undefined;
    if (mode === "older" && currentCache && !currentCache.hasMore) {
      return false;
    }

    clusterEventLoadingRef.current[clusterId] = true;
    beginDataFetch();
    setClusterEvents((current) => {
      const nextEntry: ClusterEventCache = {
        hasMore: current[clusterId]?.hasMore ?? true,
        items: current[clusterId]?.items ?? [],
        loading: true,
        oldestSequence: current[clusterId]?.oldestSequence ?? null,
      };
      const next = {
        ...current,
        [clusterId]: nextEntry,
      };
      clusterEventsRef.current = next;
      return next;
    });

    try {
      const page = await ClusterConnectionService.fetchEventPageFromYaml(
        connection.yaml,
        beforeSequence,
        eventPageSize,
      );
      setClusterEvents((current) => {
        const existing = current[clusterId];
        const existingItems = existing?.items ?? [];
        const existingSequences = new Set(existingItems.map((item) => item.sequence));
        const incomingItems = page.items.filter((item) => !existingSequences.has(item.sequence));
        const hasExistingItems = existingItems.length > 0;
        const nextItems = mode === "older"
          ? [...existingItems, ...incomingItems]
          : hasExistingItems
            ? [...incomingItems, ...existingItems]
            : page.items;
        const hasMore = mode === "older"
          ? page.has_more
          : hasExistingItems
            ? existing?.hasMore ?? page.has_more
            : page.has_more;
        const oldestSequence = nextItems.length === 0
          ? null
          : nextItems.reduce(
            (min, item) => (item.sequence < min ? item.sequence : min),
            nextItems[0].sequence,
          );
        const next = {
          ...current,
          [clusterId]: {
            hasMore,
            items: nextItems,
            loading: false,
            oldestSequence,
          },
        };
        clusterEventsRef.current = next;
        return next;
      });
      return true;
    } catch (error) {
      logger.error("Failed to fetch event page", { clusterId, error });
      markDataFetchError();
      setClusterEvents((current) => {
        const nextEntry: ClusterEventCache = {
          hasMore: current[clusterId]?.hasMore ?? true,
          items: current[clusterId]?.items ?? [],
          loading: false,
          oldestSequence: current[clusterId]?.oldestSequence ?? null,
        };
        const next = {
          ...current,
          [clusterId]: nextEntry,
        };
        clusterEventsRef.current = next;
        return next;
      });
      return false;
    } finally {
      clusterEventLoadingRef.current[clusterId] = false;
      endDataFetch();
    }
  }, [beginDataFetch, connectionConfigs, endDataFetch, eventPageSize, markDataFetchError]);

  const clearClusterData = useCallback((clusterId: string) => {
    setClusterSnapshots((current) => {
      const next = { ...current };
      delete next[clusterId];
      return next;
    });
    setClusterSnapshotErrors((current) => {
      const next = { ...current };
      delete next[clusterId];
      return next;
    });
    setClusterSnapshotLoading((current) => {
      const next = { ...current };
      delete next[clusterId];
      return next;
    });
    setClusterEvents((current) => {
      const next = { ...current };
      delete next[clusterId];
      clusterEventsRef.current = next;
      return next;
    });
    delete clusterEventLoadingRef.current[clusterId];
  }, []);

  return {
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
  };
}
