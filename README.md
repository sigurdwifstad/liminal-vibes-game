# Liminal Vibes

A first-person 3D liminal horror game built with Python + Ursina, heavily vibe coded of course.
The game is inspired by the "Backrooms" lore and feature film.

![A strange looking, empty office building hallway](resources/LiminalVibes.jpg)

## Game Description
- You are a child trapped in a strange, empty office building.
- Explore a procedurally generated maze-like environment and try to reach the exit. 
- It seems you are not entirely alone in the building...

## Controls
- Move: `WASD`
- Look: Mouse/touchpad (or arrow keys)
- FOV adjust: `Q` / `E`
- Sprint: Hold `Shift`
- Restart after death: `R`

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

## Test Mode

Use test mode for more improved quality of life while testing. In this mode, the player is invincible and the mazes are small.
An extra HUD appears with additional information.

```bash
python main.py --test
```

To enable test mode only when you reach a specific level (for instance level 5), use:

```bash
python main.py --test-level-5
```

To jump directly to a specific level (for instance level 5), use:

```bash
python main.py --start-level 5
```

## Run Tests

```bash
python run_tests.py
```

## Building Installers (Windows & macOS, no prerequisites for players)

Players don't need Python installed — they just download and run the
installer for their OS:

- **Windows**: `LiminalVibesSetup.exe` — a standard installer with Start Menu/
  desktop shortcuts and an uninstaller.
- **macOS**: `LiminalVibes.dmg` — open it and drag Liminal Vibes into
  Applications.

### Recommended: build both via GitHub Actions

PyInstaller cannot cross-compile, so each installer must be built on its
native OS. The workflow in `.github/workflows/build-installers.yml` handles
this automatically using GitHub-hosted Windows and macOS runners:

- Push a tag like `v1.0.0` to build both installers and attach them to a new
  GitHub Release, or
- Trigger it manually from the Actions tab ("Run workflow") and download the
  artifacts.

No local setup is required to use this — it all runs in CI.

### Building locally

To build on your own machine instead, run the matching OS's steps:

```bash
pip install -r requirements-build.txt
python build_installer.py
```

- On Windows this also requires [Inno Setup](https://jrsoftware.org/isinfo.php)
  (a build-time tool only) to be installed and `iscc`/`ISCC.exe` on your PATH.
  Output: `installer/Output/LiminalVibesSetup.exe`.
- On macOS this uses only built-in tools (`hdiutil`). Output:
  `dist/LiminalVibes.dmg`.

