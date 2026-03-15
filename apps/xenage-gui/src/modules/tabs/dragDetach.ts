import type { DragEndEvent } from "@dnd-kit/core";

export const TAB_DETACH_TRIGGER_PX = 28;

function pointerFromActivatorEvent(event: Event, deltaX: number, deltaY: number): { x: number; y: number } | null {
  if ("clientX" in event && "clientY" in event) {
    const x = Number(event.clientX);
    const y = Number(event.clientY);
    if (!Number.isNaN(x) && !Number.isNaN(y)) {
      return { x: x + deltaX, y: y + deltaY };
    }
  }

  if ("changedTouches" in event) {
    const changedTouches = (event as TouchEvent).changedTouches;
    if (changedTouches.length === 0) {
      return null;
    }
    const touch = changedTouches[0];
    return { x: touch.clientX + deltaX, y: touch.clientY + deltaY };
  }

  return null;
}

export function shouldDetachTabByDrag(
  event: DragEndEvent,
  tabBarBounds: DOMRect,
  threshold = TAB_DETACH_TRIGGER_PX,
): boolean {
  const pointer = pointerFromActivatorEvent(event.activatorEvent, event.delta.x, event.delta.y);
  if (pointer) {
    const outsideVertically = pointer.y < tabBarBounds.top - threshold
      || pointer.y > tabBarBounds.bottom + threshold;
    const outsideHorizontally = pointer.x < tabBarBounds.left - threshold
      || pointer.x > tabBarBounds.right + threshold;
    return outsideVertically || outsideHorizontally;
  }

  const initialRect = event.active.rect.current.initial;
  if (!initialRect) {
    return false;
  }
  const translatedRect = event.active.rect.current.translated;
  const left = translatedRect?.left ?? initialRect.left + event.delta.x;
  const top = translatedRect?.top ?? initialRect.top + event.delta.y;
  const width = translatedRect?.width ?? initialRect.width;
  const height = translatedRect?.height ?? initialRect.height;
  const centerX = left + width / 2;
  const centerY = top + height / 2;
  const outsideVertically = centerY < tabBarBounds.top - threshold
    || centerY > tabBarBounds.bottom + threshold;
  const outsideHorizontally = centerX < tabBarBounds.left - threshold
    || centerX > tabBarBounds.right + threshold;
  return outsideVertically || outsideHorizontally;
}
