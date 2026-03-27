import { useSortable } from "@dnd-kit/sortable";
import { CSS as DndCss } from "@dnd-kit/utilities";
import { Icon } from "../../components/Icon";
import type { IconName } from "../../components/Icon";
import { logger } from "../../services/logger";

export function SortableTab({
  active,
  accent,
  closable,
  iconName,
  id,
  onActivate,
  onClose,
  title,
}: {
  active: boolean;
  accent: string;
  closable: boolean;
  iconName: IconName;
  id: string;
  onActivate: () => void;
  onClose: () => void;
  title: string;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id });
  const style = {
    ["--tab-accent" as string]: accent,
    transform: DndCss.Transform.toString(transform),
    transition,
  };

  return (
    <div
      {...attributes}
      {...listeners}
      aria-selected={active}
      className={`tab ${active ? "tab--active" : ""} ${isDragging ? "tab--dragging" : ""}`}
      data-tab-id={id}
      onClick={onActivate}
      onKeyDown={(event) => {
        if (event.key === "Enter") {
          event.preventDefault();
          onActivate();
        }
      }}
      ref={setNodeRef}
      role="tab"
      style={style}
      tabIndex={0}
    >
      <span className="tab__icon">
        <Icon name={iconName} />
      </span>
      <span className="tab__title">{title}</span>
      <div className="tab__actions">
        <button
          aria-label={`Close ${title}`}
          className={`tab__close ${!closable ? "tab__close--disabled" : ""}`}
          disabled={!closable}
          onClick={(event) => {
            event.preventDefault();
            event.stopPropagation();
            logger.debug("Close button clicked", { tabId: id, closable });
            if (closable) {
              onClose();
            }
          }}
          onPointerDown={(event) => event.stopPropagation()}
          type="button"
        >
          <Icon name="close" />
        </button>
      </div>
    </div>
  );
}
