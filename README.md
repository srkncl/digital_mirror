# Digital Mirror 🪞

A camera mirror app for Apple platforms built with Python.

Works on **macOS** and **iOS**.

![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)
![PySide6](https://img.shields.io/badge/PySide6-Qt6-green.svg)
![OpenCV](https://img.shields.io/badge/OpenCV-4.x-red.svg)
![Apple](https://img.shields.io/badge/Apple-macOS%20%7C%20iOS-black.svg)

## Features

- 📹 Real-time camera preview
- 🪞 Mirror mode (horizontal flip) - like a real mirror
- 🔍 Zoom control (1x to 5x) with pinch-to-zoom gesture support
- ☀️ Brightness adjustment
- 🖥️ Fullscreen support
- 📷 Freeze frame (click-hold or double-tap to lock)
- 🖐️ Pan frozen image with trackpad scroll, drag, or arrow keys
- 🎛️ Multiple camera support with device name detection
- 💾 Persistent settings (remembers your preferences)
- 🌙 Dark theme UI
- ⌨️ Keyboard shortcuts

## Quick Start (Run from Source)

### Option 1: Bootstrap Script (Recommended)

```bash
# Clone the repository
git clone https://github.com/yourusername/digital-mirror.git
cd digital-mirror

# Run bootstrap (creates venv, installs everything)
python3 scripts/bootstrap.py

# Activate the environment
source .venv/bin/activate

# Run the app
hatch run run
```

### Option 2: Manual Setup

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install hatch pyinstaller pillow

# Run the app
python digital_mirror.py
# or: hatch run run
```

---

## Build macOS App (.app + .dmg)

```bash
# Build the app bundle
hatch run build

# Create DMG installer
hatch run dmg

# Or do both at once
hatch run release
```

**Output:**
- `dist/Digital Mirror.app` - The application bundle
- `dist/DigitalMirror-1.1.0.dmg` - DMG installer with Applications shortcut

### Installing the App

1. Open the `.dmg` file
2. Drag **Digital Mirror** to **Applications**
3. **First launch:** Right-click the app → **Open** (to bypass Gatekeeper warning)
4. Grant camera permission when prompted

---

## iOS Deployment

For running on iOS, you have several options:

### Option 1: Pyto or Pythonista (Easiest)

1. Install [Pyto](https://apps.apple.com/app/pyto/id1436650069) or [Pythonista](https://apps.apple.com/app/pythonista-3/id1085978097) from the App Store
2. Copy `digital_mirror.py` to the app
3. Install required packages via the app's package manager
4. Run the script

### Option 2: BeeWare/Briefcase (Native App)

For creating a native iOS app:

```bash
# Install Briefcase
pip install briefcase

# Create iOS project
briefcase create iOS

# Build and run on simulator
briefcase run iOS

# Build for device
briefcase build iOS
```

See [BeeWare documentation](https://beeware.org/) for details.

---

## Project Structure

```
DigitalMirror/
├── digital_mirror.py      # Main application code
├── pyproject.toml         # Project config & Hatch scripts
├── requirements.txt       # Python dependencies
├── DigitalMirror.spec     # PyInstaller configuration
├── entitlements.plist     # macOS entitlements (camera access)
├── create_icon.py         # Icon generator script
├── scripts/
│   ├── bootstrap.py       # Environment setup script
│   └── create_dmg.py      # DMG creation script
├── assets/                # Generated assets
│   ├── icon.iconset/      # Icon images
│   └── icon.icns          # macOS icon file
├── RELEASING.md           # Release instructions
├── RELEASE_NOTES.md       # Version history
└── dist/                  # Build output (not in git)
    ├── Digital Mirror.app
    └── DigitalMirror-X.Y.Z.dmg
```

---

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `M` | Toggle mirror mode |
| `F` | Toggle fullscreen |
| `Esc` | Exit fullscreen |
| `Q` | Quit app |

---

## Troubleshooting

### "App is damaged and can't be opened"

This happens because the app isn't signed with an Apple Developer certificate. Fix:

```bash
xattr -cr "/Applications/Digital Mirror.app"
```

Or right-click → Open on first launch.

### Camera permission denied

1. Go to **System Settings** → **Privacy & Security** → **Camera**
2. Enable access for **Digital Mirror**

### "No cameras found"

- Check that your camera is connected
- Close other apps that might be using the camera
- Try restarting the app

### Build fails with "icon.icns not found"

Run the icon generator manually:

```bash
python create_icon.py
iconutil -c icns assets/icon.iconset -o assets/icon.icns
```

---

## Distribution Notes

The build script creates an **ad-hoc signed** app, which works for:
- Personal use
- Internal distribution
- Testing

For **public distribution** (App Store or notarized), you'll need:
1. Apple Developer account ($99/year)
2. Developer ID certificate
3. Notarization with Apple

```bash
# Sign with Developer ID
codesign --force --deep --sign "Developer ID Application: Your Name" "dist/Digital Mirror.app"

# Notarize
xcrun notarytool submit dist/DigitalMirror-1.0.0.dmg --apple-id YOUR_ID --password APP_PASSWORD --team-id TEAM_ID
```

---

## License

MIT License - feel free to use and modify!
