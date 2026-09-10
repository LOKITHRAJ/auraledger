# -*- mode: python ; coding: utf-8 -*-
import os
import sys
import streamlit
from PyInstaller.utils.hooks import copy_metadata

# Locate streamlit package path to bundle its react static frontend assets
streamlit_dir = os.path.dirname(streamlit.__file__)

block_cipher = None

# Custom assets to bundle into the EXE
added_datas = [
    (os.path.join(streamlit_dir, "static"), "streamlit/static"),
    (os.path.join(streamlit_dir, "static"), "static"),
    ("src", "src"),
    ("screens", "screens"),
    ("components", "components"),
    ("services", "services"),
    ("app.py", "."),
]

# Add optional prompts/knowledge if they exist
if os.path.exists("src/prompts"):
    added_datas.append(("src/prompts", "src/prompts"))
if os.path.exists("knowledge"):
    added_datas.append(("knowledge", "knowledge"))

# Bundle package metadata for Streamlit to prevent PackageNotFoundError at runtime
added_datas += copy_metadata('streamlit')

a = Analysis(
    ['launcher.py'],
    pathex=['.'],
    binaries=[],
    datas=added_datas,
    hiddenimports=[
        'streamlit',
        'openpyxl',
        'pandas',
        'plotly',
        'pystray',
        'PIL',
        'cryptography',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Single file or folder packaging target configuration
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='AuraLedgerIQ',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Headless silent mode
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
