import { access, mkdir, readFile, rename, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import type { NextRequest } from "next/server";

export const runtime = "nodejs";

type Channel = "latest" | "development";

const INSTALLER_USER_AGENT = "xenage-landing-installer";
const CACHE_ROOT = process.env.XENAGE_INSTALL_CACHE_DIR ?? join(tmpdir(), "xenage-install-cache");

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

type CacheEntry = {
  version: string;
  assetUrl: string;
  filePath: string;
  contentType: string;
  contentLength: string;
  channel: Channel;
  target: string;
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
  return "development";
}

function supportedManifestUrls(channel: Channel): readonly string[] {
  if (channel === "latest") {
    return LATEST_MANIFESTS;
  }
  return DEVELOPMENT_MANIFESTS;
}

function cacheMetaPath(channel: Channel, target: string): string {
  return join(CACHE_ROOT, `${channel}-${target}.json`);
}

function defaultBinaryName(target: string): string {
  if (target.startsWith("windows-")) {
    return "xenage.exe";
  }
  return "xenage";
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

async function fileExists(path: string): Promise<boolean> {
  try {
    await access(path);
    return true;
  } catch {
    return false;
  }
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

function resolveAssetUrl(manifest: StandaloneManifest, target: string): string {
  const platforms = manifest.platforms;
  if (!platforms) {
    throw new Error("Standalone manifest has no platforms");
  }

  for (const candidate of fallbackTargets(target)) {
    const entry = platforms[candidate];
    if (!entry || typeof entry.url !== "string" || entry.url.length === 0) {
      continue;
    }
    return sanitizeAssetUrl(entry.url);
  }

  throw new HttpError(404, `No standalone asset found in latest.json for target ${target}`);
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
): Promise<string> {
  const primaryTag = releaseTagFromDownloadUrl(manifestUrl);
  const anyPlatformUrl = Object.values(manifest.platforms ?? {})
    .map((entry) => entry.url)
    .find((url): url is string => typeof url === "string" && url.length > 0);
  const fallbackTag = anyPlatformUrl ? releaseTagFromDownloadUrl(anyPlatformUrl) : null;
  const releaseTag = primaryTag ?? fallbackTag;

  if (!releaseTag) {
    throw new HttpError(404, `Could not determine release tag for fallback target ${target}`);
  }

  const response = await fetch(`https://api.github.com/repos/xenage/xenage/releases/tags/${encodeURIComponent(releaseTag)}`, {
    cache: "no-store",
    headers: { "user-agent": INSTALLER_USER_AGENT },
  });
  if (!response.ok) {
    throw new HttpError(502, `Failed to fetch release metadata for tag ${releaseTag}`);
  }

  const release = (await response.json()) as GitHubRelease;
  const assets = release.assets ?? [];
  for (const asset of assets) {
    if (inferCliTargetFromAssetName(asset.name) === target) {
      return sanitizeAssetUrl(asset.browser_download_url);
    }
  }

  throw new HttpError(404, `No CLI asset found for target ${target} in release ${releaseTag}`);
}

async function readCache(path: string): Promise<CacheEntry | null> {
  try {
    const raw = await readFile(path, "utf-8");
    return JSON.parse(raw) as CacheEntry;
  } catch {
    return null;
  }
}

async function writeCache(path: string, entry: CacheEntry): Promise<void> {
  await writeFile(path, JSON.stringify(entry), "utf-8");
}

async function downloadToCache(channel: Channel, target: string, version: string, assetUrl: string): Promise<CacheEntry> {
  await mkdir(CACHE_ROOT, { recursive: true });

  const response = await fetch(assetUrl, {
    cache: "no-store",
    headers: { "user-agent": INSTALLER_USER_AGENT },
  });

  if (!response.ok || !response.body) {
    throw new Error(`Failed to download standalone binary from ${assetUrl}`);
  }

  const fileName = `${channel}-${target}-${Date.now()}-${Math.random().toString(36).slice(2)}.bin`;
  const tempPath = join(CACHE_ROOT, `${fileName}.tmp`);
  const finalPath = join(CACHE_ROOT, fileName);

  const binary = Buffer.from(await response.arrayBuffer());
  await writeFile(tempPath, binary);
  await rename(tempPath, finalPath);

  return {
    version,
    assetUrl,
    filePath: finalPath,
    contentType: response.headers.get("content-type") ?? "application/octet-stream",
    contentLength: response.headers.get("content-length") ?? "",
    channel,
    target,
  };
}

function responseHeaders(target: string, entry: CacheEntry): Headers {
  const headers = new Headers();
  headers.set("content-type", entry.contentType || "application/octet-stream");
  headers.set("content-disposition", `attachment; filename=\"${defaultBinaryName(target)}\"`);
  headers.set("cache-control", "no-store");
  if (entry.contentLength.length > 0) {
    headers.set("content-length", entry.contentLength);
  }
  headers.set("x-xenage-channel", entry.channel);
  headers.set("x-xenage-version", entry.version);
  return headers;
}

async function resolveCacheEntry(channel: Channel, target: string): Promise<CacheEntry> {
  const { manifest, manifestUrl } = await fetchManifest(channel);
  const version = typeof manifest.version === "string" ? manifest.version : "unknown";
  let assetUrl: string;
  try {
    assetUrl = resolveAssetUrl(manifest, target);
  } catch (error) {
    if (error instanceof HttpError && error.status === 404) {
      assetUrl = await resolveCliAssetUrlFromRelease(manifest, manifestUrl, target);
    } else {
      throw error;
    }
  }
  const metaPath = cacheMetaPath(channel, target);

  if (channel === "latest") {
    const cached = await readCache(metaPath);
    if (
      cached &&
      cached.version === version &&
      cached.assetUrl === assetUrl &&
      (await fileExists(cached.filePath))
    ) {
      return cached;
    }
  }

  const fresh = await downloadToCache(channel, target, version, assetUrl);
  await writeCache(metaPath, fresh);
  return fresh;
}

export async function GET(request: NextRequest): Promise<Response> {
  const target = request.nextUrl.searchParams.get("target") ?? "";
  const channel = parseChannel(request.nextUrl.searchParams.get("channel"));

  if (!TARGETS.has(target)) {
    return new Response("Unsupported target", { status: 400 });
  }

  try {
    const entry = await resolveCacheEntry(channel, target);

    if (!(await fileExists(entry.filePath))) {
      return new Response("Cached file is missing", { status: 500 });
    }

    const payload = await readFile(entry.filePath);
    return new Response(payload, {
      status: 200,
      headers: responseHeaders(target, entry),
    });
  } catch (error) {
    if (error instanceof HttpError) {
      return new Response(error.message, { status: error.status });
    }
    const message = error instanceof Error ? error.message : "Unexpected backend error";
    return new Response(message, { status: 502 });
  }
}
