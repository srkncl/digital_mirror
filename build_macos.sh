#!/bin/bash
#
# Build script for Digital Mirror macOS app
# Creates a .app bundle and optional .dmg installer
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
APP_NAME="Digital Mirror"
APP_VERSION="1.0.0"
BUNDLE_ID="com.digitalmirror.app"

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  🪞 Digital Mirror - macOS App Builder${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Check if running on macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    echo -e "${RED}❌ This script must be run on macOS${NC}"
    exit 1
fi

# Check Python
echo -e "${YELLOW}Checking Python...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 not found. Please install Python 3.9+${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo -e "${GREEN}✓ Python $PYTHON_VERSION found${NC}"

# Create/activate virtual environment
echo ""
echo -e "${YELLOW}Setting up virtual environment...${NC}"
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo -e "${GREEN}✓ Created virtual environment${NC}"
fi

source venv/bin/activate
echo -e "${GREEN}✓ Activated virtual environment${NC}"

# Install dependencies
echo ""
echo -e "${YELLOW}Installing dependencies...${NC}"
pip install --upgrade pip -q
pip install -r requirements.txt -q
pip install pyinstaller pillow -q
echo -e "${GREEN}✓ Dependencies installed${NC}"

# Generate app icon
echo ""
echo -e "${YELLOW}Generating app icon...${NC}"
python3 create_icon.py

# Check if icon was created
if [ ! -f "assets/icon.icns" ]; then
    echo -e "${YELLOW}⚠️  icon.icns not found, creating from iconset...${NC}"
    if [ -d "assets/icon.iconset" ]; then
        iconutil -c icns assets/icon.iconset -o assets/icon.icns
        echo -e "${GREEN}✓ Created icon.icns${NC}"
    else
        echo -e "${RED}❌ Could not create icon. Using default.${NC}"
    fi
fi

# Clean previous builds
echo ""
echo -e "${YELLOW}Cleaning previous builds...${NC}"
rm -rf build dist
echo -e "${GREEN}✓ Cleaned build directories${NC}"

# Build with PyInstaller
echo ""
echo -e "${YELLOW}Building app with PyInstaller...${NC}"
echo -e "${BLUE}  This may take a few minutes...${NC}"
pyinstaller DigitalMirror.spec --noconfirm

if [ ! -d "dist/Digital Mirror.app" ]; then
    echo -e "${RED}❌ Build failed - app bundle not created${NC}"
    exit 1
fi

echo -e "${GREEN}✓ App bundle created${NC}"

# Sign the app (ad-hoc signing for local use)
echo ""
echo -e "${YELLOW}Signing app (ad-hoc)...${NC}"
codesign --force --deep --sign - "dist/Digital Mirror.app" 2>/dev/null || true
echo -e "${GREEN}✓ App signed${NC}"

# Create DMG installer
echo ""
echo -e "${YELLOW}Creating DMG installer...${NC}"

DMG_NAME="DigitalMirror-${APP_VERSION}.dmg"
DMG_TEMP="dist/temp.dmg"
DMG_FINAL="dist/${DMG_NAME}"

# Create a temporary directory for DMG contents
DMG_DIR="dist/dmg"
rm -rf "$DMG_DIR"
mkdir -p "$DMG_DIR"

# Copy app to DMG directory
cp -R "dist/Digital Mirror.app" "$DMG_DIR/"

# Create symbolic link to Applications folder
ln -s /Applications "$DMG_DIR/Applications"

# Create the DMG
hdiutil create -volname "Digital Mirror" -srcfolder "$DMG_DIR" -ov -format UDZO "$DMG_FINAL"

# Clean up
rm -rf "$DMG_DIR"

echo -e "${GREEN}✓ DMG created: $DMG_FINAL${NC}"

# Summary
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  ✨ Build Complete!${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "  ${BLUE}App Bundle:${NC}  dist/Digital Mirror.app"
echo -e "  ${BLUE}DMG Installer:${NC}  dist/${DMG_NAME}"
echo ""
echo -e "  ${YELLOW}To install:${NC}"
echo -e "    1. Open the DMG file"
echo -e "    2. Drag 'Digital Mirror' to Applications"
echo -e "    3. On first launch, right-click → Open (to bypass Gatekeeper)"
echo ""
echo -e "  ${YELLOW}Note:${NC} The app is ad-hoc signed for local use."
echo -e "        For distribution, you'll need an Apple Developer certificate."
echo ""

# Deactivate virtual environment
deactivate
