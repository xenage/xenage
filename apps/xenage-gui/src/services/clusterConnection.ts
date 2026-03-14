import { invoke } from "@tauri-apps/api/core";
import type { GuiClusterSnapshot } from "../types/guiConnection";

export interface StoredClusterConnection {
  id: string;
  name: string;
  yaml: string;
}

export interface StoredClusterUiPrefs {
  connection_id: string;
  name: string;
  accent: string;
}

export class ClusterConnectionService {
  static async fetchSnapshotFromYaml(configYaml: string): Promise<GuiClusterSnapshot> {
    return invoke<GuiClusterSnapshot>("fetch_cluster_snapshot_from_yaml", { configYaml });
  }

  static async saveConnectionYaml(configYaml: string): Promise<StoredClusterConnection> {
    return invoke<StoredClusterConnection>("save_cluster_connection_yaml", { configYaml });
  }

  static async listConnectionYamls(): Promise<StoredClusterConnection[]> {
    return invoke<StoredClusterConnection[]>("list_cluster_connection_yamls");
  }

  static async listClusterUiPrefs(): Promise<StoredClusterUiPrefs[]> {
    return invoke<StoredClusterUiPrefs[]>("list_cluster_ui_prefs");
  }

  static async saveClusterUiPrefsEntry(
    connectionId: string,
    name: string,
    accent: string,
  ): Promise<StoredClusterUiPrefs> {
    return invoke<StoredClusterUiPrefs>("save_cluster_ui_prefs_entry", {
      connectionId,
      name,
      accent,
    });
  }

  static async deleteClusterConnection(connectionId: string): Promise<void> {
    await invoke("delete_cluster_connection", { connectionId });
  }
}
