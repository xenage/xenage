import { beforeEach, describe, expect, it, vi } from "vitest";
import { UpdateService, type UpdateInfo } from "./update";

const invokeMock = vi.fn();
const listenMock = vi.fn();
const relaunchMock = vi.fn();

vi.mock("@tauri-apps/api/core", () => ({
  invoke: (...args: unknown[]) => invokeMock(...args),
}));

vi.mock("@tauri-apps/api/event", () => ({
  listen: (...args: unknown[]) => listenMock(...args),
}));

vi.mock("@tauri-apps/plugin-process", () => ({
  relaunch: (...args: unknown[]) => relaunchMock(...args),
}));

vi.mock("./logger", () => ({
  logger: {
    debug: vi.fn(),
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
  },
}));

describe("UpdateService", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it("uses main channel by default", () => {
    expect(UpdateService.getChannel()).toBe("main");
  });

  it("passes selected channel to check_for_updates", async () => {
    localStorage.setItem("xenage-update-channel", "dev");
    const payload: UpdateInfo = {
      version: "1.2.3",
      current_version: "1.2.2",
      target: "linux-x86_64",
    };
    invokeMock.mockResolvedValueOnce(payload);

    const result = await UpdateService.checkForUpdates();

    expect(invokeMock).toHaveBeenCalledWith("check_for_updates", {
      channel: "dev",
      force: false,
    });
    expect(result).toEqual(payload);
  });

  it("installs and relaunches when update install succeeds", async () => {
    localStorage.setItem("xenage-update-channel", "dev");
    invokeMock.mockResolvedValueOnce(true);
    relaunchMock.mockResolvedValueOnce(undefined);

    const installed = await UpdateService.downloadUpdate();

    expect(installed).toBe(true);
    expect(invokeMock).toHaveBeenCalledWith("install_update", {
      channel: "dev",
      force: false,
    });
    expect(relaunchMock).toHaveBeenCalledTimes(1);
  });

  it("does not call force install outside dev channel", async () => {
    localStorage.setItem("xenage-update-channel", "main");

    const installed = await UpdateService.forceUpdateDev();

    expect(installed).toBe(false);
    expect(invokeMock).not.toHaveBeenCalled();
    expect(relaunchMock).not.toHaveBeenCalled();
  });

  it("forces install on dev channel", async () => {
    localStorage.setItem("xenage-update-channel", "dev");
    invokeMock.mockResolvedValueOnce(true);
    relaunchMock.mockResolvedValueOnce(undefined);

    const installed = await UpdateService.forceUpdateDev();

    expect(installed).toBe(true);
    expect(invokeMock).toHaveBeenCalledWith("install_update", {
      channel: "dev",
      force: true,
    });
    expect(relaunchMock).toHaveBeenCalledTimes(1);
  });

  it("subscribes to updater log stream", async () => {
    const unlisten = vi.fn();
    const payload = {
      channel: "dev",
      endpoint: "https://example.com/latest.json",
      step: "download-progress",
      message: "progress",
      force: false,
    };

    listenMock.mockImplementationOnce(async (_event, cb) => {
      cb({ payload });
      return unlisten;
    });

    const handler = vi.fn();
    const dispose = await UpdateService.subscribeToLogs(handler);

    expect(handler).toHaveBeenCalledWith(payload);
    expect(dispose).toBe(unlisten);
  });
});
