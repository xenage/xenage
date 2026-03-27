import { fireEvent, render, screen } from "@testing-library/react";
import { vi } from "vitest";
import type { NavigationLeaf } from "../../../types/controlPlane";
import { ClusterTree } from "./ClusterTree";

const NAV_ITEMS: NavigationLeaf[] = [
  { label: "Nodes", kind: "Node" },
  { label: "Group Config", kind: "GroupConfig" },
  { label: "Events", kind: "Event" },
  { label: "Users", kind: "User" },
  { label: "Roles", kind: "Role" },
  { label: "Role Bindings", kind: "RoleBinding" },
];

describe("ClusterTree", () => {
  it("renders collapsible RBAC subtree and opens RBAC resources", () => {
    const onOpen = vi.fn();
    const onSelectCluster = vi.fn();
    const onToggle = vi.fn();

    render(
      <ClusterTree
        activeClusterId="cluster-1"
        activeKind="Node"
        cluster={{ id: "cluster-1", name: "Alpha", accent: "#22c55e" }}
        expanded
        items={NAV_ITEMS}
        onEditCluster={vi.fn()}
        onOpen={onOpen}
        onSelectCluster={onSelectCluster}
        onToggle={onToggle}
      />,
    );

    const rbacToggle = screen.getByRole("button", { name: /RBAC/i });
    expect(rbacToggle).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Roles/i })).toBeInTheDocument();
    fireEvent.click(rbacToggle);
    expect(screen.queryByRole("button", { name: /Roles/i })).not.toBeInTheDocument();
    fireEvent.click(rbacToggle);
    fireEvent.click(screen.getByRole("button", { name: /Roles/i }));
    expect(onOpen).toHaveBeenCalledWith("Role", "cluster-1");

    fireEvent.click(screen.getByRole("button", { name: /Alpha/i }));
    expect(onSelectCluster).toHaveBeenCalledWith("cluster-1");
    expect(onToggle).toHaveBeenCalledTimes(1);
  });
});
