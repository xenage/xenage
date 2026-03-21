import { invoke } from "@tauri-apps/api/core";

export interface DetachedTabWindowRequest extends Record<string, unknown> {
  sourceUrl: string;
  tabId: string;
  tabKind: string;
  clusterId: string;
  tabLabel: string;
  clusterLabel: string;
}

export class WindowService {
  static async openDetachedTabWindow(request: DetachedTabWindowRequest): Promise<string> {
    return invoke<string>("open_detached_tab_window", request);
  }
}
