# Spec Delta

## ADDED Requirements

### Requirement: Launcher icon
The Fire TV app's manifest SHALL declare a package icon, and the icon file SHALL be a byte-for-byte copy of the PWA's `pwa/public/icon-512.png`, so the TV launcher shows the same icon as the phone app. The manifest check run by `npm run build:release` SHALL report no "Icon is not defined" message.

#### Scenario: Manifest declares the icon
- **WHEN** `firetv/manifest.toml` is read
- **THEN** its `[package]` section has an `icon` entry pointing at a file in the `firetv/` package that exists

#### Scenario: Same icon as the PWA
- **WHEN** the icon file named by the manifest is compared with `pwa/public/icon-512.png`
- **THEN** the two files are identical

#### Scenario: Build has no icon warning
- **WHEN** `npm run build:release` runs in `firetv/`
- **THEN** its output does not contain "Icon is not defined in the manifest"
