# Release Notes

## v1.2.0 (2026-01-01)

### New Features
- **WhatsApp Sticker Mode** - Create stickers with transparent background
  - Face-only segmentation using MediaPipe AI
  - Automatic white outline for sticker effect
  - Mask editing tool to refine sticker outline
  - Export as WebP (512x512, <500KB) for WhatsApp

### Improvements
- Simplified icon-only toolbar with tooltips
- Default mask edit mode set to erase for easier refinement

---

## v1.1.0 (2026-01-01)

### New Features
- **Zoom up to 5x** - Extended zoom range from 3x to 5x
- **Freeze frame** - Click and hold to temporarily freeze, or double-tap to lock
- **Pan frozen image** - Navigate zoomed frozen frames with:
  - Trackpad two-finger scroll
  - Mouse drag (when locked)
  - Arrow keys
- **Pinch-to-zoom** - Native trackpad gesture support for zoom control
- **iOS support** - Added compatibility for iOS devices via Pyto/Pythonista

### Improvements
- Removed Windows and Linux support (Apple platforms only)
- Simplified camera device detection for macOS/iOS
- Added frozen state overlay with contextual instructions

### Technical
- Added `is_ios()` helper for platform detection
- Refactored frame rendering with pan offset support
- Added `wheelEvent` handler for scroll-based panning

---

## v1.0.0 (2025-12-31)

### Initial Release
- Real-time camera preview
- Mirror mode (horizontal flip)
- Zoom control (1x to 3x)
- Brightness adjustment
- Fullscreen support
- Multiple camera support with device name detection
- Persistent settings (camera, mirror, zoom, brightness, window geometry)
- Dark theme UI
- Keyboard shortcuts:
  - `M` - Toggle mirror mode
  - `F` - Toggle fullscreen
  - `Esc` - Exit fullscreen
  - `Q` - Quit app

### Platforms
- macOS (primary)
- iOS (via Pyto/Pythonista)
