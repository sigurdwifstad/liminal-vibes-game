from __future__ import annotations

import math
import random
from collections import deque
from typing import Iterable, List, Set, Tuple

from panda3d.core import PNMImage, Texture as PandaTexture
from ursina import Entity, Texture, Vec3, color, destroy

from core_logic import touches_exit_portal

Cell = Tuple[int, int]


class MazeManager:
    def __init__(self, seed: int, level: int, cell_size: float = 4.0, test: bool = False):
        self.seed = seed
        self.level = max(1, level)
        self.test = test
        self.cell_size = cell_size
        self.grid_size = self._maze_cells_per_side(self.level)
        self.half_grid = self.grid_size // 2

        self.entities: List[Entity] = []
        self.walkable_cells: Set[Cell] = set()
        self.start_cell: Cell = (0, 0)
        self.exit_cell: Cell = (0, 0)
        self.exit_wall_cell: Cell = (0, 0)
        self.exit_direction: Cell = (1, 0)
        self.wall_height = 3.0
        self.exit_portal_height = 2.0
        self.exit_portal_width_ratio = 1.0 / 3.0

        self._inv_cell_size: float = 1.0 / cell_size

        self.wall_texture = self._build_wall_texture()
        self.floor_texture = self._build_floor_texture()
        self.ceiling_texture = self._build_ceiling_texture()
        self.door_texture = self._build_door_texture()

        self._generate_level()

    def _maze_cells_per_side(self, level: int) -> int:
        if self.test:
            return 9
        size = 17 + (level - 1) * 4
        if size % 2 == 0:
            size += 1
        return min(size, 61)

    def _global_from_local(self, lx: int, lz: int) -> Cell:
        return lx - self.half_grid, lz - self.half_grid

    def _build_wall_texture(self) -> Texture:
        img = self._build_wall_surface_image()

        panda_tex = PandaTexture("liminal_wall")
        panda_tex.load(img)
        texture = Texture(panda_tex)
        texture.filtering = "bilinear"
        return texture

    def _build_wall_surface_image(self) -> PNMImage:
        size = 128
        img = PNMImage(size, size)
        rng = random.Random(f"{self.seed}|wall_texture")

        base_r, base_g, base_b = 214 / 255.0, 205 / 255.0, 170 / 255.0
        for y in range(size):
            horizontal_wave = 0.006 * ((y % 20) / 20.0)
            for x in range(size):
                grain = rng.uniform(-0.02, 0.02)
                vertical_band = 0.014 if (x % 32) < 2 else 0.0
                blotch = 0.008 if (x // 9 + y // 11) % 13 == 0 else 0.0
                shade = max(-0.06, min(0.06, grain - vertical_band + blotch + horizontal_wave))
                img.setXel(x, y, base_r + shade, base_g + shade, base_b + shade)
        return img

    def _build_floor_texture(self) -> Texture:
        size = 128
        img = PNMImage(size, size)
        rng = random.Random(f"{self.seed}|floor_texture")

        base_r, base_g, base_b = 214 / 255.0, 205 / 255.0, 170 / 255.0
        for y in range(size):
            for x in range(size):
                grain = rng.uniform(-0.028, 0.02)
                stain = -0.03 if (x // 14 + y // 9) % 17 == 0 else 0.0
                seam = -0.015 if (x % 32) in (0, 1) or (y % 32) in (0, 1) else 0.0
                shade = max(-0.08, min(0.05, grain + stain + seam))
                img.setXel(x, y, base_r + shade, base_g + shade, base_b + shade)

        panda_tex = PandaTexture("liminal_floor")
        panda_tex.load(img)
        texture = Texture(panda_tex)
        texture.filtering = "bilinear"
        return texture

    def _build_ceiling_texture(self) -> Texture:
        size = 128
        img = PNMImage(size, size)
        rng = random.Random(f"{self.seed}|ceiling_texture")

        base_r, base_g, base_b = 214 / 255.0, 205 / 255.0, 170 / 255.0
        for y in range(size):
            for x in range(size):
                grain = rng.uniform(-0.016, 0.014)
                tile_line = -0.012 if (x % 32) in (0, 1) or (y % 32) in (0, 1) else 0.0
                shade = max(-0.05, min(0.04, grain + tile_line))
                img.setXel(x, y, base_r + shade, base_g + shade, base_b + shade)

        panda_tex = PandaTexture("liminal_ceiling")
        panda_tex.load(img)
        texture = Texture(panda_tex)
        texture.filtering = "bilinear"
        return texture

    def _build_door_texture(self) -> Texture:
        size = 128
        img = PNMImage(size, size, 4)
        for y in range(size):
            for x in range(size):
                img.setXel(x, y, 0.0, 0.0, 0.0)
                img.setAlpha(x, y, 0.0)

        tape_rng = random.Random(f"{self.seed}|door_tape")
        portal_width_px = max(22, int(size * self.exit_portal_width_ratio))
        half_width = portal_width_px // 2
        center_x = size // 2
        left_center = center_x - half_width
        right_center = center_x + half_width
        top_y = max(18, min(size - 8, int(size * (self.exit_portal_height / self.wall_height))))

        def paint_tape(px: int, py: int, alpha_scale: float = 1.0) -> None:
            if not (0 <= px < size and 0 <= py < size):
                return
            shade = tape_rng.uniform(-0.07, 0.05)
            blue_r = min(1.0, max(0.0, 38 / 255.0 + shade * 0.18))
            blue_g = min(1.0, max(0.0, 135 / 255.0 + shade * 0.24))
            blue_b = min(1.0, max(0.0, 1.0 + shade * 0.08))
            alpha = min(1.0, max(0.0, 0.86 + shade * 0.22)) * alpha_scale
            img.setXel(px, py, blue_r, blue_g, blue_b)
            img.setAlpha(px, py, alpha)

        for py in range(0, top_y + 1):
            left_shift = int(1.5 * math.sin(py * 0.12 + 0.3)) + tape_rng.randint(-1, 1)
            right_shift = int(1.5 * math.sin(py * 0.11 + 1.7)) + tape_rng.randint(-1, 1)
            left_width = 5 + (1 if (py // 11) % 2 == 0 else 0)
            right_width = 4 + (1 if (py // 9) % 2 == 1 else 0)

            for px in range(left_center + left_shift - left_width, left_center + left_shift + left_width + 1):
                if tape_rng.random() > 0.04:
                    paint_tape(px, py, alpha_scale=0.92 if abs(px - (left_center + left_shift)) > left_width - 2 else 1.0)

            for px in range(right_center + right_shift - right_width, right_center + right_shift + right_width + 1):
                if tape_rng.random() > 0.05:
                    paint_tape(px, py, alpha_scale=0.9 if abs(px - (right_center + right_shift)) > right_width - 1 else 1.0)

        top_band_half = 4
        for px in range(left_center - 2, right_center + 3):
            top_curve = int(1.2 * math.sin(px * 0.09 + 0.8))
            for py in range(top_y + top_curve - top_band_half, top_y + top_curve + top_band_half + 1):
                if tape_rng.random() > 0.035:
                    edge_alpha = 0.9 if abs(py - (top_y + top_curve)) >= top_band_half - 1 else 1.0
                    paint_tape(px, py, alpha_scale=edge_alpha)

        panda_tex = PandaTexture("liminal_door")
        panda_tex.load(img)
        texture = Texture(panda_tex)
        texture.filtering = "bilinear"
        return texture

    def _generate_walkable_cells(self) -> Set[Cell]:
        grid = [[False for _ in range(self.grid_size)] for _ in range(self.grid_size)]
        rng = random.Random(f"{self.seed}|level|{self.level}")
        stack = [(1, 1)]
        grid[1][1] = True

        directions = [(2, 0), (-2, 0), (0, 2), (0, -2)]
        while stack:
            x, z = stack[-1]
            neighbors = []
            for dx, dz in directions:
                nx, nz = x + dx, z + dz
                if 1 <= nx < self.grid_size - 1 and 1 <= nz < self.grid_size - 1 and not grid[nz][nx]:
                    neighbors.append((nx, nz, dx // 2, dz // 2))

            if not neighbors:
                stack.pop()
                continue

            nx, nz, wx, wz = rng.choice(neighbors)
            grid[z + wz][x + wx] = True
            grid[nz][nx] = True
            stack.append((nx, nz))

        walkable: Set[Cell] = set()
        for lz in range(self.grid_size):
            for lx in range(self.grid_size):
                if grid[lz][lx]:
                    walkable.add(self._global_from_local(lx, lz))
        return walkable

    def _pick_farthest_cell(self, start: Cell) -> Cell:
        visited = {start}
        queue = deque([(start, 0)])
        farthest = start
        far_dist = 0

        while queue:
            cell, dist = queue.popleft()
            if dist > far_dist:
                far_dist = dist
                farthest = cell

            for nb in self.walkable_neighbors(cell):
                if nb not in visited:
                    visited.add(nb)
                    queue.append((nb, dist + 1))

        return farthest

    def _is_boundary_adjacent_walkable(self, cell: Cell) -> bool:
        lx = cell[0] + self.half_grid
        lz = cell[1] + self.half_grid
        return lx in (1, self.grid_size - 2) or lz in (1, self.grid_size - 2)

    def _pick_exit_anchor_cell(self, start: Cell) -> Cell:
        visited = {start}
        queue = deque([(start, 0)])
        best = start
        best_dist = -1

        while queue:
            cell, dist = queue.popleft()
            if self._is_boundary_adjacent_walkable(cell) and dist > best_dist:
                best = cell
                best_dist = dist

            for nb in self.walkable_neighbors(cell):
                if nb not in visited:
                    visited.add(nb)
                    queue.append((nb, dist + 1))

        if best_dist >= 0:
            return best
        return self._pick_farthest_cell(start)

    def _exit_dir_from_anchor(self, anchor: Cell) -> Cell:
        lx = anchor[0] + self.half_grid
        lz = anchor[1] + self.half_grid
        distances = {
            (-1, 0): lx,
            (1, 0): (self.grid_size - 1) - lx,
            (0, -1): lz,
            (0, 1): (self.grid_size - 1) - lz,
        }
        return min(distances, key=distances.get)

    def _append_exit_door_entities(self, x: float, z: float, wall_height: float) -> None:
        self.entities.append(
            Entity(
                model="cube",
                position=Vec3(x, wall_height * 0.5, z),
                scale=Vec3(self.cell_size, wall_height, self.cell_size),
                color=color.rgb(214, 205, 170),
                texture=self.wall_texture,
                texture_scale=(1.0, 1.4),
                collider="box",
            )
        )

        tape_rng = random.Random(f"{self.seed}|exit_tape|{self.exit_wall_cell[0]}|{self.exit_wall_cell[1]}")
        tape_color = color.rgb(48, 148, 255)
        tape_depth = 0.035
        wall_base_y = 0.0
        tape_thickness = 0.095
        top_thickness = 0.09
        portal_width = self.cell_size * self.exit_portal_width_ratio
        portal_left = -(self.cell_size / 6.0)
        portal_right = self.cell_size / 6.0
        portal_top_y = self.exit_portal_height

        if self.exit_direction == (1, 0):
            face_center = Vec3(x - (self.cell_size * 0.5) - (tape_depth * 0.5), wall_base_y, z)
            lateral_axis = Vec3(0, 0, 1)
        elif self.exit_direction == (-1, 0):
            face_center = Vec3(x + (self.cell_size * 0.5) + (tape_depth * 0.5), wall_base_y, z)
            lateral_axis = Vec3(0, 0, 1)
        elif self.exit_direction == (0, 1):
            face_center = Vec3(x, wall_base_y, z - (self.cell_size * 0.5) - (tape_depth * 0.5))
            lateral_axis = Vec3(1, 0, 0)
        else:
            face_center = Vec3(x, wall_base_y, z + (self.cell_size * 0.5) + (tape_depth * 0.5))
            lateral_axis = Vec3(1, 0, 0)

        def add_tape_strip(center: Vec3, scale: Vec3, rotation_z: float = 0.0) -> None:
            self.entities.append(
                Entity(
                    model="cube",
                    position=center,
                    scale=scale,
                    rotation=Vec3(0, 0, rotation_z),
                    color=tape_color,
                )
            )

        if abs(lateral_axis.x) > 0:
            side_scale_left = Vec3(tape_thickness, self.exit_portal_height, tape_depth)
            side_scale_right = Vec3(tape_thickness, self.exit_portal_height, tape_depth)
            top_scale = Vec3(portal_width + tape_thickness, top_thickness, tape_depth)
        else:
            side_scale_left = Vec3(tape_depth, self.exit_portal_height, tape_thickness)
            side_scale_right = Vec3(tape_depth, self.exit_portal_height, tape_thickness)
            top_scale = Vec3(tape_depth, top_thickness, portal_width + tape_thickness)

        add_tape_strip(
            face_center + lateral_axis * (portal_left + tape_rng.uniform(-0.02, 0.01)) + Vec3(0, self.exit_portal_height * 0.5, 0),
            side_scale_left,
            rotation_z=-1.2 + tape_rng.uniform(-0.4, 0.3),
        )
        add_tape_strip(
            face_center + lateral_axis * (portal_right + tape_rng.uniform(-0.01, 0.02)) + Vec3(0, self.exit_portal_height * 0.5, 0),
            side_scale_right,
            rotation_z=1.0 + tape_rng.uniform(-0.3, 0.4),
        )
        add_tape_strip(
            face_center + lateral_axis * tape_rng.uniform(-0.02, 0.02) + Vec3(0, portal_top_y, 0),
            top_scale,
            rotation_z=tape_rng.uniform(-0.35, 0.35),
        )

    def _build_entities(self) -> None:
        wall_height = self.wall_height
        surface_color = color.rgb(214, 205, 170)
        light_panel_color = color.rgb(255, 255, 240)

        for lz in range(self.grid_size):
            for lx in range(self.grid_size):
                gx, gz = self._global_from_local(lx, lz)
                x, z = self.world_from_cell((gx, gz))
                is_walkable = (gx, gz) in self.walkable_cells

                if is_walkable:
                    # Floor and ceiling only needed for walkable (visible) cells.
                    self.entities.append(
                        Entity(
                            model="cube",
                            position=Vec3(x, 0.0, z),
                            scale=Vec3(self.cell_size, 0.1, self.cell_size),
                            color=surface_color,
                            texture=self.floor_texture,
                            texture_scale=(2.2, 2.2),
                        )
                    )
                    self.entities.append(
                        Entity(
                            model="cube",
                            position=Vec3(x, wall_height, z),
                            scale=Vec3(self.cell_size, 0.1, self.cell_size),
                            color=surface_color,
                            texture=self.ceiling_texture,
                            texture_scale=(1.9, 1.9),
                        )
                    )
                    if (gx + gz) % 3 == 0:
                        self.entities.append(
                            Entity(
                                model="cube",
                                position=Vec3(x, wall_height - 0.07, z),
                                scale=Vec3(self.cell_size * 0.72, 0.02, self.cell_size * 0.28),
                                color=light_panel_color,
                            )
                        )
                else:
                    if (gx, gz) == self.exit_wall_cell:
                        self._append_exit_door_entities(x, z, wall_height)
                        continue
                    self.entities.append(
                        Entity(
                            model="cube",
                            position=Vec3(x, wall_height / 2.0, z),
                            scale=Vec3(self.cell_size, wall_height, self.cell_size),
                            color=surface_color,
                            texture=self.wall_texture,
                            texture_scale=(1.0, 1.4),
                            collider="box",
                        )
                    )

    def _generate_level(self) -> None:
        self.walkable_cells = self._generate_walkable_cells()
        self.start_cell = self._global_from_local(1, 1)
        self.exit_cell = self._pick_exit_anchor_cell(self.start_cell)
        self.exit_direction = self._exit_dir_from_anchor(self.exit_cell)
        self.exit_wall_cell = (
            self.exit_cell[0] + self.exit_direction[0],
            self.exit_cell[1] + self.exit_direction[1],
        )
        self._build_entities()

    def clear_all(self) -> None:
        for entity in self.entities:
            destroy(entity)
        self.entities.clear()
        self.walkable_cells.clear()

    def world_from_cell(self, cell: Cell) -> tuple[float, float]:
        gx, gz = cell
        return gx * self.cell_size, gz * self.cell_size

    def cell_from_world(self, position: Vec3) -> Cell:
        gx = round(position.x * self._inv_cell_size)
        gz = round(position.z * self._inv_cell_size)
        return gx, gz

    def is_walkable_cell(self, cell: Cell) -> bool:
        return cell in self.walkable_cells

    def walkable_neighbors(self, cell: Cell) -> Iterable[Cell]:
        x, z = cell
        for nx, nz in ((x + 1, z), (x - 1, z), (x, z + 1), (x, z - 1)):
            if (nx, nz) in self.walkable_cells:
                yield nx, nz

    def random_far_walkable_cell(self, from_cell: Cell, min_dist: int = 18) -> Cell:
        candidates = [cell for cell in self.walkable_cells if abs(cell[0] - from_cell[0]) + abs(cell[1] - from_cell[1]) >= min_dist]
        if not candidates:
            return from_cell
        rng = random.Random(f"{self.seed}|spawn_pick|{from_cell[0]}|{from_cell[1]}|{len(candidates)}")
        return rng.choice(candidates)

    def player_reached_exit(self, player_position: Vec3) -> bool:
        player_cell = self.cell_from_world(player_position)
        if player_cell not in (self.exit_cell, self.exit_wall_cell):
            return False

        exit_wx, exit_wz = self.world_from_cell(self.exit_cell)
        return touches_exit_portal(
            player_x=player_position.x,
            player_z=player_position.z,
            exit_x=exit_wx,
            exit_z=exit_wz,
            exit_direction=self.exit_direction,
            cell_size=self.cell_size,
            collider_radius=0.45,
            portal_width_ratio=self.exit_portal_width_ratio,
        )

    def has_clear_line(self, a: Cell, b: Cell) -> bool:
        ax, az = a
        bx, bz = b
        dx = bx - ax
        dz = bz - az
        steps = max(abs(dx), abs(dz))
        if steps == 0:
            return True
        # Anything farther than 30 cells is completely hidden by fog – treat as blocked.
        if steps > 30:
            return False
        # Check only intermediate cells (skip the two endpoints which may be wall-adjacent).
        for i in range(1, steps):
            sx = ax + round(dx * i / steps)
            sz = az + round(dz * i / steps)
            if (sx, sz) not in self.walkable_cells:
                return False
        return True

