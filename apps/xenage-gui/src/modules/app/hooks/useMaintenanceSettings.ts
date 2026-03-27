import { useCallback, useEffect, useState } from "react";
import type { LogLevel } from "../../../services/logger";
import { getLogLevel, logger, setLogLevel } from "../../../services/logger";
import type { StandaloneStatus } from "../../../services/standalone";
import { StandaloneService } from "../../../services/standalone";
import type { UpdateChannel, UpdateLogEvent } from "../../../services/update";
import { UpdateService } from "../../../services/update";
import { DEFAULT_CONTROL_PLANE_ARGS, DEFAULT_RUNTIME_ARGS } from "../constants";
import { parseArgsList } from "../utils";

type UseMaintenanceSettingsResult = {
  channel: UpdateChannel;
  checkingUpdates: boolean;
  controlPlaneArgs: string;
  handleChannelChange: (nextChannel: UpdateChannel) => void;
  handleCheckUpdates: () => Promise<void>;
  handleForceUpdate: () => Promise<void>;
  handleInstallStandaloneBundle: () => Promise<void>;
  handleInstallStandaloneServices: () => Promise<void>;
  handleInstallUpdate: () => Promise<void>;
  handleLogLevelChange: (nextLevel: LogLevel) => void;
  handleStartStandaloneServices: () => Promise<void>;
  handleStopStandaloneServices: () => Promise<void>;
  logLevel: LogLevel;
  managingStandalone: boolean;
  refreshStandaloneStatus: () => Promise<StandaloneStatus | null>;
  runtimeArgs: string;
  setControlPlaneArgs: (value: string) => void;
  setRuntimeArgs: (value: string) => void;
  standaloneStatus: StandaloneStatus | null;
  standaloneStatusMessage: string | null;
  updateStatus: string | null;
};

