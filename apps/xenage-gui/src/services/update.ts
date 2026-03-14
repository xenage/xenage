import { invoke } from '@tauri-apps/api/core';
import { listen } from '@tauri-apps/api/event';
import { relaunch } from '@tauri-apps/plugin-process';
import { logger } from './logger';

/**
 * Update service abstraction for Xenage GUI.
 * Integrates with Tauri's updater plugin.
 */

export type UpdateChannel = 'main' | 'dev';

export interface UpdateInfo {
  current_version?: string;
  version: string;
  notes?: string;
  pub_date?: string;
  target?: string;
}

export interface UpdateLogEvent {
  channel: UpdateChannel;
  endpoint: string;
  step: string;
  message: string;
  force: boolean;
  current_version?: string;
  version?: string;
  target?: string;
  downloaded_bytes?: number;
  content_length?: number;
}

export class UpdateService {
  private static readonly CHANNEL_KEY = 'xenage-update-channel';
  private static readonly LOG_EVENT = 'updater://log';

  static getChannel(): UpdateChannel {
    const channel = localStorage.getItem(this.CHANNEL_KEY);
    return (channel as UpdateChannel) || 'main';
  }

  static setChannel(channel: UpdateChannel) {
    localStorage.setItem(this.CHANNEL_KEY, channel);
    logger.info('Update channel changed', { channel });
  }

  static async subscribeToLogs(handler: (event: UpdateLogEvent) => void): Promise<() => void> {
    return listen<UpdateLogEvent>(this.LOG_EVENT, ({ payload }) => {
      logger.debug('Updater event received', payload);
      handler(payload);
    });
  }

  /**
   * Checks if a new update is available.
   * Uses the Tauri updater plugin.
   */
  static async checkForUpdates(): Promise<UpdateInfo | null> {
    const channel = this.getChannel();
    logger.info('Checking for updates', { channel });
    
    try {
      const update = await invoke<UpdateInfo | null>('check_for_updates', {
        channel,
        force: false,
      });

      if (update) {
        logger.info('Update available', update);
        return update;
      }
      logger.info('No updates available', { channel });
    } catch (error) {
      logger.error('Failed to check for updates', error);
    }

    return null; 
  }
  /**
   * Downloads and installs the update.
   */
  static async downloadUpdate(): Promise<boolean> {
    const channel = this.getChannel();
    logger.info('Downloading and installing update', { channel });
    
    try {
      const installed = await invoke<boolean>('install_update', {
        channel,
        force: false,
      });

      if (installed) {
        logger.info('Update installed successfully, restarting application');
        void relaunch().catch((error) => {
          logger.error('Failed to relaunch after successful update install', error);
        });
        return true;
      }
      logger.warn('Install update returned false', { channel });
    } catch (error) {
      logger.error('Failed to download/install update', error);
    }

    return false;
  }

  /**
   * Forces an update on the dev channel regardless of the current version.
   * In a real app, this might involve ignoring version checks if possible,
   * but here we just re-check and prompt for download.
   */
  static async forceUpdateDev(): Promise<boolean> {
    const channel = this.getChannel();
    if (channel !== 'dev') {
      logger.warn('Force update is only available on dev channel');
      return false;
    }
 
    try {
      const installed = await invoke<boolean>('install_update', {
        channel,
        force: true,
      });

      if (installed) {
        logger.info('Dev update installed successfully, restarting application');
        void relaunch().catch((error) => {
          logger.error('Failed to relaunch after successful dev update install', error);
        });
      } else {
        logger.warn('Dev force update returned false');
      }

      return installed;
    } catch (error) {
      logger.error('Failed to force update dev release', error);
      return false;
    }
  }
}
