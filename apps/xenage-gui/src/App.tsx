import { useState } from "react";
import "./App.css";
import { UpdateService } from "./services/update";
import type { UpdateChannel } from "./services/update";

function App() {
  const [checking, setChecking] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [channel, setChannel] = useState<UpdateChannel>(UpdateService.getChannel());

  const handleCheckUpdates = async () => {
    setChecking(true);
    setStatus("Checking for updates...");
    try {
      const update = await UpdateService.checkForUpdates();
      if (update) {
        setStatus(`Update available: ${update.version}`);
        const shouldUpdate = window.confirm(`Update available: ${update.version}. Download and install now?`);
        if (shouldUpdate) {
          setStatus("Downloading and installing update...");
          await UpdateService.downloadUpdate();
        }
      } else {
        setStatus("No updates available.");
      }
    } catch (error) {
      console.error(error);
      setStatus("Error checking for updates.");
    } finally {
      setChecking(false);
    }
  };

  const handleChannelChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const newChannel = e.target.value as UpdateChannel;
    setChannel(newChannel);
    UpdateService.setChannel(newChannel);
    setStatus(`Switched to ${newChannel} channel.`);
  };

  return (
    <main className="container">
      <h1>Xenage</h1>
      <div className="card">
        <div className="settings">
          <label htmlFor="channel-select">Update Channel: </label>
          <select id="channel-select" value={channel} onChange={handleChannelChange}>
            <option value="main">Main (Stable)</option>
            <option value="dev">Development</option>
          </select>
        </div>
        <br />
        <button onClick={handleCheckUpdates} disabled={checking}>
          {checking ? "Checking..." : "Check for updates"}
        </button>
        {status && <p className="status-message">{status}</p>}
      </div>
    </main>
  );
}

export default App;
