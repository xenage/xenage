import { useCallback, useMemo, useState } from "react";

type ConsoleLine = {
  id: number;
  text: string;
};

type CommandResult = {
  message: string;
  success: boolean;
};

function focusElement(element: HTMLElement): void {
  if (!element.hasAttribute("tabindex")) {
    element.setAttribute("tabindex", "-1");
  }
  element.focus();
}

function findOpenTarget(command: string): HTMLElement | null {
  const normalized = command.trim().toLowerCase();
  if (normalized === "settings" || normalized === "window settings") {
    return document.querySelector("button[title='Open settings']");
  }
  if (normalized === "setup" || normalized === "window setup") {
    return document.querySelector("button[title='Open setup guide']");
  }

  const resourceLabel = normalized.startsWith("resource ")
    ? normalized.slice("resource ".length).trim()
    : normalized;
  if (!resourceLabel) {
    return null;
  }
  const resourceButtons = Array.from(document.querySelectorAll<HTMLButtonElement>("button.resource-link"));
  return resourceButtons.find((item) => item.textContent?.trim().toLowerCase() === resourceLabel) ?? null;
}

function findWindowTarget(windowName: string): HTMLElement | null {
  const normalized = windowName.trim().toLowerCase();
  if (normalized === "sidebar") {
    return document.querySelector<HTMLElement>(".navigator");
  }
  if (normalized === "workspace") {
    return document.querySelector<HTMLElement>(".workspace");
  }
  if (normalized === "table") {
    return document.querySelector<HTMLElement>(".schema-table");
  }
  return null;
}

function clearSelectionMarkers(): void {
  const selected = document.querySelectorAll<HTMLElement>(".agent-console-selected");
  selected.forEach((item) => item.classList.remove("agent-console-selected"));
}

function parseCommand(raw: string): CommandResult {
  const command = raw.trim();
  if (!command) {
    return { message: "Empty command", success: false };
  }
  if (command === "help") {
    return {
      message: "Commands: open <resource|settings|setup>, focus window <name>, focus <selector>, select <selector>, table info",
      success: true,
    };
  }
  if (command === "table info") {
    const rowCount = document.querySelectorAll(".schema-table__row").length;
    const selectedCount = document.querySelectorAll(".schema-table__row input[type='checkbox']:checked").length;
    return {
      message: `Table rows: ${rowCount}, selected: ${selectedCount}`,
      success: true,
    };
  }
  if (command.startsWith("open ")) {
    const target = findOpenTarget(command.slice("open ".length));
    if (!target) {
      return { message: "Open target not found", success: false };
    }
    target.click();
    return { message: "Open command executed", success: true };
  }
  if (command.startsWith("focus window ")) {
    const windowName = command.slice("focus window ".length).trim();
    const target = findWindowTarget(windowName);
    if (!target) {
      return { message: "Window target not found", success: false };
    }
    focusElement(target);
    return { message: `Focused window ${windowName}`, success: true };
  }
  if (command.startsWith("focus ")) {
    const selector = command.slice("focus ".length).trim();
    const target = document.querySelector<HTMLElement>(selector);
    if (!target) {
      return { message: `Selector not found: ${selector}`, success: false };
    }
    focusElement(target);
    return { message: `Focused ${selector}`, success: true };
  }
  if (command.startsWith("select ")) {
    const selector = command.slice("select ".length).trim();
    const target = document.querySelector<HTMLElement>(selector);
    if (!target) {
      return { message: `Selector not found: ${selector}`, success: false };
    }
    clearSelectionMarkers();
    target.classList.add("agent-console-selected");
    focusElement(target);
    return { message: `Selected ${selector}`, success: true };
  }
  return { message: "Unknown command", success: false };
}

export function AgentConsole() {
  const [command, setCommand] = useState("");
  const [history, setHistory] = useState<ConsoleLine[]>([]);

  const addHistory = useCallback((line: string) => {
    setHistory((current) => {
      const next = [...current, { id: current.length + 1, text: line }];
      return next.slice(-18);
    });
  }, []);

  const shellPrompt = useMemo(() => "agent-console$", []);

  return (
    <div className="agent-console-pane">
      <div className="agent-console__header">
        <span>{shellPrompt}</span>
      </div>
      <label className="agent-console__input-row">
        <span>Command</span>
        <input
          aria-label="Agent command"
          onChange={(event) => setCommand(event.target.value)}
          onKeyDown={(event) => {
            if (event.key !== "Enter") {
              return;
            }
            event.preventDefault();
            addHistory(`> ${command}`);
            const result = parseCommand(command);
            addHistory(`${result.success ? "ok" : "err"}: ${result.message}`);
            setCommand("");
          }}
          placeholder="help"
          value={command}
        />
      </label>
      <div className="agent-console__output" aria-label="Agent output">
        {history.map((line) => (
          <div className="agent-console__line" key={line.id}>{line.text}</div>
        ))}
      </div>
    </div>
  );
}
