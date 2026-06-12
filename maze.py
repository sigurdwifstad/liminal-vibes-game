from __future__ import annotations

import random
from collections import deque
from typing import Iterable, List, Set, Tuple

from panda3d.core import PNMImage, Texture as PandaTexture
from ursina import Entity, Texture, Vec3, color, destroy
from ursina.shaders import lit_with_shadows_shader

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

        panda_tex = PandaTexture("liminal_wall")
        panda_tex.load(img)
        texture = Texture(panda_tex)
        texture.filtering = "bilinear"
        return texture

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
        img = PNMImage(size, size)

        # White base for the door
        base_r, base_g, base_b = 240 / 255.0, 240 / 255.0, 238 / 255.0

        # Fill entire image with near-white
        for y in range(size):
            for x in range(size):
                # Very subtle grain for realism
                grain = random.Random(f"{self.seed}|door_texture|{x}|{y}").uniform(-0.015, 0.015)
                color_val = base_r + grain
                img.setXel(x, y, color_val, color_val, color_val)

        # Draw a grey/dark circular doorknob in the right-middle area
        center_x = int(size * 0.75)  # Right side
        center_y = size // 2  # Middle height
        knob_radius = 6

        knob_r, knob_g, knob_b = 100 / 255.0, 100 / 255.0, 100 / 255.0

        for y in range(max(0, center_y - knob_radius), min(size, center_y + knob_radius + 1)):
            for x in range(max(0, center_x - knob_radius), min(size, center_x + knob_radius + 1)):
                dx = x - center_x
                dy = y - center_y
                dist = (dx * dx + dy * dy) ** 0.5

                if dist <= knob_radius:
                    # Gradient for 3D effect
                    shade = (knob_radius - dist) / knob_radius * 0.3
                    img.setXel(x, y, knob_r - shade, knob_g - shade, knob_b - shade)

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
        # Create a door tile with custom door texture
        # Door is rectangular (tall, not a full wall patch)
        self.entities.append(
            Entity(
                model="cube",
                position=Vec3(x, wall_height * 0.5, z),
                scale=Vec3(self.cell_size * 0.5, wall_height * 0.9, self.cell_size * 0.1),
                color=color.rgb(255, 255, 255),
                texture=self.door_texture,
                texture_scale=(1.0, 1.2),
                collider="box",
                shader=lit_with_shadows_shader,
            )
        )

    def _build_entities(self) -> None:
        wall_height = 3.0
        surface_color = color.rgb(214, 205, 170)

        for lz in range(self.grid_size):
            for lx in range(self.grid_size):
                gx, gz = self._global_from_local(lx, lz)
                x, z = self.world_from_cell((gx, gz))

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

                if (gx, gz) in self.walkable_cells:
                    if (gx + gz) % 3 == 0:
                        self.entities.append(
                            Entity(
                                model="cube",
                                position=Vec3(x, wall_height - 0.07, z),
                                scale=Vec3(self.cell_size * 0.72, 0.02, self.cell_size * 0.28),
                                color=color.rgb(255, 255, 240),
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
                            shader=lit_with_shadows_shader,
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
        gx = round(position.x / self.cell_size)
        gz = round(position.z / self.cell_size)
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
        # Check if player is at the exit location
        # The exit door is placed at exit_wall_cell

        # Method 1: Check if player is in or very close to exit_cell
        player_cell = self.cell_from_world(player_position)
        if player_cell == self.exit_cell:
            return True

        # Check if player is in a neighboring cell to exit_cell
        ex, ez = self.exit_cell
        if abs(player_cell[0] - ex) <= 1 and abs(player_cell[1] - ez) <= 1:
            # Player is in a neighboring cell, check world distance to door
            door_center_wx, door_center_wz = self.world_from_cell(self.exit_cell)
            dx = player_position.x - door_center_wx
            dz = player_position.z - door_center_wz
            distance = (dx * dx + dz * dz) ** 0.5

            # If within 2.5 units (more than half a cell), player has reached the exit
            if distance < 2.5:
                return True

        return False

    def has_clear_line(self, a: Cell, b: Cell) -> bool:
        ax, az = a
        bx, bz = b
        steps = max(abs(bx - ax), abs(bz - az))
        if steps == 0:
            return True

        for i in range(steps + 1):
            t = i / steps
            sx = round(ax + (bx - ax) * t)
            sz = round(az + (bz - az) * t)
            if (sx, sz) != a and (sx, sz) != b and (sx, sz) not in self.walkable_cells:
                return False
        return True

