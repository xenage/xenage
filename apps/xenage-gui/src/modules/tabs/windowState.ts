import type { OpenTab } from "./types";
import type { IconName } from "../../components/Icon";

export function parseInitialWindowTab(sourceUrl: string): OpenTab | null {
  const params = new URL(sourceUrl).searchParams;
  if (params.get("tabPopout") !== "1") {
    return null;
  }
  const kind = params.get("tabKind")?.trim();
  if (!kind) {
    return null;
  }
  const clusterId = params.get("clusterId")?.trim() ?? "";
  const tabId = params.get("tabId")?.trim() || `${clusterId}:${kind}`;
  return {
    id: tabId,
    kind,
    clusterId,
  };
}

export type InitialHorizontalWindowTab = {
  icon: IconName;
  id: string;
  kind: "console" | "rbac-editor";
  payload: {
    clusterId: string;
    clusterYaml: string;
    kind: string;
    resourceName: string | null;
    yaml: string;
  } | null;
  title: string;
};

function parseHorizontalIcon(icon: string | null): IconName {
  if (icon === "session" || icon === "user" || icon === "role" || icon === "roleBinding") {
    return icon;
  }
  return "overview";
}

export function parseInitialHorizontalWindowTab(sourceUrl: string): InitialHorizontalWindowTab | null {
  const params = new URL(sourceUrl).searchParams;
  if (params.get("subWindowPopout") !== "1") {
    return null;
  }
  const kind = params.get("subWindowKind")?.trim();
  const id = params.get("subWindowTabId")?.trim();
  const title = params.get("subWindowTitle")?.trim();
  if (!kind || !id || !title) {
    return null;
  }

  if (kind === "console") {
    return {
      icon: parseHorizontalIcon(params.get("subWindowIcon")),
      id,
      kind: "console",
      payload: null,
      title,
    };
  }
  if (kind !== "rbac-editor") {
    return null;
  }

  const clusterId = params.get("subWindowClusterId")?.trim() ?? "";
  const clusterYaml = params.get("subWindowClusterYaml") ?? "";
  const resourceKind = params.get("subWindowResourceKind")?.trim() ?? "";
  const yaml = params.get("subWindowYaml") ?? "";
  const resourceName = params.get("subWindowResourceName");
  if (!clusterId || !clusterYaml.trim() || !resourceKind || !yaml.trim()) {
    return null;
  }

  return {
    icon: parseHorizontalIcon(params.get("subWindowIcon")),
    id,
    kind: "rbac-editor",
    payload: {
      clusterId,
      clusterYaml,
      kind: resourceKind,
      resourceName: resourceName && resourceName.trim() ? resourceName.trim() : null,
      yaml,
    },
    title,
  };
}
