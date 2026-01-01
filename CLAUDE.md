# Claude Commands for Digital Mirror

This document contains commands for Claude Code to build and release Digital Mirror.

## Build Commands

### Build macOS App
```
Build the macOS .app bundle:
1. Activate virtual environment: source .venv/bin/activate
2. Install dependencies: pip install -r requirements.txt && pip install pyinstaller pillow
3. Generate icon if needed: python create_icon.py && iconutil -c icns assets/icon.iconset -o assets/icon.icns
4. Build with PyInstaller: pyinstaller DigitalMirror.spec
5. Sign the app: codesign --force --deep --sign - "dist/Digital Mirror.app"
```

### Build DMG Installer
```
Create DMG installer from the built app:
hdiutil create -volname "Digital Mirror" -srcfolder "dist/Digital Mirror.app" -ov -format UDZO "dist/DigitalMirror-VERSION.dmg"
```

### Full Release Build
```
Run the automated build script:
chmod +x build_macos.sh && ./build_macos.sh
```

## Release Commands

### Create Release Commit
```
1. Update version number in RELEASE_NOTES.md
2. Stage changes: git add .
3. Commit with release message:
   git commit -m "Release vX.Y.Z - [brief description]"
4. Tag the release: git tag vX.Y.Z
```

### Version Bump Checklist
- [ ] Update RELEASE_NOTES.md with new version section
- [ ] Update version in DMG filename (build script or manual)
- [ ] Commit all changes
- [ ] Create git tag
- [ ] Build DMG

## Development Commands

### Run from Source
```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python digital_mirror.py
```

### Clean Build Artifacts
```
rm -rf build/ dist/ *.spec __pycache__/
```

### Regenerate Icon
```
python create_icon.py
iconutil -c icns assets/icon.iconset -o assets/icon.icns
```

## File Structure

| File | Purpose |
|------|---------|
| `digital_mirror.py` | Main application code |
| `requirements.txt` | Python dependencies |
| `build_macos.sh` | Automated build script |
| `create_icon.py` | Icon generator |
| `DigitalMirror.spec` | PyInstaller configuration |
| `entitlements.plist` | macOS entitlements (camera) |
| `RELEASE_NOTES.md` | Version history |
| `README.md` | User documentation |

## Notes

- Always test the app before creating a release
- DMG is ad-hoc signed (works for personal/internal use)
- For App Store distribution, requires Apple Developer account
