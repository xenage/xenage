import { invoke } from '@tauri-apps/api/core';
import { ask } from '@tauri-apps/plugin-dialog';
import { relaunch } from '@tauri-apps/plugin-process';

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

export class UpdateService {
  private static readonly CHANNEL_KEY = 'xenage-update-channel';

  static getChannel(): UpdateChannel {
    const channel = localStorage.getItem(this.CHANNEL_KEY);
    return (channel as UpdateChannel) || 'main';
  }

  static setChannel(channel: UpdateChannel) {
    localStorage.setItem(this.CHANNEL_KEY, channel);
  }

  /**
   * Checks if a new update is available.
   * Uses the Tauri updater plugin.
   */
  static async checkForUpdates(): Promise<UpdateInfo | null> {
    const channel = this.getChannel();
    console.log(`Checking for updates on channel: ${channel}...`);
    
    try {
      const update = await invoke<UpdateInfo | null>('check_for_updates', {
        channel,
        force: false,
      });

      if (update) {
        console.log(`Update available: ${update.version}`);
        return update;
      }
    } catch (error) {
      console.error('Failed to check for updates:', error);
    }

    return null; 
  }
  /**
   * Downloads and installs the update.
   */
  static async downloadUpdate(): Promise<boolean> {
    const channel = this.getChannel();
    console.log(`Downloading and installing update for channel: ${channel}...`);
    
    try {
      const installed = await invoke<boolean>('install_update', {
        channel,
        force: false,
      });

      if (installed) {
        const confirm = await ask('The update has been installed. Do you want to restart the application now?', {
          title: 'Update successful',
          kind: 'info',
        });

        if (confirm) {
          await relaunch();
        }
        return true;
      }
    } catch (error) {
      console.error('Failed to download/install update:', error);
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
      console.warn('Force update is only available on dev channel');
      return false;
    }
 
    try {
      const installed = await invoke<boolean>('install_update', {
        channel,
        force: true,
      });

      if (installed) {
        const confirm = await ask('The dev update has been installed. Do you want to restart the application now?', {
          title: 'Update successful',
          kind: 'info',
        });

        if (confirm) {
          await relaunch();
        }
      }

      return installed;
    } catch (error) {
      console.error('Failed to force update dev release:', error);
      return false;
    }
  }
}
