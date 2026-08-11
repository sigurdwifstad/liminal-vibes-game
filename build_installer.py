"""Build a native, prerequisite-free installer for the current OS.

Run this on Windows to produce a Windows installer, or on macOS to produce a
macOS installer. PyInstaller cannot cross-compile, so each installer must be
built on its target OS (this is exactly what the GitHub Actions workflow in
.github/workflows/build-installers.yml does automatically for both OSes).

Usage:
    python build_installer.py

Windows output: installer/Output/LiminalVibesSetup.exe
  Requires Inno Setup (https://jrsoftware.org/isinfo.php) to be installed and
  `iscc` (or `ISCC.exe`) available on PATH. Inno Setup is a build-time tool
  only -- the resulting installer has no prerequisites for end users.

macOS output: dist/LiminalVibes.dmg
  Uses only tools built into macOS (hdiutil), so nothing extra to install.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent


def run_pyinstaller() -> None:
    print("== Running PyInstaller ==")
    subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "LiminalVibes.spec"],
        cwd=ROOT,
        check=True,
    )


def package_windows() -> Path:
    iscc = shutil.which("iscc") or shutil.which("ISCC")
    if not iscc:
        raise SystemExit(
            "Inno Setup (iscc) not found on PATH. Install it from "
            "https://jrsoftware.org/isinfo.php, then re-run this script."
        )
    print("== Building Windows installer with Inno Setup ==")
    subprocess.run([iscc, str(ROOT / "installer" / "windows.iss")], cwd=ROOT, check=True)
    return ROOT / "installer" / "Output" / "LiminalVibesSetup.exe"


def package_macos() -> Path:
    print("== Building macOS .dmg ==")
    subprocess.run([str(ROOT / "installer" / "build_macos_dmg.sh")], cwd=ROOT, check=True)
    return ROOT / "dist" / "LiminalVibes.dmg"


def main() -> int:
    run_pyinstaller()

    if sys.platform.startswith("win"):
        output = package_windows()
    elif sys.platform == "darwin":
        output = package_macos()
    else:
        print("No installer packaging is defined for this OS; the raw binary "
              "is available at dist/LiminalVibes.")
        return 0

    if output.exists():
        print(f"\nInstaller ready: {output}")
        return 0

    print(f"\nExpected installer was not found at {output}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
