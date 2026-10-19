/// <reference types="node" />
import {execFileSync} from 'child_process';
import {readFileSync} from 'fs';
import {join} from 'path';

const ROOT = join(__dirname, '..');
const PATTERNS: [string, RegExp][] = [
  ['passcode value', /passcode\s*[:=]\s*['"][^'"]+['"]/i],
  ['bearer token', /Bearer\s+[A-Za-z0-9._-]{8,}/],
  ['AWS access key', /AKIA[0-9A-Z]{16}/],
];

// Source has no secrets
test('no file in the Fire TV app holds a passcode, token or AWS key', () => {
  const files = execFileSync('git', ['ls-files', '--cached', '--others', '--exclude-standard'], {cwd: ROOT, encoding: 'utf8'})
    .split('\n')
    .filter((f: string) => f && !f.endsWith('secrets.test.ts') && !f.endsWith('package-lock.json'));
  expect(files.length).toBeGreaterThan(0);
  const found = files.flatMap(f => {
    const text = readFileSync(join(ROOT, f), 'utf8');
    return PATTERNS.filter(([, re]) => re.test(text)).map(([name]) => `${f}: ${name}`);
  });
  expect(found).toEqual([]);
});
