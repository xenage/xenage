import type { NextRequest } from "next/server";

export const runtime = "nodejs";

const MANIFEST_URLS = [
  "https://github.com/xenage/xenage/releases/download/xenage-standalone-dev/latest.json",
  "https://github.com/xenage/xenage/releases/download/xenage-standalone-main/latest.json",
] as const;

const SUPPORTED_TARGETS = new Set([
  "linux-x86_64",
  "linux-aarch64",
  "darwin-x86_64",
  "darwin-aarch64",
  "windows-x86_64",
  "windows-aarch64",
]);

type ManifestPlatform = {
  url?: string;
};

type StandaloneManifest = {
  platforms?: Record<string, ManifestPlatform>;
};

function fallbackTargets(target: string): string[] {
  if (target === "darwin-aarch64") {
    return [target, "darwin-x86_64"];
  }
  if (target === "windows-aarch64") {
    return [target, "windows-x86_64"];
  }
  return [target];
}

function sanitizeUrl(url: string): string {
  return url.replace(/ /g, "%20");
}

async function fetchManifest(): Promise<StandaloneManifest> {
  for (const manifestUrl of MANIFEST_URLS) {
    const response = await fetch(manifestUrl, {
      cache: "no-store",
      headers: {
        "user-agent": "xenage-landing-installer",
      },
    });
    if (!response.ok) {
      continue;
    }
    const payload = (await response.json()) as StandaloneManifest;
    return payload;
  }
  throw new Error("Standalone release manifest was not found");
}

function resolveAssetUrl(manifest: StandaloneManifest, target: string): string {
  const platforms = manifest.platforms;
  if (!platforms) {
    throw new Error("Standalone manifest has no platforms field");
  }

  for (const candidate of fallbackTargets(target)) {
    const entry = platforms[candidate];
    if (!entry || typeof entry.url !== "string" || entry.url.length === 0) {
      continue;
    }
    return sanitizeUrl(entry.url);
  }

  throw new Error(`No standalone asset found for target ${target}`);
}

function responseFilename(target: string): string {
  if (target.startsWith("windows-")) {
    return "xenage.exe";
  }
  return "xenage";
}

export async function GET(request: NextRequest): Promise<Response> {
  const target = request.nextUrl.searchParams.get("target") ?? "";
  if (!SUPPORTED_TARGETS.has(target)) {
    return new Response("Unsupported target", { status: 400 });
  }

  try {
    const manifest = await fetchManifest();
    const assetUrl = resolveAssetUrl(manifest, target);

    const assetResponse = await fetch(assetUrl, {
      cache: "no-store",
      headers: {
        "user-agent": "xenage-landing-installer",
      },
    });

    if (!assetResponse.ok || !assetResponse.body) {
      return new Response("Failed to download standalone asset", { status: 502 });
    }

    const headers = new Headers();
    headers.set("content-type", "application/octet-stream");
    headers.set("content-disposition", `attachment; filename=\"${responseFilename(target)}\"`);
    headers.set("cache-control", "no-store");

    const contentLength = assetResponse.headers.get("content-length");
    if (contentLength) {
      headers.set("content-length", contentLength);
    }

    return new Response(assetResponse.body, {
      status: 200,
      headers,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unexpected backend error";
    return new Response(message, { status: 502 });
  }
}
