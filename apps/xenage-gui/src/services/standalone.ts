import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { logger } from "./logger";
import type { UpdateChannel } from "./update";

export type NodeRole = "control-plane" | "runtime";

export interface StandaloneLogEvent {
  channel: string;
  asset: string;
  step: string;
  message: string;
}

export interface ServiceStatus {
  state: string;
  details?: string;
}

export interface StandaloneStatus {
  installed: boolean;
  install_dir: string;
  asset_name: string;
  version?: string;
  control_plane_service: ServiceStatus;
  runtime_service: ServiceStatus;
}

export interface StandaloneInstallResult {
  version: string;
  install_dir: string;
  asset_name: string;
}

export class StandaloneService {
  private static readonly LOG_EVENT = "standalone://log";

  static async subscribeToLogs(handler: (event: StandaloneLogEvent) => void): Promise<() => void> {
    try {
      return await listen<StandaloneLogEvent>(this.LOG_EVENT, ({ payload }) => {
        logger.debug("Standalone event received", payload);
        handler(payload);
      });
    } catch (error) {
      logger.warn("Standalone log subscription unavailable", error);
      return () => {};
    }
  }

  static async installBundle(channel: UpdateChannel): Promise<StandaloneInstallResult> {
    logger.info("Installing standalone bundle", { channel });
    return invoke<StandaloneInstallResult>("install_standalone_bundle", { channel });
  }

  static async installNodeService(role: NodeRole, args: string[]): Promise<string> {
    logger.info("Installing node service", { role, argCount: args.length });
    return invoke<string>("install_node_service", { role, args });
  }

  static async startNodeService(role: NodeRole): Promise<string> {
    logger.info("Starting node service", { role });
    return invoke<string>("start_node_service", { role });
  }

  static async stopNodeService(role: NodeRole): Promise<string> {
    logger.info("Stopping node service", { role });
    return invoke<string>("stop_node_service", { role });
  }

  static async status(): Promise<StandaloneStatus> {
    return invoke<StandaloneStatus>("standalone_status");
  }
}
