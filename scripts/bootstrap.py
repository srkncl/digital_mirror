#!/usr/bin/env python3
"""Bootstrap script for Digital Mirror development environment.

Run this after cloning the repository to set up everything needed.
"""

import os
import subprocess
import sys
import venv
from pathlib import Path

VENV_DIR = ".venv"
PROJECT_ROOT = Path(__file__).parent.parent


def run(cmd, **kwargs):
    """Run a command and print it."""
    print(f"  $ {cmd}")
    subprocess.run(cmd, shell=True, check=True, **kwargs)


def main():
    os.chdir(PROJECT_ROOT)

    print("\n🪞 Digital Mirror - Bootstrap\n")
    print("=" * 50)

    # Check Python version
    if sys.version_info < (3, 9):
        print(f"❌ Python 3.9+ required, got {sys.version}")
        sys.exit(1)
    print(f"✓ Python {sys.version_info.major}.{sys.version_info.minor}")

    # Create virtual environment if it doesn't exist
    venv_path = PROJECT_ROOT / VENV_DIR
    if not venv_path.exists():
        print(f"\n📦 Creating virtual environment in {VENV_DIR}/...")
        venv.create(venv_path, with_pip=True)
        print("✓ Virtual environment created")
    else:
        print(f"✓ Virtual environment exists at {VENV_DIR}/")

    # Determine pip path
    if sys.platform == "win32":
        pip = venv_path / "Scripts" / "pip"
        python = venv_path / "Scripts" / "python"
    else:
        pip = venv_path / "bin" / "pip"
        python = venv_path / "bin" / "python"

    # Upgrade pip
    print("\n📦 Upgrading pip...")
    run(f'"{pip}" install --upgrade pip')

    # Install hatch
    print("\n📦 Installing Hatch...")
    run(f'"{pip}" install hatch')

    # Install project dependencies
    print("\n📦 Installing project dependencies...")
    run(f'"{pip}" install -r requirements.txt')

    # Install build dependencies
    print("\n📦 Installing build dependencies...")
    run(f'"{pip}" install pyinstaller pillow')

    print("\n" + "=" * 50)
    print("✨ Bootstrap complete!\n")
    print("To activate the environment:")
    print(f"  source {VENV_DIR}/bin/activate")
    print("\nTo run the app:")
    print("  hatch run run")
    print("  # or: python digital_mirror.py")
    print("\nTo build a release:")
    print("  hatch run release")
    print()


if __name__ == "__main__":
    main()
