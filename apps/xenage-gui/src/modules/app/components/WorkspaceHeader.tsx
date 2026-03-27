import { DndContext, closestCenter } from "@dnd-kit/core";
import type { DragEndEvent, SensorDescriptor, SensorOptions } from "@dnd-kit/core";
import { SortableContext, horizontalListSortingStrategy } from "@dnd-kit/sortable";
import { OverlayScrollbarsComponent } from "overlayscrollbars-react";
import type { OverlayScrollbarsComponentRef } from "overlayscrollbars-react";
import type { PartialOptions } from "overlayscrollbars";
import type { MutableRefObject, WheelEvent } from "react";
import { Icon, iconNameForItem } from "../../../components/Icon";
import { SortableTab } from "../../tabs/SortableTab";
import type { OpenTab } from "../../tabs/types";
import type { ClusterEntry } from "../types";
import { SETTINGS_KIND, SETTINGS_TAB_ID, SETUP_TAB_ID } from "../constants";

type WorkspaceHeaderProps = {
  activeTabId: string;
  clusters: ClusterEntry[];
  hasStoredConnections: boolean;
  onActivateTab: (tabId: string, clusterId: string) => void;
  onCloseTab: (tabId: string) => void;
  onDragEnd: (event: DragEndEvent) => void;
  onShowSidebar: () => void;
  onTabWheel: (event: WheelEvent<HTMLDivElement>) => void;
  openTabs: OpenTab[];
  resourcesByKind: Map<string, { title: string }>;
  showSidebar: boolean;
  tabBarRef: MutableRefObject<HTMLDivElement | null>;
  tabSensors: SensorDescriptor<SensorOptions>[];
  tabScrollbarOptions: PartialOptions;
  tabStripRef: MutableRefObject<OverlayScrollbarsComponentRef<"div"> | null>;
};

export function WorkspaceHeader({
  activeTabId,
  clusters,
  hasStoredConnections,
  onActivateTab,
  onCloseTab,
  onDragEnd,
  onShowSidebar,
  onTabWheel,
  openTabs,
  resourcesByKind,
  showSidebar,
  tabBarRef,
  tabSensors,
  tabScrollbarOptions,
  tabStripRef,
}: WorkspaceHeaderProps) {
  return (
    <header className="workspace__bar">
      {!showSidebar && hasStoredConnections ? (
        <button
          className="workspace__sidebar-toggle"
          onClick={onShowSidebar}
          title="Show sidebar"
          type="button"
        >
          <Icon name="panel" />
        </button>
      ) : null}
      <div className="tab-bar" ref={tabBarRef}>
        <DndContext
          collisionDetection={closestCenter}
          onDragEnd={onDragEnd}
          sensors={tabSensors}
        >
          <OverlayScrollbarsComponent
            className="tab-strip scroll-host scroll-host--tabs"
            onWheel={onTabWheel}
            options={tabScrollbarOptions}
            ref={tabStripRef}
          >
            <SortableContext items={openTabs.map((tab) => tab.id)} strategy={horizontalListSortingStrategy}>
              <div className="tab-strip__inner">
                {openTabs.map((tab) => {
                  const resource = resourcesByKind.get(tab.kind);
                  const active = tab.id === activeTabId;
                  const closable = openTabs.length > 1;
                  const cluster = clusters.find((item) => item.id === tab.clusterId) ?? {
                    id: "local",
                    name: "LOCAL",
                    accent: "#22c55e",
                  };
                  const tabLabel = tab.id === SETTINGS_TAB_ID
                    ? SETTINGS_KIND
                    : tab.id === SETUP_TAB_ID
                      ? "Setup Guide"
                      : resource?.title ?? tab.kind;
                  const title = cluster.name ? `${tabLabel} · ${cluster.name}` : tabLabel;

                  return (
                    <SortableTab
                      active={active}
                      accent={cluster.accent}
                      closable={closable}
                      id={tab.id}
                      iconName={tab.id === SETTINGS_TAB_ID || tab.id === SETUP_TAB_ID ? "settings" : iconNameForItem(tab.kind)}
                      key={tab.id}
                      onActivate={() => onActivateTab(tab.id, tab.clusterId)}
                      onClose={() => onCloseTab(tab.id)}
                      title={title}
                    />
                  );
                })}
              </div>
            </SortableContext>
          </OverlayScrollbarsComponent>
        </DndContext>
      </div>
    </header>
  );
}
