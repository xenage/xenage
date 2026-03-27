import { useCallback, useMemo, useRef, useState } from "react";
import type {
  Dispatch,
  MutableRefObject,
  SetStateAction,
  WheelEvent,
} from "react";
import { PointerSensor, useSensor, useSensors } from "@dnd-kit/core";
import type { DragEndEvent } from "@dnd-kit/core";
import { arrayMove } from "@dnd-kit/sortable";
import type { OverlayScrollbarsComponentRef } from "overlayscrollbars-react";
import { logger } from "../../../services/logger";
import { WindowService } from "../../../services/window";
import type { StoredClusterConnection } from "../../../services/clusterConnection";
import { shouldDetachTabByDrag } from "../../tabs/dragDetach";
import type { OpenTab } from "../../tabs/types";
import type { ClusterEntry } from "../types";
import {
  SETTINGS_KIND,
  SETTINGS_TAB_ID,
  SETUP_KIND,
  SETUP_TAB_ID,
} from "../constants";

type UseTabManagerArgs = {
  activeClusterId: string;
  clusters: ClusterEntry[];
  connectionConfigs: StoredClusterConnection[];
  initialWindowTab: OpenTab | null;
  setActiveClusterId: (value: string) => void;
  setGuiConnectionYaml: (value: string) => void;
};

type UseTabManagerResult = {
  activateTab: (tabId: string, clusterId: string) => void;
  activeTabId: string;
  closeTab: (tabId: string) => void;
  handleTabDragEnd: (event: DragEndEvent) => void;
  handleTabWheel: (event: WheelEvent<HTMLDivElement>) => void;
  openResource: (kind: string, clusterId: string) => void;
  openSettingsTab: () => void;
  openSetupTab: () => void;
  openTabInWindow: (tab: OpenTab) => Promise<boolean>;
  openTabs: OpenTab[];
  setActiveTabId: Dispatch<SetStateAction<string>>;
  setOpenTabs: Dispatch<SetStateAction<OpenTab[]>>;
  tabBarRef: MutableRefObject<HTMLDivElement | null>;
  tabSensors: ReturnType<typeof useSensors>;
  tabStripRef: MutableRefObject<OverlayScrollbarsComponentRef<"div"> | null>;
};

export function useTabManager({
  activeClusterId,
  clusters,
  connectionConfigs,
  initialWindowTab,
  setActiveClusterId,
  setGuiConnectionYaml,
}: UseTabManagerArgs): UseTabManagerResult {
  const tabBarRef = useRef<HTMLDivElement | null>(null);
  const tabStripRef = useRef<OverlayScrollbarsComponentRef<"div"> | null>(null);
  const [openTabs, setOpenTabs] = useState<OpenTab[]>(() =>
    initialWindowTab ? [initialWindowTab] : [{ id: SETUP_TAB_ID, kind: SETUP_KIND, clusterId: "" }],
  );
  const [activeTabId, setActiveTabId] = useState<string>(initialWindowTab?.id ?? SETUP_TAB_ID);

  const activateTab = useCallback((tabId: string, clusterId: string) => {
    logger.debug("Activating tab", { tabId, clusterId });
    setActiveTabId(tabId);
    setActiveClusterId(clusterId);
  }, [setActiveClusterId]);

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
  }, [activateTab, activeClusterId, clusters, connectionConfigs, setGuiConnectionYaml]);

  const openSettingsTab = useCallback(() => {
    const clusterId = activeClusterId || clusters[0]?.id || "";
    setOpenTabs((current) => {
      if (current.some((tab) => tab.id === SETTINGS_TAB_ID)) {
        return current;
      }
      return [...current, { id: SETTINGS_TAB_ID, kind: SETTINGS_KIND, clusterId }];
    });
    activateTab(SETTINGS_TAB_ID, clusterId);
  }, [activateTab, activeClusterId, clusters]);

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

  const openTabInWindow = useCallback((tab: OpenTab): Promise<boolean> => {
    const tabLabel = tab.id === SETTINGS_TAB_ID ? SETTINGS_KIND : tab.id === SETUP_TAB_ID ? "Setup Guide" : tab.kind;
    const clusterLabel = clusters.find((cluster) => cluster.id === tab.clusterId)?.name || "xenage";
    return WindowService.openDetachedTabWindow({
      sourceUrl: window.location.href,
      tabId: tab.id,
      tabKind: tab.kind,
      clusterId: tab.clusterId,
      tabLabel,
      clusterLabel,
    }).then(() => {
      logger.info("Opened detached tab window", { tabId: tab.id, clusterId: tab.clusterId });
      return true;
    }).catch((error) => {
      logger.error("Failed to open detached tab window", { tabId: tab.id, clusterId: tab.clusterId, error });
      return false;
    });
  }, [clusters]);

  const shouldDetachByDrag = useCallback((event: DragEndEvent): boolean => {
    const tabBarBounds = tabBarRef.current?.getBoundingClientRect();
    if (!tabBarBounds) {
      return false;
    }
    return shouldDetachTabByDrag(event, tabBarBounds);
  }, []);

  const detachTabToWindow = useCallback(async (tabId: string) => {
    const tab = openTabs.find((candidate) => candidate.id === tabId);
    if (!tab) {
      logger.warn("Attempted to detach missing tab", { tabId });
      return;
    }
    const opened = await openTabInWindow(tab);
    if (!opened) {
      return;
    }
    closeTab(tabId);
  }, [closeTab, openTabInWindow, openTabs]);

  const handleTabDragEnd = useCallback((event: DragEndEvent) => {
    const sourceId = String(event.active.id);
    if (!sourceId) {
      return;
    }
    if (shouldDetachByDrag(event)) {
      logger.info("Detaching tab via drag", { tabId: sourceId });
      void detachTabToWindow(sourceId);
      return;
    }
    const targetId = event.over ? String(event.over.id) : "";
    if (!targetId || sourceId === targetId) {
      return;
    }
    setOpenTabs((current) => {
      const sourceIndex = current.findIndex((tab) => tab.id === sourceId);
      const targetIndex = current.findIndex((tab) => tab.id === targetId);
      if (sourceIndex === -1 || targetIndex === -1) {
        return current;
      }
      return arrayMove(current, sourceIndex, targetIndex);
    });
  }, [detachTabToWindow, shouldDetachByDrag]);

  const tabSensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 8 },
    }),
  );

  const handleTabWheel = useCallback((event: WheelEvent<HTMLDivElement>) => {
    const element = tabStripRef.current?.osInstance()?.elements().scrollOffsetElement;
    if (!element) {
      return;
    }
    if (Math.abs(event.deltaY) <= Math.abs(event.deltaX)) {
      return;
    }

    event.preventDefault();
    element.scrollLeft += event.deltaY;
    logger.debug("Horizontal tab scroll", {
      deltaX: event.deltaX,
      deltaY: event.deltaY,
      nextScrollLeft: element.scrollLeft,
    });
  }, []);

  return useMemo(() => ({
    activateTab,
    activeTabId,
    closeTab,
    handleTabDragEnd,
    handleTabWheel,
    openResource,
    openSettingsTab,
    openSetupTab,
    openTabInWindow,
    openTabs,
    setActiveTabId,
    setOpenTabs,
    tabBarRef,
    tabSensors,
    tabStripRef,
  }), [
    activateTab,
    activeTabId,
    closeTab,
    handleTabDragEnd,
    handleTabWheel,
    openResource,
    openSettingsTab,
    openSetupTab,
    openTabInWindow,
    openTabs,
    tabSensors,
  ]);
}
