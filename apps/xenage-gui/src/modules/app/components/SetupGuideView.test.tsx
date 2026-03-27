import { fireEvent, render, screen } from "@testing-library/react";
import { vi } from "vitest";
import { SetupGuideView } from "./SetupGuideView";

describe("SetupGuideView", () => {
  it("renders YAML editor state and triggers connect/yaml handlers", () => {
    const onConnect = vi.fn(async () => {});
    const onYamlChange = vi.fn();

    render(
      <SetupGuideView
        connectingGui={false}
        guiConnectionStatus="Ready to connect"
        guiConnectionYaml="apiVersion: xenage.io/v1alpha1"
        onConnect={onConnect}
        onYamlChange={onYamlChange}
      />,
    );

    expect(screen.getByText("Setup Guide")).toBeInTheDocument();
    expect(screen.getByText("Ready to connect")).toBeInTheDocument();

    const yamlEditor = screen.getByRole("textbox");
    fireEvent.change(yamlEditor, { target: { value: "kind: ClusterConnection" } });
    expect(onYamlChange).toHaveBeenCalledWith("kind: ClusterConnection");

    fireEvent.click(screen.getByRole("button", { name: "Connect" }));
    expect(onConnect).toHaveBeenCalledTimes(1);
  });

  it("disables the connect button while connection is in progress", () => {
    render(
      <SetupGuideView
        connectingGui
        guiConnectionStatus={null}
        guiConnectionYaml=""
        onConnect={vi.fn(async () => {})}
        onYamlChange={vi.fn()}
      />,
    );

    const connectButton = screen.getByRole("button", { name: "Connecting..." });
    expect(connectButton).toBeDisabled();
  });
});
