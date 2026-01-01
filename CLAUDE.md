# Claude Commands for Digital Mirror

Commands for Claude Code to build and manage Digital Mirror.

## Quick Start (Fresh Clone)

```bash
# Option 1: Using Hatch (recommended)
pip install hatch
hatch run run

# Option 2: Manual setup
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python digital_mirror.py
```

## Hatch Commands

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

## Build Commands

### Build macOS App (Hatch)

```bash
hatch run build
```

### Build DMG Installer

```bash
hatch run dmg
```

### Full Release Build

```bash
hatch run release
```

Or use the shell script:

```bash
chmod +x build_macos.sh && ./build_macos.sh
```

## Version Bump Checklist

Update version in these files:

| File | Location |
|------|----------|
| `digital_mirror.py` | `VERSION = "X.Y.Z"` (line 8) |
| `pyproject.toml` | `version = "X.Y.Z"` (line 6) |
| `build_macos.sh` | `APP_VERSION="X.Y.Z"` (line 18) |
| `RELEASE_NOTES.md` | Add new section at top |

## Release Commands

```bash
# 1. Update versions (see checklist above)
# 2. Update RELEASE_NOTES.md

# 3. Commit and tag
git add -A
git commit -m "Bump version to X.Y.Z"
git tag -a vX.Y.Z -m "Release vX.Y.Z"

# 4. Build
hatch run release

# 5. Push
git push origin main
git push origin vX.Y.Z
```

## File Structure

| File | Purpose |
|------|---------|
| `digital_mirror.py` | Main application code |
| `pyproject.toml` | Project config and Hatch scripts |
| `requirements.txt` | Python dependencies (pip) |
| `build_macos.sh` | Automated build script |
| `create_icon.py` | Icon generator |
| `DigitalMirror.spec` | PyInstaller configuration |
| `entitlements.plist` | macOS entitlements (camera) |
| `scripts/create_dmg.py` | DMG creation script |
| `RELEASE_NOTES.md` | Version history |
| `RELEASING.md` | Detailed release instructions |
| `README.md` | User documentation |

## Notes

- Always test the app before creating a release
- DMG is ad-hoc signed (works for personal/internal use)
- For App Store distribution, requires Apple Developer account
- Hatch creates isolated environments automatically
