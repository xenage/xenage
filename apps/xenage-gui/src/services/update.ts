import { check } from '@tauri-apps/plugin-updater';
import { ask } from '@tauri-apps/plugin-dialog';
import { relaunch } from '@tauri-apps/plugin-process';

/**
 * Update service abstraction for Xenage GUI.
 * Integrates with Tauri's updater plugin.
 */

export type UpdateChannel = 'main' | 'dev';

export interface UpdateInfo {
  version: string;
  notes?: string;
  pub_date?: string;
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
      // In Tauri 2.0, endpoints are configured in tauri.conf.json.
      // We check for updates using the default configuration.
      const update = await check();
      if (update) {
        console.log(`Update available: ${update.version}`);
        return {
          version: update.version,
          notes: typeof update.body === 'string' ? update.body : undefined,
          pub_date: update.date,
        };
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
      const update = await check();
      if (update) {
        let downloaded = 0;
        let contentLength = 0;

        await update.downloadAndInstall((event) => {
          switch (event.event) {
            case 'Started':
              contentLength = event.data.contentLength || 0;
              console.log(`started downloading ${event.data.contentLength} bytes`);
              break;
            case 'Progress':
              downloaded += event.data.chunkLength;
              console.log(`downloaded ${downloaded} from ${contentLength}`);
              break;
            case 'Finished':
              console.log('download finished');
              break;
          }
        });

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
}