export function useMaintenanceSettings(): UseMaintenanceSettingsResult {
  const [checkingUpdates, setCheckingUpdates] = useState(false);
  const [managingStandalone, setManagingStandalone] = useState(false);
  const [updateStatus, setUpdateStatus] = useState<string | null>(null);
  const [standaloneStatusMessage, setStandaloneStatusMessage] = useState<string | null>(null);
  const [channel, setChannel] = useState<UpdateChannel>(UpdateService.getChannel());
  const [standaloneStatus, setStandaloneStatus] = useState<StandaloneStatus | null>(null);
  const [controlPlaneArgs, setControlPlaneArgs] = useState(DEFAULT_CONTROL_PLANE_ARGS);
  const [runtimeArgs, setRuntimeArgs] = useState(DEFAULT_RUNTIME_ARGS);
  const [logLevel, setAppLogLevel] = useState<LogLevel>(getLogLevel());

  const handleChannelChange = useCallback((nextChannel: UpdateChannel) => {
    logger.info("Changing update channel", { from: channel, to: nextChannel });
    setChannel(nextChannel);
    UpdateService.setChannel(nextChannel);
    setUpdateStatus(`Switched to ${nextChannel} channel.`);
  }, [channel]);

  const handleLogLevelChange = useCallback((nextLevel: LogLevel) => {
    setLogLevel(nextLevel);
    setAppLogLevel(nextLevel);
    logger.info("Application log level changed", { level: nextLevel });
    setUpdateStatus(`Log level changed to ${nextLevel}.`);
  }, []);

  const handleCheckUpdates = useCallback(async () => {
    setCheckingUpdates(true);
    setUpdateStatus("Checking GitHub releases...");
    logger.info("Manual update check requested");
    try {
      const update = await UpdateService.checkForUpdates();
      setUpdateStatus(update ? `Update available: ${update.version}` : "No updates available.");
    } finally {
      setCheckingUpdates(false);
    }
  }, []);

  const handleInstallUpdate = useCallback(async () => {
    setCheckingUpdates(true);
    setUpdateStatus("Downloading and installing update...");
    logger.info("Manual install update requested");
    try {
      const success = await UpdateService.downloadUpdate();
      setUpdateStatus(success ? "Update installed. Restarting application..." : "No update installed.");
    } finally {
      setCheckingUpdates(false);
    }
  }, []);

  const handleForceUpdate = useCallback(async () => {
    setCheckingUpdates(true);
    setUpdateStatus("Forcing dev update...");
    logger.warn("Force dev update requested");
    try {
      const success = await UpdateService.forceUpdateDev();
      setUpdateStatus(success ? "Dev update installed. Restarting application..." : "No dev update installed.");
    } finally {
      setCheckingUpdates(false);
    }
  }, []);

  const refreshStandaloneStatus = useCallback(async () => {
    try {
      const status = await StandaloneService.status();
      setStandaloneStatus(status);
      return status;
    } catch (error) {
      logger.error("Failed to fetch standalone status", error);
      setStandaloneStatusMessage("Failed to fetch standalone status.");
      return null;
    }
  }, []);

  const handleInstallStandaloneBundle = useCallback(async () => {
    setManagingStandalone(true);
    setStandaloneStatusMessage("Downloading standalone package...");
    try {
      const result = await StandaloneService.installBundle(channel);
      setStandaloneStatusMessage(`Installed standalone ${result.version} to ${result.install_dir}`);
      await refreshStandaloneStatus();
    } catch (error) {
      logger.error("Failed to install standalone package", error);
      setStandaloneStatusMessage("Standalone package installation failed.");
    } finally {
      setManagingStandalone(false);
    }
  }, [channel, refreshStandaloneStatus]);

  const handleInstallStandaloneServices = useCallback(async () => {
    setManagingStandalone(true);
    setStandaloneStatusMessage("Installing node services...");
    try {
      const cpArgs = parseArgsList(controlPlaneArgs);
      const rtArgs = parseArgsList(runtimeArgs);
      await StandaloneService.installNodeService("control-plane", cpArgs);
      await StandaloneService.installNodeService("runtime", rtArgs);
      setStandaloneStatusMessage("Node services installed.");
      await refreshStandaloneStatus();
    } catch (error) {
      logger.error("Failed to install standalone services", error);
      setStandaloneStatusMessage("Service installation failed. Check arguments and permissions.");
    } finally {
      setManagingStandalone(false);
    }
  }, [controlPlaneArgs, refreshStandaloneStatus, runtimeArgs]);

  const handleStartStandaloneServices = useCallback(async () => {
    setManagingStandalone(true);
    setStandaloneStatusMessage("Starting node services...");
    try {
      await StandaloneService.startNodeService("control-plane");
      await StandaloneService.startNodeService("runtime");
      setStandaloneStatusMessage("Node services started.");
      await refreshStandaloneStatus();
    } catch (error) {
      logger.error("Failed to start standalone services", error);
      setStandaloneStatusMessage("Failed to start services. Check service privileges.");
    } finally {
      setManagingStandalone(false);
    }
  }, [refreshStandaloneStatus]);

  const handleStopStandaloneServices = useCallback(async () => {
    setManagingStandalone(true);
    setStandaloneStatusMessage("Stopping node services...");
    try {
      await StandaloneService.stopNodeService("control-plane");
      await StandaloneService.stopNodeService("runtime");
      setStandaloneStatusMessage("Node services stopped.");
      await refreshStandaloneStatus();
    } catch (error) {
      logger.error("Failed to stop standalone services", error);
      setStandaloneStatusMessage("Failed to stop services.");
    } finally {
      setManagingStandalone(false);
    }
  }, [refreshStandaloneStatus]);

  useEffect(() => {
    let mounted = true;
    let unlisten: (() => void) | undefined;

    logger.debug("Subscribing to updater logs");
    void UpdateService.subscribeToLogs((event: UpdateLogEvent) => {
      if (!mounted) {
        return;
      }
      logger.debug("Updater event bridged to UI", event);
      setUpdateStatus(event.message);
    }).then((dispose) => {
      unlisten = dispose;
    });

    return () => {
      mounted = false;
      logger.debug("Unsubscribing from updater logs");
      unlisten?.();
    };
  }, []);

  useEffect(() => {
    let mounted = true;
    let unlisten: (() => void) | undefined;

    logger.debug("Subscribing to standalone logs");
    void StandaloneService.subscribeToLogs((event) => {
      if (!mounted) {
        return;
      }
      setStandaloneStatusMessage(event.message);
    }).then((dispose) => {
      unlisten = dispose;
    });

    return () => {
      mounted = false;
      logger.debug("Unsubscribing from standalone logs");
      unlisten?.();
    };
  }, []);

  useEffect(() => {
    void refreshStandaloneStatus();
  }, [refreshStandaloneStatus]);

  return {
    channel,
    checkingUpdates,
    controlPlaneArgs,
    handleChannelChange,
    handleCheckUpdates,
    handleForceUpdate,
    handleInstallStandaloneBundle,
    handleInstallStandaloneServices,
    handleInstallUpdate,
    handleLogLevelChange,
    handleStartStandaloneServices,
    handleStopStandaloneServices,
    logLevel,
    managingStandalone,
    refreshStandaloneStatus,
    runtimeArgs,
    setControlPlaneArgs,
    setRuntimeArgs,
    standaloneStatus,
    standaloneStatusMessage,
    updateStatus,
  };
}
