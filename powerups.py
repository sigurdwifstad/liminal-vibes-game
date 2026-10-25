from __future__ import annotations

import math
import random
from enum import Enum

from ursina import Entity, Vec3, camera, color, destroy

from core_logic import level_has_powerups


class PowerUpType(Enum):
    HEART = "heart"
    LIGHTNING = "lightning"
    GUN = "gun"
    SPRAY = "spray"


# Icon parts in unit space (-0.5..0.5): (shape, x, y, width, height, rotation_z, color)
_ICON_SPECS = {
    PowerUpType.HEART: (
        ("circle", -0.17, 0.12, 0.40, 0.40, 0, color.rgb(225, 30, 45)),
        ("circle", 0.17, 0.12, 0.40, 0.40, 0, color.rgb(225, 30, 45)),
        ("quad", 0.0, -0.06, 0.43, 0.43, 45, color.rgb(225, 30, 45)),
    ),
    PowerUpType.LIGHTNING: (
        ("quad", 0.07, 0.21, 0.17, 0.55, -25, color.rgb(255, 225, 40)),
        ("quad", -0.07, -0.21, 0.17, 0.55, -25, color.rgb(255, 225, 40)),
        ("quad", 0.0, 0.0, 0.42, 0.14, 0, color.rgb(255, 225, 40)),
    ),
    PowerUpType.GUN: (
        ("quad", 0.0, 0.08, 0.62, 0.2, 0, color.rgb(70, 75, 85)),
        ("quad", 0.38, 0.1, 0.26, 0.11, 0, color.rgb(110, 115, 125)),
        ("quad", -0.17, -0.14, 0.18, 0.36, -15, color.rgb(55, 58, 66)),
    ),
    PowerUpType.SPRAY: (
        ("quad", 0.0, -0.08, 0.32, 0.6, 0, color.rgb(200, 205, 210)),
        ("quad", 0.0, 0.0, 0.32, 0.22, 0, color.rgb(215, 35, 40)),
        ("quad", 0.0, 0.3, 0.18, 0.12, 0, color.rgb(60, 62, 68)),
        ("quad", 0.15, 0.36, 0.14, 0.05, 0, color.rgb(60, 62, 68)),
    ),
}


def build_icon(kind: PowerUpType, parent, size: float, flat: bool) -> Entity:
    """Build a power-up symbol. `flat` -> 2D HUD icon; otherwise a chunky 3D one."""
    root = Entity(parent=parent)
    for shape, x, y, w, h, rot, col in _ICON_SPECS[kind]:
        if flat:
            Entity(parent=root, model=shape, position=Vec3(x * size, y * size, 0), scale=Vec3(w * size, h * size, 1), rotation_z=rot, color=col)
        else:
            model = "sphere" if shape == "circle" else "cube"
            Entity(
                parent=root,
                model=model,
                position=Vec3(x * size, y * size, 0),
                scale=Vec3(w * size, h * size, 0.18 * size),
                rotation_z=rot,
                color=col,
                unlit=True,
            )
    return root


class PowerUpPickup(Entity):
    BASE_HEIGHT = 1.1
    BOB_AMPLITUDE = 0.12

    def __init__(self, kind: PowerUpType, position: Vec3, phase: float = 0.0):
        super().__init__(position=position)
        self.kind = kind
        self._base_y = self.BASE_HEIGHT
        self._phase = phase
        self.visual = build_icon(kind, self, size=1.0, flat=False)
        self.y = self._base_y

    def animate_step(self, t: float, dt: float) -> None:
        self.rotation_y += 40.0 * dt
        self.y = self._base_y + math.sin(t * 2.0 + self._phase) * self.BOB_AMPLITUDE


class PowerUpManager:
    PICKUP_RADIUS = 1.3

    def __init__(self) -> None:
        self.pickups: list[PowerUpPickup] = []
        self.held: set[PowerUpType] = set()
        self.gun_used = False
        self._t = 0.0

    def clear(self) -> None:
        for pickup in self.pickups:
            destroy(pickup)
        self.pickups.clear()
        self.held.clear()
        self.gun_used = False

    def spawn_for_level(self, maze, level: int) -> None:
        self.clear()
        if not level_has_powerups(level):
            return
        rng = random.Random(f"{maze.seed}|powerups|{level}")
        cells = maze.dead_end_cells()
        rng.shuffle(cells)
        count = len(PowerUpType)
        chosen = cells[:count]
        if len(chosen) < count:
            used = set(chosen) | {maze.start_cell, maze.exit_cell}
            spare = sorted(c for c in maze.walkable_cells if c not in used)
            rng.shuffle(spare)
            chosen += spare[: count - len(chosen)]
        for index, (kind, cell) in enumerate(zip(PowerUpType, chosen)):
            wx, wz = maze.world_from_cell(cell)
            self.pickups.append(PowerUpPickup(kind, Vec3(wx, 0, wz), phase=index * 2.1))

    def update(self, dt: float, player_position: Vec3) -> list[PowerUpType]:
        self._t += dt
        collected: list[PowerUpType] = []
        for pickup in list(self.pickups):
            pickup.animate_step(self._t, dt)
            dx = pickup.x - player_position.x
            dz = pickup.z - player_position.z
            if dx * dx + dz * dz <= self.PICKUP_RADIUS ** 2:
                self.pickups.remove(pickup)
                self.held.add(pickup.kind)
                collected.append(pickup.kind)
                destroy(pickup)
        return collected

    def has(self, kind: PowerUpType) -> bool:
        return kind in self.held

    @property
    def gun_ready(self) -> bool:
        return PowerUpType.GUN in self.held

    def consume(self, kind: PowerUpType) -> None:
        self.held.discard(kind)
        if kind is PowerUpType.GUN:
            self.gun_used = True


class PowerUpHUD:
    ICON_SIZE = 0.06
    ICON_GAP = 0.075

    def __init__(self, left_x: float, bar_y: float) -> None:
        self.left_x = left_x
        self.y = bar_y + 0.065
        self.icons = {kind: build_icon(kind, camera.ui, self.ICON_SIZE, flat=True) for kind in PowerUpType}
        for icon in self.icons.values():
            icon.enabled = False
        self.crosshair = Entity(parent=camera.ui, enabled=False)
        for w, h in ((0.022, 0.003), (0.003, 0.022)):
            Entity(parent=self.crosshair, model="quad", scale=Vec3(w, h, 1), color=color.rgba(255, 255, 255, 220))
        self.set_left_x(left_x)

    def set_left_x(self, left_x: float) -> None:
        self.left_x = left_x

    def refresh(self, held: set[PowerUpType], show: bool = True) -> None:
        slot = 0
        for kind in PowerUpType:
            icon = self.icons[kind]
            visible = show and kind in held
            icon.enabled = visible
            if visible:
                icon.position = Vec3(self.left_x + self.ICON_SIZE * 0.5 + slot * self.ICON_GAP, self.y, 0)
                slot += 1
        self.crosshair.enabled = show and PowerUpType.GUN in held
