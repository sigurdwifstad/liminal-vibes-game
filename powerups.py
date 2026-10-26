from __future__ import annotations

import math
import random
from enum import Enum

from ursina import Entity, Mesh, Vec3, camera, color, destroy

from core_logic import level_has_powerups


class PowerUpType(Enum):
    HEART = "heart"
    LIGHTNING = "lightning"
    GUN = "gun"
    SPRAY = "spray"


# Lightning bolt as one solid polygon (no seams between parts), triangulated by hand.
_BOLT_POINTS = ((0.12, 0.5), (-0.22, -0.04), (-0.02, -0.04), (-0.12, -0.5), (0.22, 0.06), (0.02, 0.06))
_BOLT_TRIANGLES = ((0, 1, 2), (0, 2, 5), (2, 4, 5), (2, 3, 4))

# Icon parts in unit space (-0.5..0.5): (shape, x, y, width, height, rotation_z, color)
_ICON_SPECS = {
    PowerUpType.HEART: (
        # A square rotated 45 degrees with a circle (diameter = side) centred on the
        # midpoint of each upper side: lobe centres sit at (+-s/(2*sqrt2), c + s/(2*sqrt2)).
        ("circle", -0.1414, 0.1114, 0.40, 0.40, 0, color.rgb(225, 30, 45)),
        ("circle", 0.1414, 0.1114, 0.40, 0.40, 0, color.rgb(225, 30, 45)),
        ("quad", 0.0, -0.03, 0.40, 0.40, 45, color.rgb(225, 30, 45)),
    ),
    PowerUpType.LIGHTNING: (
        ("poly", _BOLT_POINTS, _BOLT_TRIANGLES, color.rgb(255, 225, 40)),
    ),
    PowerUpType.GUN: (
        ("quad", 0.0, 0.08, 0.62, 0.2, 0, color.rgb(70, 75, 85)),
        ("quad", 0.38, 0.1, 0.26, 0.11, 0, color.rgb(110, 115, 125)),
        ("quad", -0.17, -0.14, 0.18, 0.36, -15, color.rgb(55, 58, 66)),
    ),
    PowerUpType.SPRAY: (
        ("quad", 0.0, -0.08, 0.32, 0.6, 0, color.rgb(200, 205, 210)),
        ("quad", 0.0, 0.0, 0.35, 0.22, 0, color.rgb(215, 35, 40)),
        ("quad", 0.0, 0.28, 0.18, 0.12, 0, color.rgb(60, 62, 68)),
        ("quad", 0.15, 0.31, 0.14, 0.05, 0, color.rgb(60, 62, 68)),
    ),
}


def _poly_mesh(points, triangles, size: float, half_depth: float | None) -> Mesh:
    """Flat double-sided polygon, or an extruded prism when `half_depth` is given."""
    if half_depth is None:
        verts = [Vec3(x * size, y * size, 0) for x, y in points]
        tris = [t for t in triangles] + [(t[2], t[1], t[0]) for t in triangles]
        return Mesh(vertices=verts, triangles=tris, mode="triangle")

    n = len(points)
    verts = [Vec3(x * size, y * size, -half_depth) for x, y in points] + [Vec3(x * size, y * size, half_depth) for x, y in points]
    tris = [t for t in triangles] + [(t[0] + n, t[1] + n, t[2] + n) for t in triangles]
    for i in range(n):
        j = (i + 1) % n
        tris.append((i, j, j + n))
        tris.append((i, j + n, i + n))
    return Mesh(vertices=verts, triangles=tris, mode="triangle")


def build_icon(kind: PowerUpType, parent, size: float, flat: bool) -> Entity:
    """Build a power-up symbol. `flat` -> 2D HUD icon; otherwise a chunky 3D one."""
    root = Entity(parent=parent)
    for index, part in enumerate(_ICON_SPECS[kind]):
        # Later parts are slightly thicker so overlapping faces are never coplanar (z-fighting).
        depth = (0.18 + 0.004 * index) * size
        if part[0] == "poly":
            _, points, triangles, col = part
            Entity(parent=root, model=_poly_mesh(points, triangles, size, None if flat else depth * 0.5), color=col, unlit=True, double_sided=True)
            continue
        shape, x, y, w, h, rot, col = part
        if flat:
            Entity(parent=root, model=shape, position=Vec3(x * size, y * size, 0), scale=Vec3(w * size, h * size, 1), rotation_z=rot, color=col)
        else:
            if shape == "circle":
                # Extruded disc so round parts have the same thickness as the box parts.
                ring = [(0.5 * math.cos(i * math.tau / 24), 0.5 * math.sin(i * math.tau / 24)) for i in range(24)]
                fan = [(0, i, i + 1) for i in range(1, 23)]
                model = _poly_mesh(ring, fan, 1.0, 0.5)
            else:
                model = "cube"
            Entity(
                parent=root,
                model=model,
                position=Vec3(x * size, y * size, 0),
                scale=Vec3(w * size, h * size, depth),
                rotation_z=rot,
                color=col,
                unlit=True,
                double_sided=True,
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
