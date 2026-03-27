import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, '../../..');
const scriptPath = path.join(repoRoot, 'scripts', 'export_structures.py');

const venvUnix = path.join(repoRoot, '.venv', 'bin', 'python');
const venvWindows = path.join(repoRoot, '.venv', 'Scripts', 'python.exe');

const attempts = [];
if (fs.existsSync(venvUnix)) {
  attempts.push({ cmd: venvUnix, args: [scriptPath] });
}
if (fs.existsSync(venvWindows)) {
  attempts.push({ cmd: venvWindows, args: [scriptPath] });
}
attempts.push({ cmd: 'python', args: [scriptPath] });
attempts.push({ cmd: 'py', args: ['-3', scriptPath] });

let lastError = null;
for (const attempt of attempts) {
  const result = spawnSync(attempt.cmd, attempt.args, {
    cwd: repoRoot,
    stdio: 'inherit',
  });

  if (!result.error && result.status === 0) {
    process.exit(0);
  }

  if (result.error && result.error.code === 'ENOENT') {
    continue;
  }

  lastError = result.error
    ? `${attempt.cmd} ${attempt.args.join(' ')}: ${result.error.message}`
    : `${attempt.cmd} ${attempt.args.join(' ')} exited with code ${result.status}`;
}

console.error(lastError || 'Failed to execute scripts/export_structures.py');
process.exit(1);
