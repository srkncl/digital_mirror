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

### 1. Create a virtual environment (recommended)

```bash
python3 -m venv venv
source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the app

```bash
python digital_mirror.py
```

---

## Build macOS App (.app + .dmg)

### Automated Build (Recommended)

Run the build script - it handles everything:

```bash
chmod +x build_macos.sh
./build_macos.sh
```

This will:
1. Set up a virtual environment
2. Install all dependencies
3. Generate the app icon
4. Build the `.app` bundle with PyInstaller
5. Create a `.dmg` installer

**Output:**
- `dist/Digital Mirror.app` - The application bundle
- `dist/DigitalMirror-1.0.0.dmg` - DMG installer

### Manual Build Steps

If you prefer to build manually:

```bash
# 1. Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt
pip install pyinstaller pillow

# 3. Generate icon
python create_icon.py
iconutil -c icns assets/icon.iconset -o assets/icon.icns

# 4. Build with PyInstaller
pyinstaller DigitalMirror.spec

# 5. Sign the app (ad-hoc for local use)
codesign --force --deep --sign - "dist/Digital Mirror.app"
```

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
├── requirements.txt       # Python dependencies
├── DigitalMirror.spec     # PyInstaller configuration
├── entitlements.plist     # macOS entitlements (camera access)
├── create_icon.py         # Icon generator script
├── build_macos.sh         # Automated build script
├── assets/                # Generated assets
│   ├── icon.iconset/      # Icon images
│   └── icon.icns          # macOS icon file
└── dist/                  # Build output
    ├── Digital Mirror.app
    └── DigitalMirror-1.0.0.dmg
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
