import fs from 'node:fs';

const githubOutput = process.env.GITHUB_OUTPUT;
const refName = process.env.GITHUB_REF_NAME ?? '';
const refType = process.env.GITHUB_REF_TYPE ?? (process.env.GITHUB_REF?.startsWith('refs/tags/') ? 'tag' : 'branch');
const runNumber = process.env.GITHUB_RUN_NUMBER ?? '0';

function readProjectVersion() {
  const pyproject = fs.readFileSync('pyproject.toml', 'utf8');
  const match = pyproject.match(/^version\s*=\s*"([^"]+)"$/m);
  if (!match) {
    throw new Error('Failed to parse project version from pyproject.toml');
  }
  return match[1];
}

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
  parseSemver(normalized);
  return normalized;
}

function nextPatchCiVersion(version, ciRunNumber) {
  const parsed = parseSemver(version);
  return `${parsed.major}.${parsed.minor}.${parsed.patch + 1}-${ciRunNumber}`;
}

const baseVersion = readProjectVersion();

let releaseMode = 'stable';
let releaseVersion = baseVersion;
let releaseTag = `xenage-standalone-v${baseVersion}`;
let releaseName = `Xenage Standalone v${baseVersion}`;
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
  releaseTag = 'xenage-standalone-dev';
  releaseName = 'Xenage Standalone Development';
  prerelease = true;
} else if (refName === 'main') {
  releaseMode = 'nightly';
  releaseVersion = nextPatchCiVersion(baseVersion, runNumber);
  releaseTag = 'nightly';
  releaseName = 'Xenage Nightly';
  prerelease = true;
}

if (githubOutput) {
  fs.appendFileSync(githubOutput, `release_mode=${releaseMode}\n`);
  fs.appendFileSync(githubOutput, `release_version=${releaseVersion}\n`);
  fs.appendFileSync(githubOutput, `release_tag=${releaseTag}\n`);
  fs.appendFileSync(githubOutput, `release_name=${releaseName}\n`);
  fs.appendFileSync(githubOutput, `release_prerelease=${prerelease ? 'true' : 'false'}\n`);
}

console.log(`Prepared standalone version ${releaseVersion} for ${refType}:${refName || 'unknown'}.`);
