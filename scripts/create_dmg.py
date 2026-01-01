#!/usr/bin/env python3
"""Create DMG installer with Applications shortcut."""

import os
import shutil
import subprocess
import sys

# Add parent directory to path to import VERSION
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from digital_mirror import VERSION

APP_NAME = "Digital Mirror"
DMG_DIR = "dist/dmg"
APP_PATH = f"dist/{APP_NAME}.app"


def main():
    # Check if app exists
    if not os.path.exists(APP_PATH):
        print(f"Error: {APP_PATH} not found. Run 'hatch run build' first.")
        sys.exit(1)

    # Clean up any existing dmg directory
    if os.path.exists(DMG_DIR):
        shutil.rmtree(DMG_DIR)

    # Create dmg directory and copy app
    os.makedirs(DMG_DIR)
    shutil.copytree(APP_PATH, f"{DMG_DIR}/{APP_NAME}.app")

    # Create Applications symlink
    os.symlink("/Applications", f"{DMG_DIR}/Applications")

    # Create DMG
    dmg_path = f"dist/DigitalMirror-{VERSION}.dmg"
    subprocess.run(
        [
            "hdiutil",
            "create",
            "-volname",
            APP_NAME,
            "-srcfolder",
            DMG_DIR,
            "-ov",
            "-format",
            "UDZO",
            dmg_path,
        ],
        check=True,
    )

    # Clean up
    shutil.rmtree(DMG_DIR)

    print(f"Created: {dmg_path}")


if __name__ == "__main__":
    main()
