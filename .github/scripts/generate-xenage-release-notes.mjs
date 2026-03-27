import { execSync } from 'node:child_process';
import fs from 'node:fs';

const repo = process.env.REPO;
const releaseTag = process.env.RELEASE_TAG;
const releaseName = process.env.RELEASE_NAME;
const releaseMode = process.env.RELEASE_MODE;
const outputPath = process.env.RELEASE_NOTES_PATH;

if (!repo || !releaseTag || !releaseMode || !outputPath) {
  throw new Error('REPO, RELEASE_TAG, RELEASE_MODE and RELEASE_NOTES_PATH are required');
}

function sh(command) {
  return execSync(command, { encoding: 'utf8' }).trim();
}

function safeSh(command, fallback = '') {
  try {
    return sh(command);
  } catch {
    return fallback;
  }
}

function previousStableTag(currentTag) {
  const tagsRaw = safeSh('git tag --sort=-creatordate', '');
  const tags = tagsRaw
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .filter((tag) => tag !== currentTag)
    .filter((tag) => !['nightly', 'xenage-gui-dev', 'xenage-standalone-dev'].includes(tag));

  return tags[0] || null;
}

function collectCommitSubjects(baseRef, headRef) {
  const range = baseRef ? `${baseRef}..${headRef}` : headRef;
  const output = safeSh(`git log --pretty=%s ${range}`, '');
  return output.split('\n').map((line) => line.trim()).filter(Boolean);
}

function toUserFacing(subject) {
  return subject
    .replace(/^\w+(\([^)]+\))?!?:\s*/i, '')
    .replace(/^\[[^\]]+\]\s*/, '')
    .replace(/\s+/g, ' ')
    .trim();
}

function highlightsFromSubjects(subjects) {
  const lines = subjects
    .map(toUserFacing)
    .filter(Boolean)
    .filter((line) => line.length >= 10)
    .slice(0, 5);

  if (lines.length >= 2) {
    return lines.map((line) => `- ${line}`);
  }

  return [
    '- Improved overall product stability and reliability.',
    '- Updated installation and update delivery paths for end users.',
    '- Refined CLI and GUI release experience across supported platforms.',
  ];
}

function detectBreakingChanges(subjects) {
  return subjects.filter((subject) => /breaking change|!:|\bbreaking\b/i.test(subject));
}

function technicalLinks(prevTag) {
  const releasesUrl = `https://github.com/${repo}/releases`;
  const compareUrl = prevTag
    ? `https://github.com/${repo}/compare/${prevTag}...${releaseTag}`
    : `https://github.com/${repo}/commits/${releaseTag}`;
  const prsUrl = prevTag
    ? `https://github.com/${repo}/pulls?q=is%3Apr+is%3Amerged+base%3Amain+sort%3Aupdated-desc`
    : `https://github.com/${repo}/pulls?q=is%3Apr+is%3Amerged+base%3Amain+sort%3Aupdated-desc`;

  return {
    compareUrl,
    releasesUrl,
    prsUrl,
  };
}

let notes;

if (releaseMode === 'tag') {
  const prevTag = previousStableTag(releaseTag);
  const subjects = collectCommitSubjects(prevTag, releaseTag);
  const highlights = highlightsFromSubjects(subjects);
  const breakingChanges = detectBreakingChanges(subjects);
  const links = technicalLinks(prevTag);

  notes = [
    `# ${releaseName}`,
    '',
    '## Highlights',
    ...highlights,
    '',
    '## Breaking changes',
    ...(breakingChanges.length > 0
      ? breakingChanges.slice(0, 10).map((line) => `- ${toUserFacing(line)}`)
      : ['- None identified in this release.']),
    '',
    '## Migration / Upgrade steps',
    '1. Back up your current configuration and runtime data.',
    '2. Install the release artifacts that match your OS and CPU architecture.',
    '3. Restart Xenage components and verify cluster health after upgrade.',
    '',
    '## Full technical change list',
    `- Diff: ${links.compareUrl}`,
    `- Changelog: ${links.releasesUrl}`,
    `- PRs: ${links.prsUrl}`,
    '',
  ].join('\n');
} else {
  notes = [
    `# ${releaseName}`,
    '',
    'Nightly build from `main`. This release is continuously updated and can include unfinished changes.',
    '',
    '## Full technical change list',
    `- Commits: https://github.com/${repo}/commits/main`,
    `- Releases: https://github.com/${repo}/releases`,
    '',
  ].join('\n');
}

fs.writeFileSync(outputPath, notes, 'utf8');
console.log(`Wrote release notes to ${outputPath}`);
