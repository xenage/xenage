import fs from 'node:fs';
import path from 'node:path';
import { execSync } from 'node:child_process';

const repoRoot = process.cwd();
const tauriConfigPath = path.join(repoRoot, 'apps/xenage-gui/src-tauri/tauri.conf.json');
const cargoTomlPath = path.join(repoRoot, 'apps/xenage-gui/src-tauri/Cargo.toml');
const packageJsonPath = path.join(repoRoot, 'apps/xenage-gui/package.json');
const githubOutput = process.env.GITHUB_OUTPUT;

const branch = process.env.GITHUB_REF_NAME ?? '';
const runNumber = process.env.GITHUB_RUN_NUMBER ?? '0';

function readBaseVersion() {
  if (branch !== 'dev') {
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

const tauriConfig = JSON.parse(fs.readFileSync(tauriConfigPath, 'utf8'));
const baseVersion = readBaseVersion();

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

function makeBuildVersion(version, refName, ciRunNumber) {
  if (refName === 'dev') {
    const parsed = parseSemver(version);
    // MSI only accepts numeric pre-release identifiers, so dev builds use
    // the next patch with the CI run number as a numeric pre-release.
    return `${parsed.major}.${parsed.minor}.${parsed.patch + 1}-${ciRunNumber}`;
  }

  return version;
}

function replaceCargoVersion(content, version) {
  return content.replace(/^version = ".*"$/m, `version = "${version}"`);
}

const releaseVersion = makeBuildVersion(baseVersion, branch, runNumber);

tauriConfig.version = releaseVersion;
fs.writeFileSync(tauriConfigPath, `${JSON.stringify(tauriConfig, null, 2)}\n`);

const packageJson = JSON.parse(fs.readFileSync(packageJsonPath, 'utf8'));
packageJson.version = releaseVersion;
fs.writeFileSync(packageJsonPath, `${JSON.stringify(packageJson, null, 2)}\n`);

const cargoToml = fs.readFileSync(cargoTomlPath, 'utf8');
fs.writeFileSync(cargoTomlPath, replaceCargoVersion(cargoToml, releaseVersion));

const releaseTag = branch === 'dev' ? 'xenage-gui-dev' : `xenage-gui-v${releaseVersion}`;
const releaseName = branch === 'dev' ? 'Xenage GUI Development' : `Xenage GUI v${releaseVersion}`;

if (githubOutput) {
  fs.appendFileSync(githubOutput, `release_version=${releaseVersion}\n`);
  fs.appendFileSync(githubOutput, `release_tag=${releaseTag}\n`);
  fs.appendFileSync(githubOutput, `release_name=${releaseName}\n`);
}

console.log(`Prepared Xenage GUI version ${releaseVersion} for branch ${branch || 'unknown'}.`);
