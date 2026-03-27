import { useSortable } from "@dnd-kit/sortable";
import { CSS as DndCss } from "@dnd-kit/utilities";
import { Icon } from "../../../components/Icon";
import type { IconName } from "../../../components/Icon";

type HorizontalSortableTabProps = {
  active: boolean;
  icon: IconName;
  id: string;
  onActivate: () => void;
  onClose: () => void;
  title: string;
};

export function HorizontalSortableTab({
  active,
  icon,
  id,
  onActivate,
  onClose,
  title,
}: HorizontalSortableTabProps) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id });
  const style = {
    transform: DndCss.Transform.toString(transform),
    transition,
  };

  return (
    <button
      {...attributes}
      {...listeners}
      className={`horizontal-subwindow__tab ${active ? "horizontal-subwindow__tab--active" : ""} ${isDragging ? "horizontal-subwindow__tab--dragging" : ""}`}
      onClick={onActivate}
      ref={setNodeRef}
      style={style}
      type="button"
    >
      <span className="horizontal-subwindow__tab-icon">
        <Icon name={icon} />
      </span>
      <span className="horizontal-subwindow__tab-title">{title}</span>
      <span
        className="horizontal-subwindow__tab-close"
        onClick={(event) => {
          event.preventDefault();
          event.stopPropagation();
          onClose();
        }}
        onPointerDown={(event) => event.stopPropagation()}
        role="button"
        tabIndex={0}
      >
        ×
      </span>
    </button>
  );
}
