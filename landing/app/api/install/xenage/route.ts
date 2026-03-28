import type { NextRequest } from "next/server";

export const runtime = "nodejs";

type Channel = "latest" | "development";

const INSTALLER_USER_AGENT = "xenage-landing-installer";

const TARGETS = new Set([
  "linux-x86_64",
  "linux-aarch64",
  "darwin-x86_64",
  "darwin-aarch64",
  "windows-x86_64",
  "windows-aarch64",
]);

const LATEST_MANIFESTS = [
  "https://github.com/xenage/xenage/releases/download/nightly/latest.json",
  "https://github.com/xenage/xenage/releases/latest/download/latest.json",
] as const;

const DEVELOPMENT_MANIFESTS = [
  "https://github.com/xenage/xenage/releases/download/xenage-standalone-dev/latest.json",
  "https://github.com/xenage/xenage/releases/download/nightly/latest.json",
] as const;

type ManifestPlatform = {
  url?: string;
};

type StandaloneManifest = {
  version?: string;
  platforms?: Record<string, ManifestPlatform>;
};

type ReleaseAsset = {
  name: string;
  browser_download_url: string;
};

type GitHubRelease = {
  assets?: ReleaseAsset[];
};

class HttpError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

function parseChannel(raw: string | null): Channel {
  if (raw === "latest") {
    return "latest";
  }
  if (raw === "development") {
    return "development";
  }
  return "latest";
}

function supportedManifestUrls(channel: Channel): readonly string[] {
  if (channel === "latest") {
    return LATEST_MANIFESTS;
  }
  return DEVELOPMENT_MANIFESTS;
}

function fallbackTargets(target: string): string[] {
  if (target === "darwin-aarch64") {
    return [target, "darwin-x86_64"];
  }
  if (target === "windows-aarch64") {
    return [target, "windows-x86_64"];
  }
  return [target];
}

function sanitizeAssetUrl(url: string): string {
  return url.replace(/ /g, "%20");
}

async function fetchManifest(channel: Channel): Promise<{ manifest: StandaloneManifest; manifestUrl: string }> {
  const urls = supportedManifestUrls(channel);
  for (const manifestUrl of urls) {
    const response = await fetch(manifestUrl, {
      cache: "no-store",
      headers: { "user-agent": INSTALLER_USER_AGENT },
    });
    if (!response.ok) {
      continue;
    }
    return {
      manifest: (await response.json()) as StandaloneManifest,
      manifestUrl,
    };
  }
  throw new HttpError(404, `Standalone ${channel} manifest was not found`);
}

function resolveAssetUrlFromManifest(manifest: StandaloneManifest, target: string): string | null {
  const platforms = manifest.platforms;
  if (!platforms) {
    return null;
  }
  for (const candidate of fallbackTargets(target)) {
    const entry = platforms[candidate];
    if (!entry || typeof entry.url !== "string" || entry.url.length === 0) {
      continue;
    }
    return sanitizeAssetUrl(entry.url);
  }
  return null;
}

function releaseTagFromDownloadUrl(url: string): string | null {
  try {
    const parsed = new URL(url);
    const parts = parsed.pathname.split("/").filter(Boolean);
    const downloadIndex = parts.indexOf("download");
    if (downloadIndex >= 0 && parts.length > downloadIndex + 1) {
      return parts[downloadIndex + 1] ?? null;
    }
  } catch {
    return null;
  }
  return null;
}

function inferCliTargetFromAssetName(name: string): string | null {
  const lower = name.toLowerCase();
  if (lower.includes("xenage gui") || lower.endsWith(".sig")) {
    return null;
  }
  if (lower.startsWith("win_x86_xenage_") && lower.endsWith(".exe")) {
    return "windows-x86_64";
  }
  if (lower.startsWith("win_aarch_xenage_") && lower.endsWith(".exe")) {
    return "windows-aarch64";
  }
  if (lower.startsWith("mac_x86_xenage_")) {
    return "darwin-x86_64";
  }
  if (lower.startsWith("mac_aarch_xenage_")) {
    return "darwin-aarch64";
  }
  if (lower.startsWith("linux_x86_xenage_")) {
    return "linux-x86_64";
  }
  if (lower.startsWith("linux_aarch_xenage_")) {
    return "linux-aarch64";
  }
  return null;
}

async function resolveCliAssetUrlFromRelease(
  manifest: StandaloneManifest,
  manifestUrl: string,
  target: string,
): Promise<string | null> {
  const primaryTag = releaseTagFromDownloadUrl(manifestUrl);
  const anyPlatformUrl = Object.values(manifest.platforms ?? {})
    .map((entry) => entry.url)
    .find((url): url is string => typeof url === "string" && url.length > 0);
  const fallbackTag = anyPlatformUrl ? releaseTagFromDownloadUrl(anyPlatformUrl) : null;
  const releaseTag = primaryTag ?? fallbackTag;

  if (!releaseTag) {
    return null;
  }

  const response = await fetch(
    `https://api.github.com/repos/xenage/xenage/releases/tags/${encodeURIComponent(releaseTag)}`,
    {
      cache: "no-store",
      headers: { "user-agent": INSTALLER_USER_AGENT },
    },
  );
  if (!response.ok) {
    return null;
  }

  const release = (await response.json()) as GitHubRelease;
  const assets = release.assets ?? [];
  for (const asset of assets) {
    if (inferCliTargetFromAssetName(asset.name) === target) {
      return sanitizeAssetUrl(asset.browser_download_url);
    }
  }
  return null;
}

async function resolveDownloadUrl(channel: Channel, target: string): Promise<{ url: string; version: string }> {
  const { manifest, manifestUrl } = await fetchManifest(channel);
  const version = typeof manifest.version === "string" ? manifest.version : "unknown";

  const manifestUrlMatch = resolveAssetUrlFromManifest(manifest, target);
  if (manifestUrlMatch) {
    return { url: manifestUrlMatch, version };
  }

  const releaseUrlMatch = await resolveCliAssetUrlFromRelease(manifest, manifestUrl, target);
  if (releaseUrlMatch) {
    return { url: releaseUrlMatch, version };
  }

  throw new HttpError(404, `No asset found for target ${target}`);
}

export async function GET(request: NextRequest): Promise<Response> {
  const target = request.nextUrl.searchParams.get("target") ?? "";
  const channel = parseChannel(request.nextUrl.searchParams.get("channel"));

  if (!TARGETS.has(target)) {
    return new Response("Unsupported target", { status: 400 });
  }

  try {
    const resolved = await resolveDownloadUrl(channel, target);
    return new Response(null, {
      status: 302,
      headers: {
        location: resolved.url,
        "cache-control": "no-store",
        "x-xenage-channel": channel,
        "x-xenage-version": resolved.version,
      },
    });
  } catch (error) {
    if (error instanceof HttpError) {
      return new Response(error.message, { status: error.status });
    }
    const message = error instanceof Error ? error.message : "Unexpected backend error";
    return new Response(message, { status: 502 });
  }
}
