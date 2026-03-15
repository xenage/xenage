type ShortcutEvent = Pick<KeyboardEvent, "altKey" | "code" | "ctrlKey" | "metaKey" | "shiftKey">;

export type KeyboardShortcutAction =
  | { type: "activateTab"; index: number }
  | { type: "closeTab" }
  | { type: "refresh" }
  | { type: "switchTab"; direction: 1 | -1 };

export function isMacLikePlatform(platform: string): boolean {
  return /(mac|iphone|ipad|ipod)/i.test(platform);
}

export function detectMacLikePlatform(): boolean {
  const navigatorWithUserAgentData = navigator as Navigator & {
    userAgentData?: { platform?: string };
  };
  const platform = navigatorWithUserAgentData.userAgentData?.platform ?? navigator.platform ?? "";
  return isMacLikePlatform(platform);
}

function hasPrimaryModifier(event: ShortcutEvent, macLike: boolean): boolean {
  return macLike
    ? event.metaKey && !event.ctrlKey
    : event.ctrlKey && !event.metaKey;
}

function hasControlModifierOnly(event: ShortcutEvent): boolean {
  return event.ctrlKey && !event.metaKey && !event.altKey;
}

export function resolveGlobalShortcut(event: ShortcutEvent, macLike: boolean): KeyboardShortcutAction | null {
  const primary = hasPrimaryModifier(event, macLike);

  if (primary && !event.altKey && !event.shiftKey && event.code === "KeyR") {
    return { type: "refresh" };
  }

  if (primary && !event.altKey && !event.shiftKey && (event.code === "KeyW" || (!macLike && event.code === "F4"))) {
    return { type: "closeTab" };
  }

  if (primary && !event.altKey && !event.shiftKey && /^Digit[1-9]$/.test(event.code)) {
    const index = Number(event.code.slice(-1)) - 1;
    return { type: "activateTab", index };
  }

  if (hasControlModifierOnly(event) && event.code === "Tab") {
    return { type: "switchTab", direction: event.shiftKey ? -1 : 1 };
  }

  if (!macLike && hasControlModifierOnly(event) && (event.code === "PageDown" || event.code === "PageUp")) {
    return { type: "switchTab", direction: event.code === "PageDown" ? 1 : -1 };
  }

  if (primary && !event.altKey && event.shiftKey && (event.code === "BracketRight" || event.code === "BracketLeft")) {
    return { type: "switchTab", direction: event.code === "BracketRight" ? 1 : -1 };
  }

  if (macLike && primary && event.altKey && !event.shiftKey && (event.code === "ArrowRight" || event.code === "ArrowLeft")) {
    return { type: "switchTab", direction: event.code === "ArrowRight" ? 1 : -1 };
  }

  return null;
}
