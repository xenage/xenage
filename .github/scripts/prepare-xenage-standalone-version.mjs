import fs from 'node:fs';

const githubOutput = process.env.GITHUB_OUTPUT;
const branch = process.env.GITHUB_REF_NAME ?? '';
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

const baseVersion = readProjectVersion();
const isDev = branch === 'dev';
let releaseVersion = baseVersion;
let releaseTag = `xenage-standalone-v${baseVersion}`;
let releaseName = `Xenage Standalone v${baseVersion}`;

if (isDev) {
  const parsed = parseSemver(baseVersion);
  releaseVersion = `${parsed.major}.${parsed.minor}.${parsed.patch + 1}-${runNumber}`;
  releaseTag = 'xenage-standalone-dev';
  releaseName = 'Xenage Standalone Development';
}

if (githubOutput) {
  fs.appendFileSync(githubOutput, `release_version=${releaseVersion}\n`);
  fs.appendFileSync(githubOutput, `release_tag=${releaseTag}\n`);
  fs.appendFileSync(githubOutput, `release_name=${releaseName}\n`);
  fs.appendFileSync(githubOutput, `is_dev=${isDev ? 'true' : 'false'}\n`);
}

console.log(`Prepared standalone version ${releaseVersion} for branch ${branch || 'unknown'}.`);
