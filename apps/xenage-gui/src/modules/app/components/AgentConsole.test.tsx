import { fireEvent, render, screen } from "@testing-library/react";
import { vi } from "vitest";
import { AgentConsole } from "./AgentConsole";

describe("AgentConsole", () => {
  it("executes open resource command", () => {
    const onOpenRoles = vi.fn();
    render(
      <>
        <button className="resource-link" onClick={onOpenRoles} type="button">Roles</button>
        <AgentConsole />
      </>,
    );

    const input = screen.getByLabelText("Agent command");
    fireEvent.change(input, { target: { value: "open resource Roles" } });
    fireEvent.keyDown(input, { key: "Enter" });

    expect(onOpenRoles).toHaveBeenCalledTimes(1);
    expect(screen.getByText(/ok: Open command executed/)).toBeInTheDocument();
  });

  it("returns table info", () => {
    render(
      <>
        <div className="schema-table__row" />
        <div className="schema-table__row" />
        <AgentConsole />
      </>,
    );

    const input = screen.getByLabelText("Agent command");
    fireEvent.change(input, { target: { value: "table info" } });
    fireEvent.keyDown(input, { key: "Enter" });

    expect(screen.getByText(/Table rows: 2, selected: 0/)).toBeInTheDocument();
  });

  it("focuses window target", () => {
    render(
      <>
        <div className="workspace" data-testid="workspace" />
        <AgentConsole />
      </>,
    );

    const input = screen.getByLabelText("Agent command");
    fireEvent.change(input, { target: { value: "focus window workspace" } });
    fireEvent.keyDown(input, { key: "Enter" });

    expect(screen.getByTestId("workspace")).toHaveFocus();
  });

  it("selects element by selector and marks it", () => {
    render(
      <>
        <div className="schema-table__row" data-testid="row-target" />
        <AgentConsole />
      </>,
    );

    const input = screen.getByLabelText("Agent command");
    fireEvent.change(input, { target: { value: "select .schema-table__row" } });
    fireEvent.keyDown(input, { key: "Enter" });

    expect(screen.getByTestId("row-target")).toHaveClass("agent-console-selected");
  });
});
