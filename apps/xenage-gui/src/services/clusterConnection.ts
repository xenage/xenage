import { invoke } from "@tauri-apps/api/core";
import type { GuiClusterSnapshot, GuiEventPage } from "../types/guiConnection";

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

export interface RbacYamlResourceEntry {
  kind: string;
  name: string;
  yaml: string;
  manifest: Record<string, unknown>;
}

export class ClusterConnectionService {
  static async fetchSnapshotFromYaml(configYaml: string): Promise<GuiClusterSnapshot> {
    return invoke<GuiClusterSnapshot>("fetch_cluster_snapshot_from_yaml", { configYaml });
  }

  static async fetchEventPageFromYaml(
    configYaml: string,
    beforeSequence?: number,
    limit = 10,
  ): Promise<GuiEventPage> {
    return invoke<GuiEventPage>("fetch_cluster_events_from_yaml", {
      configYaml,
      beforeSequence,
      limit,
    });
  }

  static async saveConnectionYaml(configYaml: string): Promise<StoredClusterConnection> {
    return invoke<StoredClusterConnection>("save_cluster_connection_yaml", { configYaml });
  }

  static async syncControlPlaneUrls(
    connectionId: string,
    controlPlaneUrls: string[],
  ): Promise<StoredClusterConnection> {
    return invoke<StoredClusterConnection>("sync_cluster_connection_control_plane_urls", {
      connectionId,
      controlPlaneUrls,
    });
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

  static async listRbacYamlResources(
    configYaml: string,
    kind: string,
  ): Promise<RbacYamlResourceEntry[]> {
    return invoke<RbacYamlResourceEntry[]>("list_rbac_yaml_resources_from_yaml", {
      configYaml,
      kind,
    });
  }

  static async applyRbacYamlResource(
    configYaml: string,
    manifestYaml: string,
    deleteMode: boolean,
  ): Promise<Record<string, unknown>> {
    return invoke<Record<string, unknown>>("apply_rbac_yaml_resource_from_yaml", {
      configYaml,
      manifestYaml,
      deleteMode,
    });
  }
}
