import { fireEvent, render, screen } from "@testing-library/react";
import type { ComponentProps } from "react";
import { vi } from "vitest";
import { SettingsView } from "./SettingsView";

function createProps(): ComponentProps<typeof SettingsView> {
  return {
    channel: "dev",
    checkingUpdates: false,
    logLevel: "info",
    onChannelChange: vi.fn(),
    onCheckUpdates: vi.fn(async () => {}),
    onForceUpdate: vi.fn(async () => {}),
    onInstallStandaloneBundle: vi.fn(async () => {}),
    onInstallStandaloneServices: vi.fn(async () => {}),
    onInstallUpdate: vi.fn(async () => {}),
    onLogLevelChange: vi.fn(),
    onRefreshStandaloneStatus: vi.fn(async () => null),
    onStartStandaloneServices: vi.fn(async () => {}),
    onStopStandaloneServices: vi.fn(async () => {}),
    onUpdateControlPlaneArgs: vi.fn(),
    onUpdateRuntimeArgs: vi.fn(),
    standaloneBusy: false,
    standaloneControlPlaneArgs: "--foo",
    standaloneRuntimeArgs: "--bar",
    standaloneStatus: {
      installed: true,
      install_dir: "/tmp/xenage",
      asset_name: "xenage.tar.gz",
      version: "1.2.3",
      control_plane_service: {
        state: "running",
      },
      runtime_service: {
        state: "running",
      },
    },
    standaloneStatusMessage: "Standalone healthy",
    updateStatus: "No updates available",
  };
}

describe("SettingsView", () => {
  it("renders settings sections and triggers diagnostics/update controls", () => {
    const props = createProps();

    render(<SettingsView {...props} />);

    expect(screen.getByText("Settings")).toBeInTheDocument();
    expect(screen.getByText("Standalone healthy")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Force dev update" })).toBeInTheDocument();

    fireEvent.change(screen.getByRole("combobox", { name: "Log level" }), {
      target: { value: "error" },
    });
    expect(props.onLogLevelChange).toHaveBeenCalledWith("error");

    fireEvent.change(screen.getByRole("combobox", { name: "Channel" }), {
      target: { value: "main" },
    });
    expect(props.onChannelChange).toHaveBeenCalledWith("main");

    fireEvent.click(screen.getByRole("button", { name: "Check version" }));
    fireEvent.click(screen.getByRole("button", { name: "Install update" }));
    fireEvent.click(screen.getByRole("button", { name: "Force dev update" }));
    expect(props.onCheckUpdates).toHaveBeenCalledTimes(1);
    expect(props.onInstallUpdate).toHaveBeenCalledTimes(1);
    expect(props.onForceUpdate).toHaveBeenCalledTimes(1);
  });

  it("hides the force update action on the main channel", () => {
    const props = createProps();

    render(<SettingsView {...props} channel="main" />);

    expect(screen.queryByRole("button", { name: "Force dev update" })).not.toBeInTheDocument();
  });

  it("disables update and standalone actions while busy states are active", () => {
    const props = createProps();

    render(<SettingsView {...props} checkingUpdates standaloneBusy />);

    expect(screen.getByRole("button", { name: "Checking..." })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Install update" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Working..." })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Install services" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Start services" })).toBeDisabled();
  });
});
