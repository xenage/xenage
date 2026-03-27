import { DndContext, PointerSensor, closestCenter, useSensor, useSensors } from "@dnd-kit/core";
import type { DragEndEvent } from "@dnd-kit/core";
import { SortableContext, horizontalListSortingStrategy } from "@dnd-kit/sortable";
import type { IconName } from "../../../components/Icon";
import { shouldDetachTabByDrag } from "../../tabs/dragDetach";
import { HorizontalSortableTab } from "./HorizontalSortableTab";
import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";

export type HorizontalTab = {
  icon: IconName;
  id: string;
  title: string;
};

type HorizontalSubWindowProps = {
  activeTabId: string;
  children: ReactNode;
  onActivateTab: (tabId: string) => void;
  onCloseTab: (tabId: string) => void;
  onDetachTab: (tabId: string) => void;
  onReorderTabs: (sourceTabId: string, targetTabId: string) => void;
  tabs: HorizontalTab[];
};

const DEFAULT_HEIGHT_PX = 280;
const MIN_HEIGHT_PX = 180;
const MAX_HEIGHT_RATIO = 0.8;

export function HorizontalSubWindow({
  activeTabId,
  children,
  onActivateTab,
  onCloseTab,
  onDetachTab,
  onReorderTabs,
  tabs,
}: HorizontalSubWindowProps) {
  const [heightPx, setHeightPx] = useState<number>(DEFAULT_HEIGHT_PX);
  const resizeStartRef = useRef<{ startHeight: number; startY: number } | null>(null);
  const tabsBarRef = useRef<HTMLDivElement | null>(null);
  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 8 },
    }),
  );

  const handleDragEnd = (event: DragEndEvent) => {
    const sourceId = String(event.active.id);
    if (!sourceId) {
      return;
    }

    const tabsBounds = tabsBarRef.current?.getBoundingClientRect();
    if (tabsBounds && shouldDetachTabByDrag(event, tabsBounds)) {
      onDetachTab(sourceId);
      return;
    }

    const targetId = event.over ? String(event.over.id) : "";
    if (!targetId || sourceId === targetId) {
      return;
    }
    onReorderTabs(sourceId, targetId);
  };

  useEffect(() => {
    const handleMouseMove = (event: MouseEvent) => {
      const resizeStart = resizeStartRef.current;
      if (!resizeStart) {
        return;
      }
      const deltaY = resizeStart.startY - event.clientY;
      const maxHeight = Math.max(MIN_HEIGHT_PX, Math.floor(window.innerHeight * MAX_HEIGHT_RATIO));
      const nextHeight = Math.min(maxHeight, Math.max(MIN_HEIGHT_PX, resizeStart.startHeight + deltaY));
      setHeightPx(nextHeight);
    };
    const handleMouseUp = () => {
      resizeStartRef.current = null;
      document.body.classList.remove("horizontal-subwindow-resizing");
    };

    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);
    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
      document.body.classList.remove("horizontal-subwindow-resizing");
    };
  }, []);

  if (tabs.length === 0) {
    return null;
  }

  return (
    <div className="horizontal-subwindow" style={{ height: `${heightPx}px` }}>
      <div
        aria-label="Resize horizontal subwindow"
        className="horizontal-subwindow__resize-handle"
        onMouseDown={(event) => {
          event.preventDefault();
          resizeStartRef.current = { startHeight: heightPx, startY: event.clientY };
          document.body.classList.add("horizontal-subwindow-resizing");
        }}
        role="separator"
      />
      <div className="horizontal-subwindow__tabs" ref={tabsBarRef}>
        <DndContext collisionDetection={closestCenter} onDragEnd={handleDragEnd} sensors={sensors}>
          <SortableContext items={tabs.map((tab) => tab.id)} strategy={horizontalListSortingStrategy}>
            {tabs.map((tab) => (
              <HorizontalSortableTab
                active={activeTabId === tab.id}
                icon={tab.icon}
                id={tab.id}
                key={tab.id}
                onActivate={() => onActivateTab(tab.id)}
                onClose={() => onCloseTab(tab.id)}
                title={tab.title}
              />
            ))}
          </SortableContext>
        </DndContext>
      </div>
      <div className="horizontal-subwindow__body">{children}</div>
    </div>
  );
}
