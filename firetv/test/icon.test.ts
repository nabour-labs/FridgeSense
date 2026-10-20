import {existsSync, readFileSync} from 'fs';
import {join} from 'path';

const root = join(__dirname, '..');

/** The `icon` entry of the manifest's [package] section, or undefined. */
function packageIcon(): string | undefined {
  const manifest = readFileSync(join(root, 'manifest.toml'), 'utf8');
  const section = manifest.split(/^\[/m).find(s => s.startsWith('package]'));
  return section?.match(/^icon\s*=\s*"([^"]+)"/m)?.[1];
}

/** The icon's file in the package: "@image/<name>" lives in assets/image/, anything else is a path. */
function iconFile(icon: string): string {
  return icon.startsWith('@image/')
    ? join(root, 'assets', 'image', icon.slice('@image/'.length))
    : join(root, icon);
}

// Manifest declares the icon
test('the manifest declares a package icon that exists', () => {
  const icon = packageIcon();
  expect(icon).toBeDefined();
  expect(existsSync(iconFile(icon!))).toBe(true);
});

// Same icon as the PWA
test('the launcher icon is the PWA icon, byte for byte', () => {
  const pwaIcon = readFileSync(join(root, '..', 'pwa', 'public', 'icon-512.png'));
  expect(readFileSync(iconFile(packageIcon()!)).equals(pwaIcon)).toBe(true);
});
