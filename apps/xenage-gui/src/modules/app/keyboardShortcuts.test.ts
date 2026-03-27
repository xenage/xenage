import { describe, expect, it } from "vitest";
import { isMacLikePlatform, resolveGlobalShortcut } from "./keyboardShortcuts";

type ShortcutEventInput = {
  altKey?: boolean;
  code: string;
  ctrlKey?: boolean;
  metaKey?: boolean;
  shiftKey?: boolean;
};

function createEvent({
  altKey = false,
  code,
  ctrlKey = false,
  metaKey = false,
  shiftKey = false,
}: ShortcutEventInput): Pick<KeyboardEvent, "altKey" | "code" | "ctrlKey" | "metaKey" | "shiftKey"> {
  return {
    altKey,
    code,
    ctrlKey,
    metaKey,
    shiftKey,
  };
}

describe("keyboardShortcuts", () => {
  it("detects mac-like platforms", () => {
    expect(isMacLikePlatform("MacIntel")).toBe(true);
    expect(isMacLikePlatform("iPhone")).toBe(true);
    expect(isMacLikePlatform("Win32")).toBe(false);
  });

  it("resolves refresh and close shortcuts by physical key code", () => {
    expect(resolveGlobalShortcut(createEvent({ code: "KeyR", ctrlKey: true }), false)).toEqual({ type: "refresh" });
    expect(resolveGlobalShortcut(createEvent({ code: "KeyW", ctrlKey: true }), false)).toEqual({ type: "closeTab" });
    expect(resolveGlobalShortcut(createEvent({ code: "KeyW", metaKey: true }), true)).toEqual({ type: "closeTab" });
  });

  it("resolves tab switch shortcuts for windows/linux", () => {
    expect(resolveGlobalShortcut(createEvent({ code: "Tab", ctrlKey: true }), false)).toEqual({
      type: "switchTab",
      direction: 1,
    });
    expect(resolveGlobalShortcut(createEvent({ code: "Tab", ctrlKey: true, shiftKey: true }), false)).toEqual({
      type: "switchTab",
      direction: -1,
    });
    expect(resolveGlobalShortcut(createEvent({ code: "PageDown", ctrlKey: true }), false)).toEqual({
      type: "switchTab",
      direction: 1,
    });
  });

  it("resolves tab switch shortcuts for macOS", () => {
    expect(resolveGlobalShortcut(createEvent({ code: "BracketRight", metaKey: true, shiftKey: true }), true)).toEqual({
      type: "switchTab",
      direction: 1,
    });
    expect(resolveGlobalShortcut(createEvent({ code: "ArrowLeft", metaKey: true, altKey: true }), true)).toEqual({
      type: "switchTab",
      direction: -1,
    });
  });

  it("resolves direct tab selection shortcuts", () => {
    expect(resolveGlobalShortcut(createEvent({ code: "Digit1", ctrlKey: true }), false)).toEqual({
      type: "activateTab",
      index: 0,
    });
    expect(resolveGlobalShortcut(createEvent({ code: "Digit9", metaKey: true }), true)).toEqual({
      type: "activateTab",
      index: 8,
    });
  });
});
