# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Digital Mirror macOS app
Run with: pyinstaller DigitalMirror.spec
"""

import sys
import os
from pathlib import Path

block_cipher = None

# Get the directory containing this spec file
SPEC_DIR = Path(SPECPATH)

# Check if icon exists
icon_path = SPEC_DIR / 'assets' / 'icon.icns'
if not icon_path.exists():
    icon_path = None  # PyInstaller will use default icon
    print("Note: icon.icns not found, using default icon")

a = Analysis(
    ['digital_mirror.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'cv2',
        'numpy',
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'scipy',
        'pandas',
        'PIL',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='DigitalMirror',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # No terminal window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file='entitlements.plist',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='DigitalMirror',
)

app = BUNDLE(
    coll,
    name='Digital Mirror.app',
    icon=str(icon_path) if icon_path else None,
    bundle_identifier='com.digitalmirror.app',
    info_plist={
        'CFBundleName': 'Digital Mirror',
        'CFBundleDisplayName': 'Digital Mirror',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'NSCameraUsageDescription': 'Digital Mirror needs camera access to display your reflection.',
        'NSHighResolutionCapable': True,
        'LSMinimumSystemVersion': '11.0',
        'NSRequiresAquaSystemAppearance': False,  # Support dark mode
        'LSApplicationCategoryType': 'public.app-category.utilities',
    },
)
