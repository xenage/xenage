import { OverlayScrollbarsComponent } from "overlayscrollbars-react";
import type { PartialOptions } from "overlayscrollbars";
import type { MouseEvent } from "react";
import { Icon } from "../../../components/Icon";
import type { NavigationLeaf } from "../../../types/controlPlane";
import type { ClusterEntry } from "../types";
import { ClusterTree } from "./ClusterTree";

type NavigatorSidebarProps = {
  activeClusterId: string;
  activeKind: string;
  clusterDraftAccent: string;
  clusterDraftName: string;
  editingClusterId: string | null;
  expandedClusters: Record<string, boolean>;
  itemsByCluster: Record<string, NavigationLeaf[]>;
  onCloseEditor: () => void;
  onDeleteCluster: () => Promise<void>;
  onDraftAccentChange: (value: string) => void;
  onDraftNameChange: (value: string) => void;
  onEditCluster: (clusterId: string) => void;
  onOpenResource: (kind: string, clusterId: string) => void;
  onOpenSettings: () => void;
  onOpenSetupGuide: () => void;
  onResizeStart: (event: MouseEvent<HTMLDivElement>) => void;
  onSaveCluster: () => Promise<void>;
  onSearchChange: (value: string) => void;
  onSelectCluster: (clusterId: string) => void;
  onShareCluster: () => Promise<void>;
  onSidebarHide: () => void;
  onToggleCluster: (clusterId: string) => void;
  overlayScrollbarOptions: PartialOptions;
  search: string;
  shareCopyNotice: string | null;
  visibleClusters: ClusterEntry[];
};

export function NavigatorSidebar({
  activeClusterId,
  activeKind,
  clusterDraftAccent,
  clusterDraftName,
  editingClusterId,
  expandedClusters,
  itemsByCluster,
  onCloseEditor,
  onDeleteCluster,
  onDraftAccentChange,
  onDraftNameChange,
  onEditCluster,
  onOpenResource,
  onOpenSettings,
  onOpenSetupGuide,
  onResizeStart,
  onSaveCluster,
  onSearchChange,
  onSelectCluster,
  onShareCluster,
  onSidebarHide,
  onToggleCluster,
  overlayScrollbarOptions,
  search,
  shareCopyNotice,
  visibleClusters,
}: NavigatorSidebarProps) {
  return (
    <aside className="navigator">
      <div className="navigator__header">
        <button
          className="navigator__settings"
          onClick={onSidebarHide}
          type="button"
          title="Hide sidebar"
        >
          <Icon name="close" />
        </button>
        <button
          className="navigator__settings"
          onClick={onOpenSettings}
          type="button"
          title="Open settings"
        >
          <Icon name="settings" />
        </button>
        <div className="navigator__title">xenage</div>
      </div>

      <div className="navigator__toolbar">
        <label className="search-box search-box--toolbar">
          <span className="search-box__icon">
            <Icon name="search" />
          </span>
          <input
            aria-label="Search navigation"
            onChange={(event) => onSearchChange(event.target.value)}
            placeholder="Search"
            value={search}
          />
        </label>
        <button className="icon-button" onClick={onOpenSetupGuide} type="button" title="Open setup guide">
          <Icon name="plus" />
        </button>
      </div>

      <div className="tree-panel">
        <OverlayScrollbarsComponent
          className="tree-panel__body scroll-host scroll-host--sidebar"
          options={overlayScrollbarOptions}
        >
          <div className="tree-group__clusters">
            {visibleClusters.map((cluster) => (
              <ClusterTree
                activeClusterId={activeClusterId}
                activeKind={activeKind}
                cluster={cluster}
                expanded={expandedClusters[cluster.id] ?? false}
                items={itemsByCluster[cluster.id]}
                key={cluster.id}
                onEditCluster={onEditCluster}
                onOpen={onOpenResource}
                onSelectCluster={onSelectCluster}
                onToggle={() => onToggleCluster(cluster.id)}
              />
            ))}
          </div>
        </OverlayScrollbarsComponent>
      </div>

      {editingClusterId ? (
        <div className="cluster-editor">
          <div className="cluster-editor__header">
            <div className="cluster-editor__title">Cluster Config</div>
            <button
              className="cluster-editor__icon"
              onClick={() => void onShareCluster()}
              title="Share config (copy YAML)"
              type="button"
            >
              <Icon name="share" />
            </button>
          </div>
          {shareCopyNotice ? <div className="cluster-editor__notice">{shareCopyNotice}</div> : null}
          <label className="cluster-editor__field">
            <span>Name</span>
            <input
              onChange={(event) => onDraftNameChange(event.target.value)}
              value={clusterDraftName}
            />
          </label>
          <label className="cluster-editor__field">
            <span>Color</span>
            <input
              onChange={(event) => onDraftAccentChange(event.target.value)}
              type="color"
              value={clusterDraftAccent}
            />
          </label>
          <div className="cluster-editor__actions">
            <button className="cluster-editor__button" onClick={() => void onSaveCluster()} type="button">Save</button>
            <button className="cluster-editor__button cluster-editor__button--danger" onClick={() => void onDeleteCluster()} type="button">Delete</button>
            <button className="cluster-editor__button cluster-editor__button--muted" onClick={onCloseEditor} type="button">Cancel</button>
          </div>
        </div>
      ) : null}
      <div
        className="navigator__resize-handle"
        onMouseDown={onResizeStart}
        role="separator"
        aria-label="Resize sidebar"
      />
    </aside>
  );
}
