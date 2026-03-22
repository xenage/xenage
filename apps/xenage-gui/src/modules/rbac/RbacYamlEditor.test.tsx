import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";
import { ClusterConnectionService } from "../../services/clusterConnection";
import type { ManifestTable } from "../../types/controlPlane";
import { RbacYamlEditor } from "./RbacYamlEditor";

vi.mock("../../services/clusterConnection", () => ({
  ClusterConnectionService: {
    listConnectionYamls: vi.fn(),
    listRbacYamlResources: vi.fn(),
    applyRbacYamlResource: vi.fn(),
  },
}));

describe("RbacYamlEditor", () => {
  const roleTableSchema: ManifestTable = {
    kind: "Role",
    title: "Roles",
    source: "rbac.roles",
    rowKind: "RoleTableRow",
    rowKey: "name",
    defaultSort: { field: "name", direction: "asc" },
    columns: [
      {
        key: "name",
        label: "Name",
        path: "name",
        type: "str",
        isArray: false,
        width: 220,
        minWidth: 140,
        displayOnly: false,
      },
      {
        key: "rule_count",
        label: "Rule Count",
        path: "rule_count",
        type: "int",
        isArray: false,
        width: 140,
        minWidth: 100,
        displayOnly: false,
      },
    ],
    sample: {},
  };

  it("opens editor tab for selected row", async () => {
    const onOpenEditorTab = vi.fn();
    vi.mocked(ClusterConnectionService.listConnectionYamls).mockResolvedValue([
      { id: "cluster-1", name: "alpha", yaml: "cluster: alpha" },
    ]);
    vi.mocked(ClusterConnectionService.listRbacYamlResources).mockResolvedValue([
      {
        kind: "Role",
        name: "viewer",
        yaml: "apiVersion: rbac.authorization.xenage.dev/v1\nkind: Role\nmetadata:\n  name: viewer\n",
        manifest: {
          kind: "Role",
          metadata: { name: "viewer" },
          rules: [],
        },
      },
    ]);
    render(
      <RbacYamlEditor
        activeKind="Role"
        onOpenEditorTab={onOpenEditorTab}
        resolvedClusterId="cluster-1"
        searchTerm=""
        tableSchema={roleTableSchema}
      />,
    );

    const row = await screen.findByText("viewer");
    fireEvent.click(row);

    expect(onOpenEditorTab).toHaveBeenCalledWith({
      clusterId: "cluster-1",
      clusterYaml: "cluster: alpha",
      kind: "Role",
      resourceName: "viewer",
      yaml: expect.stringContaining("kind: Role"),
    });
  });

  it("shows delete floating action when rows are selected and deletes selected resources", async () => {
    const onOpenEditorTab = vi.fn();
    vi.mocked(ClusterConnectionService.listConnectionYamls).mockResolvedValue([
      { id: "cluster-1", name: "alpha", yaml: "cluster: alpha" },
    ]);
    vi.mocked(ClusterConnectionService.listRbacYamlResources).mockResolvedValue([
      {
        kind: "Role",
        name: "viewer",
        yaml: "apiVersion: rbac.authorization.xenage.dev/v1\nkind: Role\nmetadata:\n  name: viewer\n",
        manifest: {
          kind: "Role",
          metadata: { name: "viewer" },
          rules: [],
        },
      },
    ]);
    vi.mocked(ClusterConnectionService.applyRbacYamlResource).mockResolvedValue({ status: "deleted" });

    render(
      <RbacYamlEditor
        activeKind="Role"
        onOpenEditorTab={onOpenEditorTab}
        resolvedClusterId="cluster-1"
        searchTerm=""
        tableSchema={roleTableSchema}
      />,
    );

    await screen.findByText("viewer");
    const checkboxes = screen.getAllByRole("checkbox");
    fireEvent.click(checkboxes[1]);
    fireEvent.click(screen.getByRole("button", { name: "Delete selected RBAC resources" }));

    await waitFor(() => {
      expect(ClusterConnectionService.applyRbacYamlResource).toHaveBeenCalledWith(
        "cluster: alpha",
        expect.stringContaining("name: viewer"),
        true,
      );
    });
  });

  it("creates new resource via floating plus action and opens create tab", async () => {
    const onOpenEditorTab = vi.fn();
    vi.mocked(ClusterConnectionService.listConnectionYamls).mockResolvedValue([
      { id: "cluster-1", name: "alpha", yaml: "cluster: alpha" },
    ]);
    vi.mocked(ClusterConnectionService.listRbacYamlResources).mockResolvedValue([]);

    render(
      <RbacYamlEditor
        activeKind="User"
        onOpenEditorTab={onOpenEditorTab}
        resolvedClusterId="cluster-1"
        searchTerm=""
        tableSchema={{
          ...roleTableSchema,
          kind: "User",
          source: "rbac.users",
        }}
      />,
    );

    await screen.findByText("No User resources yet.");
    fireEvent.click(screen.getByRole("button", { name: "Create RBAC resource" }));
    expect(onOpenEditorTab).toHaveBeenCalledWith({
      clusterId: "cluster-1",
      clusterYaml: "cluster: alpha",
      kind: "User",
      resourceName: null,
      yaml: expect.stringContaining("kind: ServiceAccount"),
    });
  });
});
