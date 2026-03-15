import { useEffect } from "react";
import type {
  Dispatch,
  MutableRefObject,
  SetStateAction,
} from "react";
import type { OverlayScrollbarsComponentRef } from "overlayscrollbars-react";
import type { OpenTab } from "../../tabs/types";
import { logger } from "../../../services/logger";
import { SETTINGS_TAB_ID, SETUP_TAB_ID } from "../constants";
import type { ClusterEventCache } from "../types";
import { detectMacLikePlatform, resolveGlobalShortcut } from "../keyboardShortcuts";
import { formatClockTime } from "../utils";

type SidebarResizeState = { startX: number; startWidth: number } | null;

type UseAppEffectsArgs = {
  activateTab: (tabId: string, clusterId: string) => void;
  activeKind: string;
  activeKindNeedsSnapshot: boolean;
  activeTabId: string;
  closeTab: (tabId: string) => void;
  clusterEvents: Record<string, ClusterEventCache>;
  clusterSnapshotLoading: Record<string, boolean>;
  clusterSnapshots: Record<string, unknown>;
  fetchEventPageForCluster: (clusterId: string, mode?: "initial" | "older" | "refresh") => Promise<boolean>;
  fetchSnapshotForCluster: (clusterId: string) => Promise<boolean>;
  hasStoredConnections: boolean;
  initialWindowTab: OpenTab | null;
  openTabs: OpenTab[];
  refreshActiveTabFromServer: () => void;
  resolvedClusterId: string;
  setActiveTabId: Dispatch<SetStateAction<string>>;
  setClockTime: Dispatch<SetStateAction<string>>;
  setSidebarWidth: Dispatch<SetStateAction<number>>;
  sidebarResizeRef: MutableRefObject<SidebarResizeState>;
  tabStripRef: MutableRefObject<OverlayScrollbarsComponentRef<"div"> | null>;
};

export function useAppEffects({
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
}: UseAppEffectsArgs) {
  useEffect(() => {
    const timer = window.setInterval(() => {
      setClockTime(formatClockTime(Date.now()));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [setClockTime]);

  useEffect(() => {
    if (initialWindowTab) {
      return;
    }
    if (!hasStoredConnections && activeTabId !== SETUP_TAB_ID && activeTabId !== SETTINGS_TAB_ID) {
      setActiveTabId(SETUP_TAB_ID);
    }
  }, [activeTabId, hasStoredConnections, initialWindowTab, setActiveTabId]);

  useEffect(() => {
    if (!activeKindNeedsSnapshot || !resolvedClusterId) {
      return;
    }
    if (clusterSnapshots[resolvedClusterId] || clusterSnapshotLoading[resolvedClusterId]) {
      return;
    }
    void fetchSnapshotForCluster(resolvedClusterId);
  }, [
    activeKindNeedsSnapshot,
    clusterSnapshotLoading,
    clusterSnapshots,
    fetchSnapshotForCluster,
    resolvedClusterId,
  ]);

  useEffect(() => {
    if (activeKind !== "Event" || !resolvedClusterId) {
      return;
    }
    const cache = clusterEvents[resolvedClusterId];
    if (!cache || cache.items.length === 0) {
      void fetchEventPageForCluster(resolvedClusterId, "initial");
    }
  }, [activeKind, clusterEvents, fetchEventPageForCluster, resolvedClusterId]);

  useEffect(() => {
    if (!activeKindNeedsSnapshot || !resolvedClusterId) {
      return;
    }
    const timer = window.setInterval(() => {
      void fetchSnapshotForCluster(resolvedClusterId);
    }, 8000);
    return () => window.clearInterval(timer);
  }, [activeKindNeedsSnapshot, fetchSnapshotForCluster, resolvedClusterId]);

  useEffect(() => {
    if (activeKind !== "Event" || !resolvedClusterId) {
      return;
    }
    const timer = window.setInterval(() => {
      void fetchEventPageForCluster(resolvedClusterId, "refresh");
    }, 8000);
    return () => window.clearInterval(timer);
  }, [activeKind, fetchEventPageForCluster, resolvedClusterId]);

  useEffect(() => {
    const hostElement = tabStripRef.current?.getElement();
    if (!hostElement) {
      return;
    }

    const activeTabElement = hostElement.querySelector<HTMLElement>(`[data-tab-id="${window.CSS.escape(activeTabId)}"]`);
    if (!activeTabElement) {
      logger.debug("Active tab element not found for visibility sync", { activeTabId });
      return;
    }

    activeTabElement.scrollIntoView({
      behavior: "smooth",
      block: "nearest",
      inline: "nearest",
    });
    activeTabElement.focus({ preventScroll: true });
  }, [activeTabId, openTabs, tabStripRef]);

  useEffect(() => {
    const macLike = detectMacLikePlatform();

    const activateTabAtIndex = (index: number): boolean => {
      if (openTabs.length === 0) {
        return false;
      }
      const boundedIndex = Math.max(0, Math.min(index, openTabs.length - 1));
      const targetTab = openTabs[boundedIndex];
      if (!targetTab || targetTab.id === activeTabId) {
        return false;
      }
      activateTab(targetTab.id, targetTab.clusterId);
      return true;
    };

    const switchTab = (direction: 1 | -1): boolean => {
      if (openTabs.length <= 1) {
        return false;
      }
      const activeIndex = openTabs.findIndex((tab) => tab.id === activeTabId);
      const currentIndex = activeIndex === -1 ? 0 : activeIndex;
      const nextIndex = (currentIndex + direction + openTabs.length) % openTabs.length;
      return activateTabAtIndex(nextIndex);
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      const action = resolveGlobalShortcut(event, macLike);
      if (!action) {
        return;
      }

      if (action.type === "refresh") {
        const canRefreshFromServer = Boolean(resolvedClusterId)
          && (activeKindNeedsSnapshot || activeKind === "Event");
        if (!canRefreshFromServer) {
          return;
        }
        event.preventDefault();
        refreshActiveTabFromServer();
        return;
      }

      if (action.type === "closeTab") {
        event.preventDefault();
        if (openTabs.length > 1) {
          logger.debug("Keyboard shortcut close tab", { activeTabId });
          closeTab(activeTabId);
        }
        return;
      }

      if (action.type === "switchTab") {
        event.preventDefault();
        switchTab(action.direction);
        return;
      }

      event.preventDefault();
      if (action.index >= openTabs.length - 1) {
        activateTabAtIndex(openTabs.length - 1);
      } else {
        activateTabAtIndex(action.index);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [
    activateTab,
    activeKind,
    activeKindNeedsSnapshot,
    activeTabId,
    closeTab,
    openTabs,
    refreshActiveTabFromServer,
    resolvedClusterId,
  ]);

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
  }, [setSidebarWidth, sidebarResizeRef]);
}
