import type { OpenTab } from "./types";

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
