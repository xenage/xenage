import { describe, expect, it } from "vitest";
import { parseInitialHorizontalWindowTab } from "./windowState";

describe("parseInitialHorizontalWindowTab", () => {
  it("parses console popout tab from URL", () => {
    const tab = parseInitialHorizontalWindowTab(
      "https://example.local/?subWindowPopout=1&subWindowKind=console&subWindowTabId=console&subWindowTitle=Console&subWindowIcon=session",
    );

    expect(tab).toEqual({
      icon: "session",
      id: "console",
      kind: "console",
      payload: null,
      title: "Console",
    });
  });

  it("parses rbac editor popout tab from URL", () => {
    const tab = parseInitialHorizontalWindowTab(
      "https://example.local/?subWindowPopout=1&subWindowKind=rbac-editor&subWindowTabId=rbac%3Acluster-1%3ARole%3Aviewer&subWindowTitle=viewer&subWindowIcon=role&subWindowClusterId=cluster-1&subWindowClusterYaml=cluster%3A%20main&subWindowResourceKind=Role&subWindowResourceName=viewer&subWindowYaml=kind%3A%20Role",
    );

    expect(tab).toEqual({
      icon: "role",
      id: "rbac:cluster-1:Role:viewer",
      kind: "rbac-editor",
      payload: {
        clusterId: "cluster-1",
        clusterYaml: "cluster: main",
        kind: "Role",
        resourceName: "viewer",
        yaml: "kind: Role",
      },
      title: "viewer",
    });
  });
});
