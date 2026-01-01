# Release Instructions

This guide covers how to create a new release of Digital Mirror.

## Prerequisites

- macOS with Xcode Command Line Tools installed
- Python 3.9+
- Hatch installed (`pip install hatch` or `brew install hatch`)

## Release Checklist

### 1. Update Version Numbers

Update the version in these files:

```bash
# 1. Main application (digital_mirror.py)
VERSION = "X.Y.Z"

# 2. Project config (pyproject.toml)
version = "X.Y.Z"

# 3. Build script (build_macos.sh)
APP_VERSION="X.Y.Z"
```

**Version format:** `MAJOR.MINOR.PATCH` (e.g., `1.2.0`)
- MAJOR: Breaking changes or major new features
- MINOR: New features, backwards compatible
- PATCH: Bug fixes only

### 2. Update Release Notes

Edit `RELEASE_NOTES.md` and add a new section at the top:

```markdown
## vX.Y.Z (YYYY-MM-DD)

### New Features
- **Feature name** - Brief description

### Improvements
- Description of improvements

### Bug Fixes
- Description of fixes

### Technical
- Internal changes of note

---
```

### 3. Test the Application

```bash
# Run from source using Hatch (creates fresh environment automatically)
hatch run run

# Or run linting checks
hatch run lint:check
```

Verify:
- [ ] App launches without errors
- [ ] Camera preview works
- [ ] All features function correctly
- [ ] About dialog shows correct version

### 4. Commit Version Changes

```bash
git add -A
git commit -m "Bump version to X.Y.Z"
```

### 5. Create Git Tag

```bash
# Create annotated tag
git tag -a vX.Y.Z -m "Release vX.Y.Z"

# Example with release notes summary
git tag -a v1.2.0 -m "Release v1.2.0

- New feature A
- New feature B
- Bug fix C"
```

### 6. Build Distribution Packages

#### Option A: Using Hatch (Recommended)

```bash
# Build the app bundle (creates fresh environment)
hatch run build

# Create DMG installer
hatch run dmg

# Or do both in one command
hatch run release
```

This creates:
- `dist/Digital Mirror.app` - Application bundle
- `dist/DigitalMirror-X.Y.Z.dmg` - DMG installer with Applications shortcut

#### Option B: Using Build Script

```bash
chmod +x build_macos.sh
./build_macos.sh
```

#### Option C: Manual Build

```bash
# Activate virtual environment
source .venv/bin/activate

# Build with PyInstaller
pyinstaller DigitalMirror.spec --noconfirm

# Sign the app (ad-hoc)
codesign --force --deep --sign - "dist/Digital Mirror.app"

# Create DMG with Applications shortcut
mkdir -p dist/dmg
cp -R "dist/Digital Mirror.app" dist/dmg/
ln -s /Applications dist/dmg/Applications
hdiutil create -volname "Digital Mirror" -srcfolder dist/dmg -ov -format UDZO "dist/DigitalMirror-X.Y.Z.dmg"
rm -rf dist/dmg
```

### 7. Verify the Build

```bash
# Check DMG contents
hdiutil attach dist/DigitalMirror-X.Y.Z.dmg
ls -la /Volumes/Digital\ Mirror/
hdiutil detach /Volumes/Digital\ Mirror

# Test the built app
open "dist/Digital Mirror.app"
```

Verify:
- [ ] DMG mounts correctly
- [ ] Contains app and Applications shortcut
- [ ] App launches from DMG
- [ ] About dialog shows correct version

### 8. Push Changes and Tags

```bash
# Push commits
git push origin main

# Push tags
git push origin vX.Y.Z

# Or push all tags
git push origin --tags
```

## Quick Release Commands

For a quick release after updating version numbers and release notes:

```bash
# Set version
VERSION="1.2.0"

# Commit, tag, and build
git add -A
git commit -m "Bump version to $VERSION"
git tag -a "v$VERSION" -m "Release v$VERSION"

# Build
source .venv/bin/activate
pyinstaller DigitalMirror.spec --noconfirm
codesign --force --deep --sign - "dist/Digital Mirror.app"
mkdir -p dist/dmg
cp -R "dist/Digital Mirror.app" dist/dmg/
ln -s /Applications dist/dmg/Applications
hdiutil create -volname "Digital Mirror" -srcfolder dist/dmg -ov -format UDZO "dist/DigitalMirror-$VERSION.dmg"
rm -rf dist/dmg

# Push
git push origin main
git push origin "v$VERSION"
```

## File Locations Summary

| File | Version Location |
|------|------------------|
| `digital_mirror.py` | `VERSION = "X.Y.Z"` (line 8) |
| `pyproject.toml` | `version = "X.Y.Z"` (line 6) |
| `build_macos.sh` | `APP_VERSION="X.Y.Z"` (line 18) |
| `RELEASE_NOTES.md` | Add new section at top |

## Hatch Commands Reference

| Command | Description |
|---------|-------------|
| `hatch run run` | Run the app from source |
| `hatch run build` | Build .app bundle |
| `hatch run dmg` | Create DMG installer |
| `hatch run release` | Build + create DMG |
| `hatch run icon` | Generate app icon |
| `hatch run clean` | Remove build artifacts |
| `hatch run lint:check` | Run linting checks |
| `hatch run lint:fix` | Auto-fix lint issues |
| `hatch run test:run` | Run tests |
| `hatch env prune` | Remove all Hatch environments |

## Distribution Notes

### Ad-hoc Signing (Current)
The build script creates an ad-hoc signed app suitable for:
- Personal use
- Internal distribution
- Testing

### For Public Distribution
You'll need an Apple Developer account ($99/year):

```bash
# Sign with Developer ID
codesign --force --deep --sign "Developer ID Application: Your Name" "dist/Digital Mirror.app"

# Notarize
xcrun notarytool submit dist/DigitalMirror-X.Y.Z.dmg \
  --apple-id YOUR_APPLE_ID \
  --password APP_SPECIFIC_PASSWORD \
  --team-id YOUR_TEAM_ID \
  --wait

# Staple the notarization ticket
xcrun stapler staple dist/DigitalMirror-X.Y.Z.dmg
```
