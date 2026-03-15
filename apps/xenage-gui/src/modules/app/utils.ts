import type { GuiClusterSnapshot } from "../../types/guiConnection";

const relativeTimeFormatter = new Intl.RelativeTimeFormat(undefined, { numeric: "always" });
const SECOND_MS = 1_000;
const MINUTE_MS = 60 * SECOND_MS;
const HOUR_MS = 60 * MINUTE_MS;
const DAY_MS = 24 * HOUR_MS;

export function formatClockTime(timestamp: number): string {
  return new Intl.DateTimeFormat(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(timestamp);
}

export function formatTimeAgo(rawTimestamp: string, now: number = Date.now()): string {
  const timestamp = rawTimestamp.trim();
  if (!timestamp) {
    return "-";
  }

  const parsed = Date.parse(timestamp);
  if (Number.isNaN(parsed)) {
    return "-";
  }

  const diff = parsed - now;
  const absDiff = Math.abs(diff);

  if (absDiff < 5 * SECOND_MS) {
    return "just now";
  }
  if (absDiff < MINUTE_MS) {
    return relativeTimeFormatter.format(Math.round(diff / SECOND_MS), "second");
  }
  if (absDiff < HOUR_MS) {
    return relativeTimeFormatter.format(Math.round(diff / MINUTE_MS), "minute");
  }
  if (absDiff < DAY_MS) {
    return relativeTimeFormatter.format(Math.round(diff / HOUR_MS), "hour");
  }
  return relativeTimeFormatter.format(Math.round(diff / DAY_MS), "day");
}

export function uniqueControlPlaneUrls(urls: string[]): string[] {
  const seen = new Set<string>();
  const merged: string[] = [];
  for (const rawUrl of urls) {
    const normalized = rawUrl.trim().replace(/\/+$/, "");
    if (!normalized || seen.has(normalized)) {
      continue;
    }
    seen.add(normalized);
    merged.push(normalized);
  }
  return merged;
}

export function controlPlaneUrlsFromSnapshot(snapshot: GuiClusterSnapshot): string[] {
  return uniqueControlPlaneUrls(
    snapshot.nodes
      .filter((node) => node.role === "control-plane")
      .flatMap((node) => node.endpoints ?? []),
  );
}

export function extractClusterUserId(configYaml: string): string | null {
  const lines = configYaml.split(/\r?\n/);
  let inSpec = false;
  let specIndent = -1;
  let inUser = false;
  let userIndent = -1;

  for (const rawLine of lines) {
    const line = rawLine.replace(/\t/g, "  ");
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) {
      continue;
    }

    const indent = line.length - line.trimStart().length;

    if (inUser && indent <= userIndent) {
      inUser = false;
    }
    if (inSpec && indent <= specIndent) {
      inSpec = false;
      inUser = false;
    }

    if (!inSpec && trimmed === "spec:") {
      inSpec = true;
      specIndent = indent;
      continue;
    }
    if (inSpec && !inUser && trimmed === "user:") {
      inUser = true;
      userIndent = indent;
      continue;
    }
    if (!inUser) {
      continue;
    }

    const idMatch = trimmed.match(/^id\s*:\s*(.+)\s*$/);
    if (!idMatch) {
      continue;
    }

    const value = idMatch[1].trim().replace(/^['"]/, "").replace(/['"]$/, "");
    return value.length > 0 ? value : null;
  }

  return null;
}

export function parseArgsList(raw: string): string[] {
  return raw
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
}
