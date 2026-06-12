# Liminal Spaces

A first-person 3D liminal horror prototype built with Python + Ursina.

## Features
- Finite maze levels that grow larger each time you reach the exit door in the wall.
- Procedural textures on walls, floor, and ceiling for subtle surface detail.
- First-person movement (`WASD`) and camera look with both arrow keys and mouse/touchpad.
- Sprint with `Shift` plus stamina depletion/refill bar.
- Monster spawns after exploration time, then chases player.
- Monster starts slower, ramps speed in stepped phases with an upper cap.
- Monster has simple procedural limb walk animation while moving.
- Monster never spawns in your current line of sight.
- When out of view, monster can occasionally teleport to another hidden location.
- On death: `GAME OVER` screen with survival time in `MM:SS`.
- Every restart uses a new random seed.

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

## Test Mode

Use test mode to spawn the monster immediately. In this mode, the monster still chases but cannot kill the player.
An extra HUD appears with elapsed time, current monster speed, and whether the monster would have killed the player.

```bash
python main.py --test
```

## Controls
- Move: `WASD`
- Look: Arrow keys + mouse/touchpad
- FOV adjust: `Q` / `E`
- Sprint: Hold `Shift`
- Restart after death: `R`

## Run Tests

```bash
python run_tests.py
```

