import fs from 'node:fs';
import path from 'node:path';
import { execSync } from 'node:child_process';

const repoRoot = process.cwd();
const tauriConfigPath = path.join(repoRoot, 'apps/xenage-gui/src-tauri/tauri.conf.json');
const cargoTomlPath = path.join(repoRoot, 'apps/xenage-gui/src-tauri/Cargo.toml');
const packageJsonPath = path.join(repoRoot, 'apps/xenage-gui/package.json');
const githubOutput = process.env.GITHUB_OUTPUT;

const refName = process.env.GITHUB_REF_NAME ?? '';
const refType = process.env.GITHUB_REF_TYPE ?? (process.env.GITHUB_REF?.startsWith('refs/tags/') ? 'tag' : 'branch');
const runNumber = process.env.GITHUB_RUN_NUMBER ?? '0';

function parseSemver(version) {
  const match = version.match(/^(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$/);
  if (!match) {
    throw new Error(`Unsupported version format: ${version}`);
  }

  return {
    major: Number.parseInt(match[1], 10),
    minor: Number.parseInt(match[2], 10),
    patch: Number.parseInt(match[3], 10),
  };
}

function normalizeTagVersion(tagName) {
  const normalized = tagName.replace(/^[vV]/, '');
  const fourPartMatch = normalized.match(/^(\d+)\.(\d+)\.(\d+)\.(\d+)$/);
  if (fourPartMatch) {
    const revision = Number.parseInt(fourPartMatch[4], 10);
    if (revision !== 0) {
      throw new Error(
        `Unsupported 4-part tag version ${normalized}. Only *.0 is allowed; use a semver tag like v${fourPartMatch[1]}.${fourPartMatch[2]}.${fourPartMatch[3]}.`,
      );
    }
    return `${fourPartMatch[1]}.${fourPartMatch[2]}.${fourPartMatch[3]}`;
  }

  parseSemver(normalized);
  return normalized;
}

function nextPatchCiVersion(version, ciRunNumber) {
  const parsed = parseSemver(version);
  // MSI only accepts numeric pre-release identifiers.
  return `${parsed.major}.${parsed.minor}.${parsed.patch + 1}-${ciRunNumber}`;
}

function readBaseVersion() {
  if (refType === 'tag' || refName !== 'dev') {
    return JSON.parse(fs.readFileSync(tauriConfigPath, 'utf8')).version;
  }

  try {
    const mainTauriConfig = execSync(
      'git show origin/main:apps/xenage-gui/src-tauri/tauri.conf.json',
      { cwd: repoRoot, encoding: 'utf8' },
    );
    return JSON.parse(mainTauriConfig).version;
  } catch (error) {
    console.warn(
      `Falling back to the checked-out Tauri version because origin/main could not be read: ${error}`,
    );
    return JSON.parse(fs.readFileSync(tauriConfigPath, 'utf8')).version;
  }
}

function replaceCargoVersion(content, version) {
  return content.replace(/^version = ".*"$/m, `version = "${version}"`);
}

const baseVersion = readBaseVersion();

let releaseMode = 'stable';
let releaseVersion = baseVersion;
let releaseTag = `xenage-gui-v${releaseVersion}`;
let releaseName = `Xenage GUI v${releaseVersion}`;
let prerelease = false;

if (refType === 'tag') {
  releaseMode = 'tag';
  releaseVersion = normalizeTagVersion(refName);
  releaseTag = refName;
  releaseName = `Xenage ${refName}`;
  prerelease = false;
} else if (refName === 'dev') {
  releaseMode = 'dev';
  releaseVersion = nextPatchCiVersion(baseVersion, runNumber);
  releaseTag = 'xenage-gui-dev';
  releaseName = 'Xenage GUI Development';
  prerelease = true;
} else if (refName === 'main') {
  releaseMode = 'nightly';
  releaseVersion = nextPatchCiVersion(baseVersion, runNumber);
  releaseTag = 'nightly';
  releaseName = 'Xenage Nightly';
  prerelease = true;
}

const tauriConfig = JSON.parse(fs.readFileSync(tauriConfigPath, 'utf8'));
tauriConfig.version = releaseVersion;
fs.writeFileSync(tauriConfigPath, `${JSON.stringify(tauriConfig, null, 2)}\n`);

const packageJson = JSON.parse(fs.readFileSync(packageJsonPath, 'utf8'));
packageJson.version = releaseVersion;
fs.writeFileSync(packageJsonPath, `${JSON.stringify(packageJson, null, 2)}\n`);

const cargoToml = fs.readFileSync(cargoTomlPath, 'utf8');
fs.writeFileSync(cargoTomlPath, replaceCargoVersion(cargoToml, releaseVersion));

if (githubOutput) {
  fs.appendFileSync(githubOutput, `release_mode=${releaseMode}\n`);
  fs.appendFileSync(githubOutput, `release_version=${releaseVersion}\n`);
  fs.appendFileSync(githubOutput, `release_tag=${releaseTag}\n`);
  fs.appendFileSync(githubOutput, `release_name=${releaseName}\n`);
  fs.appendFileSync(githubOutput, `release_prerelease=${prerelease ? 'true' : 'false'}\n`);
}

console.log(`Prepared Xenage GUI version ${releaseVersion} for ${refType}:${refName || 'unknown'}.`);
