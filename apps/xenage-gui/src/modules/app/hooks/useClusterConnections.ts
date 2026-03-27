import { useCallback, useEffect, useMemo, useState } from "react";
import type { Dispatch, SetStateAction } from "react";
import { ClusterConnectionService } from "../../../services/clusterConnection";
import type {
  StoredClusterConnection,
  StoredClusterUiPrefs,
} from "../../../services/clusterConnection";
import { logger } from "../../../services/logger";
import type { GuiClusterSnapshot } from "../../../types/guiConnection";
import { DEFAULT_GUI_CONNECTION_YAML } from "../constants";
import type { ClusterEntry, ClusterUiPrefs } from "../types";

type UseClusterConnectionsResult = {
  activeClusterId: string;
  clusterDraftAccent: string;
  clusterDraftName: string;
  clusters: ClusterEntry[];
  connectGui: () => Promise<{ saved: StoredClusterConnection; snapshot: GuiClusterSnapshot } | null>;
  connectingGui: boolean;
  connectionConfigs: StoredClusterConnection[];
  deleteClusterFromEditor: () => Promise<string | null>;
  editingClusterId: string | null;
  expandedClusters: Record<string, boolean>;
  guiConnectionStatus: string | null;
  guiConnectionYaml: string;
  openClusterConfigEditor: (clusterId: string) => void;
  saveClusterConfigEditor: () => Promise<void>;
  setActiveClusterId: (value: string) => void;
  setClusterDraftAccent: (value: string) => void;
  setClusterDraftName: (value: string) => void;
  setConnectionConfigs: Dispatch<SetStateAction<StoredClusterConnection[]>>;
  setEditingClusterId: (value: string | null) => void;
  setExpandedClusters: Dispatch<SetStateAction<Record<string, boolean>>>;
  setGuiConnectionYaml: (value: string) => void;
  shareClusterConfigFromEditor: () => Promise<void>;
  shareCopyNotice: string | null;
};

