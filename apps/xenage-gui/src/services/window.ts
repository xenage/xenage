import { invoke } from "@tauri-apps/api/core";

export interface DetachedTabWindowRequest extends Record<string, unknown> {
  sourceUrl: string;
  tabId: string;
  tabKind: string;
  clusterId: string;
  tabLabel: string;
  clusterLabel: string;
}

export interface DetachedHorizontalTabWindowRequest extends Record<string, unknown> {
  sourceUrl: string;
  subWindowKind: "console" | "rbac-editor";
  tabIcon: string;
  tabId: string;
  tabTitle: string;
  clusterId: string;
  clusterLabel: string;
  clusterYaml?: string;
  resourceKind?: string;
  resourceName?: string;
  yaml?: string;
}

export class WindowService {
  static async openDetachedTabWindow(request: DetachedTabWindowRequest): Promise<string> {
    return invoke<string>("open_detached_tab_window", request);
  }

  static async openDetachedHorizontalTabWindow(
    request: DetachedHorizontalTabWindowRequest,
  ): Promise<string> {
    return invoke<string>("open_detached_horizontal_subwindow", request);
  }
}
