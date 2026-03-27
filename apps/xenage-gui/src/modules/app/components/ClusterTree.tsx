import { useState } from "react";
import { Icon, iconNameForItem } from "../../../components/Icon";
import type { NavigationLeaf } from "../../../types/controlPlane";
import type { ClusterEntry } from "../types";

const RBAC_KINDS = new Set(["User", "Role", "RoleBinding"]);

type ClusterTreeProps = {
  activeClusterId: string;
  activeKind: string;
  cluster: ClusterEntry;
  expanded: boolean;
  items: NavigationLeaf[];
  onEditCluster: (clusterId: string) => void;
  onOpen: (kind: string, clusterId: string) => void;
  onSelectCluster: (clusterId: string) => void;
  onToggle: () => void;
};

export function ClusterTree({
  activeClusterId,
  activeKind,
  cluster,
  expanded,
  items,
  onEditCluster,
  onOpen,
  onSelectCluster,
  onToggle,
}: ClusterTreeProps) {
  const mainItems = items.filter((item) => !RBAC_KINDS.has(item.kind));
  const rbacItems = items.filter((item) => RBAC_KINDS.has(item.kind));
  const [rbacExpanded, setRbacExpanded] = useState(true);

  return (
    <div className="cluster-node">
      <button
        className={`cluster-node__header ${activeClusterId === cluster.id ? "cluster-node__header--active" : ""}`}
        onClick={() => {
          onSelectCluster(cluster.id);
          onToggle();
        }}
        type="button"
      >
        <span className={`caret ${expanded ? "caret--open" : ""}`}>
          <Icon name="chevron" />
        </span>
        <span className="cluster-node__icon" style={{ color: cluster.accent }}>
          <Icon name="cluster" />
        </span>
        <span className="cluster-node__swatch" style={{ background: cluster.accent }} />
        <span className="cluster-node__name">{cluster.name}</span>
        <span
          className="cluster-node__edit"
          onClick={(event) => {
            event.preventDefault();
            event.stopPropagation();
            onEditCluster(cluster.id);
          }}
          onKeyDown={(event) => {
            if (event.key === "Enter" || event.key === " ") {
              event.preventDefault();
              event.stopPropagation();
              onEditCluster(cluster.id);
            }
          }}
          role="button"
          tabIndex={0}
          title="Cluster config"
        >
          <Icon name="settings" />
        </span>
      </button>

      {expanded ? (
        <div className="cluster-node__children">
          {mainItems.map((item) => (
            <button
              className={`resource-link ${activeClusterId === cluster.id && activeKind === item.kind ? "resource-link--active" : ""}`}
              key={`${cluster.id}-${item.kind}`}
              onClick={() => onOpen(item.kind, cluster.id)}
              type="button"
            >
              <span className="resource-link__glyph">
                <Icon name={iconNameForItem(item.kind)} />
              </span>
              <span>{item.label}</span>
            </button>
          ))}
          {rbacItems.length > 0 ? (
            <div className="cluster-node__subtree">
              <button
                aria-expanded={rbacExpanded}
                className="resource-link resource-link--subtree-toggle"
                onClick={() => setRbacExpanded((current) => !current)}
                type="button"
              >
                <span className={`caret ${rbacExpanded ? "caret--open" : ""}`}>
                  <Icon name="chevron" />
                </span>
                <span className="cluster-node__subtree-title">RBAC</span>
              </button>
              {rbacExpanded ? rbacItems.map((item) => (
                <button
                  className={`resource-link resource-link--subtree-item ${activeClusterId === cluster.id && activeKind === item.kind ? "resource-link--active" : ""}`}
                  key={`${cluster.id}-${item.kind}`}
                  onClick={() => onOpen(item.kind, cluster.id)}
                  type="button"
                >
                  <span className="resource-link__glyph">
                    <Icon name={iconNameForItem(item.kind)} />
                  </span>
                  <span>{item.label}</span>
                </button>
              )) : null}
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