export function useClusterConnections({
  initialClusterId = "",
}: {
  initialClusterId?: string;
} = {}): UseClusterConnectionsResult {
  const [guiConnectionYaml, setGuiConnectionYaml] = useState(DEFAULT_GUI_CONNECTION_YAML);
  const [connectionConfigs, setConnectionConfigs] = useState<StoredClusterConnection[]>([]);
  const [clusterUiPrefs, setClusterUiPrefs] = useState<Record<string, ClusterUiPrefs>>({});
  const [activeClusterId, setActiveClusterId] = useState(initialClusterId);
  const [expandedClusters, setExpandedClusters] = useState<Record<string, boolean>>({});
  const [guiConnectionStatus, setGuiConnectionStatus] = useState<string | null>(null);
  const [connectingGui, setConnectingGui] = useState(false);
  const [editingClusterId, setEditingClusterId] = useState<string | null>(null);
  const [clusterDraftName, setClusterDraftName] = useState("");
  const [clusterDraftAccent, setClusterDraftAccent] = useState("#22c55e");
  const [shareCopyNotice, setShareCopyNotice] = useState<string | null>(null);

  const clusters = useMemo(
    () =>
      connectionConfigs.map((item) => ({
        id: item.id,
        name: clusterUiPrefs[item.id]?.name || item.name,
        accent: clusterUiPrefs[item.id]?.accent || "#22c55e",
      })),
    [clusterUiPrefs, connectionConfigs],
  );

  const loadConnections = useCallback(async () => {
    try {
      const [saved, prefs] = await Promise.all([
        ClusterConnectionService.listConnectionYamls(),
        ClusterConnectionService.listClusterUiPrefs(),
      ]);
      setConnectionConfigs(saved);
      setClusterUiPrefs(
        prefs.reduce<Record<string, ClusterUiPrefs>>((acc, item: StoredClusterUiPrefs) => {
          acc[item.connection_id] = {
            name: item.name,
            accent: item.accent,
          };
          return acc;
        }, {}),
      );
      if (saved.length > 0) {
        setActiveClusterId((current) => (saved.some((item) => item.id === current) ? current : saved[0].id));
        setExpandedClusters((current) => {
          if (Object.keys(current).length > 0) {
            return current;
          }
          return saved.reduce<Record<string, boolean>>((acc, item, index) => {
            acc[item.id] = index === 0;
            return acc;
          }, {});
        });
        setGuiConnectionYaml((current) => (current === DEFAULT_GUI_CONNECTION_YAML ? saved[0].yaml : current));
      } else {
        setActiveClusterId("");
      }
    } catch (error) {
      logger.error("Failed to load saved cluster configs", error);
    }
  }, []);

  const connectGui = useCallback(async () => {
    setConnectingGui(true);
    setGuiConnectionStatus("Connecting to control-plane...");
    try {
      const snapshot = await ClusterConnectionService.fetchSnapshotFromYaml(guiConnectionYaml);
      const saved = await ClusterConnectionService.saveConnectionYaml(guiConnectionYaml);
      const allSaved = await ClusterConnectionService.listConnectionYamls();
      setConnectionConfigs(allSaved);
      setActiveClusterId(saved.id);
      setExpandedClusters((current) => ({ ...current, [saved.id]: true }));
      setGuiConnectionStatus(
        `Connected to ${snapshot.group_id} (state ${snapshot.state_version}, epoch ${snapshot.leader_epoch}).`,
      );
      return { saved, snapshot };
    } catch (error) {
      logger.error("Failed to connect GUI to cluster", error);
      setGuiConnectionStatus(
        error instanceof Error ? error.message : "Failed to connect using provided YAML config.",
      );
      return null;
    } finally {
      setConnectingGui(false);
    }
  }, [guiConnectionYaml]);

  const openClusterConfigEditor = useCallback((clusterId: string) => {
    const connection = connectionConfigs.find((item) => item.id === clusterId);
    if (!connection) {
      return;
    }
    const prefs = clusterUiPrefs[clusterId];
    setClusterDraftName(prefs?.name || connection.name);
    setClusterDraftAccent(prefs?.accent || "#22c55e");
    setShareCopyNotice(null);
    setEditingClusterId(clusterId);
  }, [clusterUiPrefs, connectionConfigs]);

  const saveClusterConfigEditor = useCallback(async () => {
    if (!editingClusterId) {
      return;
    }
    try {
      const saved = await ClusterConnectionService.saveClusterUiPrefsEntry(
        editingClusterId,
        clusterDraftName,
        clusterDraftAccent,
      );
      setClusterUiPrefs((current) => ({
        ...current,
        [saved.connection_id]: {
          name: saved.name,
          accent: saved.accent,
        },
      }));
      setEditingClusterId(null);
    } catch (error) {
      logger.error("Failed to save cluster UI prefs", error);
    }
  }, [clusterDraftAccent, clusterDraftName, editingClusterId]);

  const deleteClusterFromEditor = useCallback(async () => {
    if (!editingClusterId) {
      return null;
    }
    try {
      await ClusterConnectionService.deleteClusterConnection(editingClusterId);
      setConnectionConfigs((current) => current.filter((item) => item.id !== editingClusterId));
      setClusterUiPrefs((current) => {
        const next = { ...current };
        delete next[editingClusterId];
        return next;
      });
      setExpandedClusters((current) => {
        const next = { ...current };
        delete next[editingClusterId];
        return next;
      });
      setEditingClusterId(null);
      await loadConnections();
      return editingClusterId;
    } catch (error) {
      logger.error("Failed to delete cluster connection", error);
      return null;
    }
  }, [editingClusterId, loadConnections]);

  const shareClusterConfigFromEditor = useCallback(async () => {
    if (!editingClusterId) {
      return;
    }
    const config = connectionConfigs.find((item) => item.id === editingClusterId);
    if (!config) {
      return;
    }
    try {
      await navigator.clipboard.writeText(config.yaml);
      setShareCopyNotice("Config copied");
      window.setTimeout(() => setShareCopyNotice((current) => (current === "Config copied" ? null : current)), 1800);
    } catch (error) {
      logger.error("Failed to copy cluster yaml to clipboard", error);
      setGuiConnectionStatus("Failed to copy cluster config to clipboard.");
    }
  }, [connectionConfigs, editingClusterId]);

  useEffect(() => {
    void loadConnections();
  }, [loadConnections]);

  return {
    activeClusterId,
    clusterDraftAccent,
    clusterDraftName,
    clusters,
    connectGui,
    connectingGui,
    connectionConfigs,
    deleteClusterFromEditor,
    editingClusterId,
    expandedClusters,
    guiConnectionStatus,
    guiConnectionYaml,
    openClusterConfigEditor,
    saveClusterConfigEditor,
    setActiveClusterId,
    setClusterDraftAccent,
    setClusterDraftName,
    setConnectionConfigs,
    setEditingClusterId,
    setExpandedClusters,
    setGuiConnectionYaml,
    shareClusterConfigFromEditor,
    shareCopyNotice,
  };
}
