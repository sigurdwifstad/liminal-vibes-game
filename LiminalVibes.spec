# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller build spec for Liminal Vibes.

Produces a single, self-contained executable with no external prerequisites
(no system Python required on the end-user's machine):

  * Windows -> dist/LiminalVibes.exe
  * macOS   -> dist/LiminalVibes (raw binary) and dist/LiminalVibes.app (app bundle)
  * Linux   -> dist/LiminalVibes

Build with:
    pyinstaller --noconfirm --clean LiminalVibes.spec

PyInstaller cannot cross-compile: run this on the OS you want to target. The
GitHub Actions workflow in .github/workflows/build-installers.yml runs it on
both windows-latest and macos-latest runners and wraps the result in a native
installer (Inno Setup .exe on Windows, .dmg on macOS).
"""

import sys

from PyInstaller.utils.hooks import collect_all

block_cipher = None

datas = [("resources", "resources")]
binaries = []
hiddenimports = []

# Ursina and Panda3D ship large amounts of non-Python data (models, textures,
# shaders, fonts, DLLs/dylibs) that PyInstaller cannot discover via static
# analysis, so pull it all in explicitly.
for pkg in ("ursina", "panda3d", "panda3d_gltf", "panda3d_simplepbr", "screeninfo", "pygame"):
    try:
        pkg_datas, pkg_binaries, pkg_hiddenimports = collect_all(pkg)
        datas += pkg_datas
        binaries += pkg_binaries
        hiddenimports += pkg_hiddenimports
    except Exception:
        pass

# The bundled libRocket GUI bindings are unused by Ursina/this game, and on
# some platforms (e.g. Apple Silicon) the panda3d wheel only ships an
# x86_64-only "rocket" extension, which breaks the build with an arch
# mismatch. Drop it -- it's optional and never imported here.
binaries = [b for b in binaries if "rocket" not in b[0].lower()]
datas = [d for d in datas if "rocket" not in d[0].lower()]
hiddenimports = [h for h in hiddenimports if "rocket" not in h.lower()]
excludes = ["panda3d.rocket"]

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

is_macos = sys.platform == "darwin"

exe = EXE(
    pyz,
    a.scripts,
    [] if is_macos else a.binaries,
    [] if is_macos else a.zipfiles,
    [] if is_macos else a.datas,
    [],
    exclude_binaries=is_macos,
    name="LiminalVibes",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

# On macOS, PyInstaller recommends onedir (not onefile) when producing a
# proper .app bundle, so collect the onedir output and wrap it in BUNDLE.
# This gives a native double-clickable app with no prerequisites.
if is_macos:
    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name="LiminalVibes",
    )
    app = BUNDLE(
        coll,
        name="LiminalVibes.app",
        icon=None,
        bundle_identifier="com.liminalvibes.game",
        info_plist={
            "CFBundleName": "Liminal Vibes",
            "CFBundleDisplayName": "Liminal Vibes",
            "CFBundleShortVersionString": "1.0.0",
            "NSHighResolutionCapable": True,
        },
    )
