from __future__ import annotations

import math
import random
from collections import deque
from typing import Iterable, List, Set, Tuple

from panda3d.core import PNMImage, Texture as PandaTexture
from ursina import Entity, Mesh, Texture, Vec3, color, destroy

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
        self.monster_start_cell: Cell | None = None
        self.player_spawn_rotation_y: float = 0.0
        # Level 7 ("The Pyramid") special-level state: a giant static monster stands
        # in front of a distant pyramid, and the exit door on the pyramid's front
        # face only appears once the level's audio cue has finished (see main.py).
        self.pyramid_center_cell: Cell | None = None
        self.pyramid_monster_cell: Cell | None = None
        self.door_unlocked: bool = False
        self._pyramid_radius: int = 0
        self._pyramid_base_height: float = 0.0
        self._pyramid_front_wall_entity: Entity | None = None
        self.wall_height = 3.0
        self.exit_portal_height = 2.0
        self.exit_portal_width_ratio = 1.0 / 3.0
        self.wall_surface_color = color.rgb(240, 231, 196)
        self.floor_surface_color = color.rgb(227, 214, 174)
        self.ceiling_surface_color = color.rgb(240, 231, 196)
        self.lamp_positions: List[Vec3] = []
        self.lamp_cells: List[Cell] = []
        # Per-cell entity registries so lighting (or anything else) can look up the
        # exact structural geometry that borders a given cell, and can walk the real
        # walkable-cell graph to find geometry that is actually *reachable* from a
        # point, rather than just "nearby in world-space" (which would ignore walls).
        self._floor_entities: dict[Cell, Entity] = {}
        self._ceiling_entities: dict[Cell, Entity] = {}
        self._wall_entities: dict[Cell, Entity] = {}

        self._inv_cell_size: float = 1.0 / cell_size

        self.wall_texture = self._build_wall_texture()
        self.floor_texture = self._build_floor_texture()
        self.ceiling_texture = self._build_ceiling_texture()
        self.door_texture = self._build_door_texture()

        self._generate_level()

    def _maze_cells_per_side(self, level: int) -> int:
        #if self.test:
        #    return 9
        #size = 17 + (level - 1) * 4
        #if size % 2 == 0:
        #    size += 1
        #return min(size, 61)
        if self.test:
            return 9
        elif self.level == 5:
            return 35
        elif self.level == 7:
            return 101
        elif self.level == 9:
            return 45
        else:
            return 17

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
        if self.level == 5:
            walkable: Set[Cell] = set()
            for lz in range(1, self.grid_size - 1):
                walkable.add(self._global_from_local(1, lz))
            self.start_cell = self._global_from_local(1, 4)
            self.monster_start_cell = self._global_from_local(1, 1)
            self.player_spawn_rotation_y = 180.0
            self.exit_cell = self._global_from_local(1, self.grid_size - 2)
            self.exit_direction = (0, 1)
            self.exit_wall_cell = (self.exit_cell[0], self.exit_cell[1] + 1)
            return walkable

        if self.level == 7:
            return self._generate_level7_layout()

        if self.level == 9:
            return self._generate_level9_layout()

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

    def _generate_level7_layout(self) -> Set[Cell]:
        """Open-field layout for level 7 ("The Pyramid"): a single giant walkable
        plane (no interior maze walls) with a solid pyramid structure sitting in
        the distance. The pyramid's front face starts out as a plain solid wall
        and only becomes an exit once `unlock_pyramid_door()` is called."""
        half = self.half_grid
        center_local = self.grid_size // 2
        radius = max(1, min(12, half - 12))
        front_offset = radius + 8  # the giant monster stands this many cells south of the front face
        start_offset = max(front_offset + 2, min(half - 2, front_offset + 25))

        pyramid_local = (center_local, center_local)
        front_face_local = (center_local, center_local - radius)
        monster_local = (center_local, center_local - front_offset)
        start_local = (center_local, center_local - start_offset)

        walkable: Set[Cell] = set()
        for lz in range(1, self.grid_size - 1):
            for lx in range(1, self.grid_size - 1):
                walkable.add(self._global_from_local(lx, lz))

        self.pyramid_center_cell = self._global_from_local(*pyramid_local)
        for dz in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                walkable.discard((self.pyramid_center_cell[0] + dx, self.pyramid_center_cell[1] + dz))

        self._pyramid_radius = radius
        self.pyramid_monster_cell = self._global_from_local(*monster_local)
        self.start_cell = self._global_from_local(*start_local)
        self.monster_start_cell = None
        self.player_spawn_rotation_y = 0.0
        self.exit_direction = (0, 1)
        self.exit_wall_cell = self._global_from_local(*front_face_local)
        self.exit_cell = (self.exit_wall_cell[0], self.exit_wall_cell[1] - 1)
        self.door_unlocked = False
        return walkable

    def _generate_level9_layout(self) -> Set[Cell]:
        """Straight hallway layout for level 9 ("Give the monster a hug"): a single
        corridor with a friendly, motionless monster waiting at the far end and
        no exit door -- the level is completed by walking up and touching it
        (see `LiminalVibesGame._update_level9` in main.py)."""
        walkable: Set[Cell] = set()
        for lz in range(1, self.grid_size - 1):
            walkable.add(self._global_from_local(1, lz))

        self.start_cell = self._global_from_local(1, 1)
        self.monster_start_cell = self._global_from_local(1, self.grid_size - 2)
        self.player_spawn_rotation_y = 0.0
        self.exit_direction = (0, 1)
        # No portal in this level -- point the exit cells at sentinel coordinates
        # far outside the grid so `player_reached_exit` never matches, and so the
        # generic wall builder never paints an exit-door texture on the far wall.
        self.exit_cell = (10 ** 6, 10 ** 6)
        self.exit_wall_cell = (10 ** 6, 10 ** 6 + 1)
        self.door_unlocked = False
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

    def _append_exit_door_entities(self, x: float, z: float, wall_height: float, cell: Cell) -> None:
        wall_entity = Entity(
            model="cube",
            position=Vec3(x, wall_height * 0.5, z),
            scale=Vec3(self.cell_size, wall_height, self.cell_size),
            color=self.wall_surface_color,
            texture=self.wall_texture,
            texture_scale=(1.0, 1.4),
            collider="box",
        )
        self.entities.append(wall_entity)
        self._wall_entities[cell] = wall_entity

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

    def _build_pyramid_front_wall(self, x: float, z: float, height: float, y_base: float, cell: Cell) -> None:
        """Plain solid wall segment covering the pyramid's front face until the
        exit door is unlocked (see `unlock_pyramid_door`)."""
        wall_entity = Entity(
            model="cube",
            position=Vec3(x, y_base + height * 0.5, z),
            scale=Vec3(self.cell_size, height, self.cell_size),
            color=self.wall_surface_color,
            texture=self.wall_texture,
            texture_scale=(1.0, height / self.wall_height * 1.4),
        )
        self.entities.append(wall_entity)
        self._wall_entities[cell] = wall_entity
        self._pyramid_front_wall_entity = wall_entity

    def _add_cube_to_mesh(
        self,
        vertices: list[tuple[float, float, float]],
        triangles: list[int],
        uvs: list[tuple[float, float]],
        normals: list[tuple[float, float, float]],
        center_x: float,
        center_y: float,
        center_z: float,
        scale_x: float,
        scale_y: float,
        scale_z: float,
    ) -> None:
        hx = scale_x * 0.5
        hy = scale_y * 0.5
        hz = scale_z * 0.5
        face_defs = (
            ((0.0, 0.0, -1.0), ((-hx, -hy, -hz), (hx, -hy, -hz), (hx, hy, -hz), (-hx, hy, -hz))),
            ((0.0, 0.0, 1.0), ((-hx, -hy, hz), (-hx, hy, hz), (hx, hy, hz), (hx, -hy, hz))),
            ((-1.0, 0.0, 0.0), ((-hx, -hy, -hz), (-hx, hy, -hz), (-hx, hy, hz), (-hx, -hy, hz))),
            ((1.0, 0.0, 0.0), ((hx, -hy, -hz), (hx, -hy, hz), (hx, hy, hz), (hx, hy, -hz))),
            ((0.0, 1.0, 0.0), ((-hx, hy, -hz), (hx, hy, -hz), (hx, hy, hz), (-hx, hy, hz))),
            ((0.0, -1.0, 0.0), ((-hx, -hy, -hz), (-hx, -hy, hz), (hx, -hy, hz), (hx, -hy, -hz))),
        )

        for normal, face_vertices in face_defs:
            face_start = len(vertices)
            for dx, dy, dz in face_vertices:
                vertices.append((center_x + dx, center_y + dy, center_z + dz))
                normals.append(normal)
            uvs.extend(((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)))
            triangles.extend(
                (
                    face_start,
                    face_start + 1,
                    face_start + 2,
                    face_start,
                    face_start + 2,
                    face_start + 3,
                )
            )

    def _build_pyramid_tier(self, radius: float, y_base: float, block_height: float, track_walls: bool) -> None:
        """Build one terrace of the ziggurat from batched cube geometry.

        The blocks stay the same size as normal walls, but the terrace edges are
        offset by half a cell between layers, which makes the pyramid feel
        tighter without multiplying draw calls."""
        assert self.pyramid_center_cell is not None
        spacing = 0.5
        steps = int(round((radius * 2) / spacing))
        offsets = [(-radius + index * spacing) for index in range(steps + 1)]
        vertices: list[tuple[float, float, float]] = []
        triangles: list[int] = []
        uvs: list[tuple[float, float]] = []
        normals: list[tuple[float, float, float]] = []
        front_cell = self.exit_wall_cell if track_walls and math.isclose(radius, float(self._pyramid_radius)) else None

        for z_index, z_offset in enumerate(offsets):
            for x_index, x_offset in enumerate(offsets):
                if front_cell is not None and math.isclose(x_offset, 0.0) and math.isclose(z_offset, -radius):
                    x, z = self.world_from_cell(front_cell)
                    self._build_pyramid_front_wall(x, z, block_height, y_base, front_cell)
                    continue

                center_x, center_z = self.world_from_cell(
                    (self.pyramid_center_cell[0] + x_offset, self.pyramid_center_cell[1] + z_offset)
                )
                self._add_cube_to_mesh(
                    vertices,
                    triangles,
                    uvs,
                    normals,
                    center_x,
                    y_base + block_height * 0.5,
                    center_z,
                    self.cell_size,
                    block_height,
                    self.cell_size,
                )

        mesh = Mesh(vertices=vertices, triangles=triangles, uvs=uvs, normals=normals, mode="triangle")
        self.entities.append(
            Entity(
                model=mesh,
                color=self.wall_surface_color,
                texture=self.wall_texture,
            )
        )

    def _build_pyramid(self) -> None:
        assert self.pyramid_center_cell is not None
        radius = max(1, self._pyramid_radius or 12)

        # Stepped ("ziggurat") terraces, each narrower than the one below it, all
        # built from identically-sized blocks no taller than the door (matching
        # the game's normal wall height) rather than a handful of huge slabs.
        block_height = self.wall_height
        self._pyramid_base_height = block_height
        step = 0.5
        radii: List[int] = []
        r = float(radius)
        while r >= 1.0:
            radii.append(r)
            r -= step
        if not radii or not math.isclose(radii[-1], 1.0):
            radii.append(1.0)

        y_cursor = 0.0
        for index, layer_radius in enumerate(radii):
            self._build_pyramid_tier(layer_radius, y_cursor, block_height, track_walls=(index == 0))
            y_cursor += block_height

        apex_height = block_height
        apex_x, apex_z = self.world_from_cell(self.pyramid_center_cell)
        self.entities.append(
            Entity(
                model="cube",
                position=Vec3(apex_x, y_cursor + apex_height * 0.5, apex_z),
                scale=Vec3(self.cell_size, apex_height, self.cell_size),
                color=self.wall_surface_color,
                texture=self.wall_texture,
            )
        )

    def _build_entities_level7(self) -> None:
        """Open field: floor only (no ceiling, no interior walls) extending into
        the fog, plus a distant solid pyramid. Actual scene lighting for this
        level is set up by the caller (see `LiminalVibesGame._load_level`),
        mirroring how lamp point lights are owned outside of `MazeManager`."""
        total_extent = (self.grid_size - 1) * self.cell_size
        floor_entity = Entity(
            model="cube",
            position=Vec3(0.0, 0.0, 0.0),
            scale=Vec3(total_extent, 0.1, total_extent),
            color=self.floor_surface_color,
            texture=self.floor_texture,
            texture_scale=(total_extent / self.cell_size * 2.2, total_extent / self.cell_size * 2.2),
        )
        self.entities.append(floor_entity)

        self._build_pyramid()

    def unlock_pyramid_door(self) -> None:
        """Reveal the exit door on the pyramid's front face. Called once the
        level-7 einkvan audio sequence finishes playing."""
        if self.level != 7 or self.door_unlocked:
            return
        self.door_unlocked = True

        if self._pyramid_front_wall_entity is not None:
            if self._pyramid_front_wall_entity in self.entities:
                self.entities.remove(self._pyramid_front_wall_entity)
            destroy(self._pyramid_front_wall_entity)
            self._pyramid_front_wall_entity = None
            self._wall_entities.pop(self.exit_wall_cell, None)

        x, z = self.world_from_cell(self.exit_wall_cell)
        self._append_exit_door_entities(x, z, self._pyramid_base_height or self.wall_height, self.exit_wall_cell)

    def _build_entities(self) -> None:
        if self.level == 7:
            self._build_entities_level7()
            return

        wall_height = self.wall_height
        wall_color = self.wall_surface_color
        floor_color = self.floor_surface_color
        ceiling_color = self.ceiling_surface_color
        light_panel_color = color.rgb(255, 255, 240)

        for lz in range(self.grid_size):
            for lx in range(self.grid_size):
                gx, gz = self._global_from_local(lx, lz)
                x, z = self.world_from_cell((gx, gz))
                is_walkable = (gx, gz) in self.walkable_cells

                if is_walkable:
                    # Floor and ceiling only needed for walkable (visible) cells.
                    floor_entity = Entity(
                        model="cube",
                        position=Vec3(x, 0.0, z),
                        scale=Vec3(self.cell_size, 0.1, self.cell_size),
                        color=floor_color,
                        texture=self.floor_texture,
                        texture_scale=(2.2, 2.2),
                    )
                    self.entities.append(floor_entity)
                    self._floor_entities[(gx, gz)] = floor_entity

                    ceiling_entity = Entity(
                        model="cube",
                        position=Vec3(x, wall_height, z),
                        scale=Vec3(self.cell_size, 0.1, self.cell_size),
                        color=ceiling_color,
                        texture=self.ceiling_texture,
                        texture_scale=(1.9, 1.9),
                    )
                    self.entities.append(ceiling_entity)
                    self._ceiling_entities[(gx, gz)] = ceiling_entity

                    if (gx + gz) % 3 == 0:
                        lamp_pos = Vec3(x, wall_height - 0.07, z)
                        self.entities.append(
                            Entity(
                                model="cube",
                                position=lamp_pos,
                                scale=Vec3(self.cell_size * 0.72, 0.02, self.cell_size * 0.28),
                                color=light_panel_color,
                            )
                        )
                        self.lamp_positions.append(lamp_pos)
                        self.lamp_cells.append((gx, gz))
                else:
                    if (gx, gz) == self.exit_wall_cell:
                        self._append_exit_door_entities(x, z, wall_height, (gx, gz))
                        continue
                    wall_entity = Entity(
                        model="cube",
                        position=Vec3(x, wall_height / 2.0, z),
                        scale=Vec3(self.cell_size, wall_height, self.cell_size),
                        color=wall_color,
                        texture=self.wall_texture,
                        texture_scale=(1.0, 1.4),
                        collider="box",
                    )
                    self.entities.append(wall_entity)
                    self._wall_entities[(gx, gz)] = wall_entity

    def _generate_level(self) -> None:
        self.walkable_cells = self._generate_walkable_cells()
        if self.level not in (5, 7, 9):
            self.start_cell = self._global_from_local(1, 1)
            self.monster_start_cell = None
            self.player_spawn_rotation_y = 0.0
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
        self.lamp_positions.clear()
        self.lamp_cells.clear()
        self._floor_entities.clear()
        self._ceiling_entities.clear()
        self._wall_entities.clear()

    def entities_near_cell(self, cell: Cell, hops: int = 2) -> List[Entity]:
        """Collect floor/ceiling/wall entities reachable from `cell` by walking the
        real walkable-cell graph up to `hops` steps.

        This intentionally uses graph connectivity (via `walkable_neighbors`) rather
        than raw Euclidean/world-space distance. Two corridors can be only one wall
        thickness apart in world space yet be structurally unconnected; a naive
        distance-based lookup would treat them as "nearby" and light bleed-through
        would occur. Walking the walkable graph guarantees a lamp can only affect
        geometry that is actually part of its own connected corridor segment.
        """
        visited: Set[Cell] = {cell}
        frontier: List[Cell] = [cell]
        for _ in range(max(0, hops)):
            next_frontier: List[Cell] = []
            for c in frontier:
                for nb in self.walkable_neighbors(c):
                    if nb not in visited:
                        visited.add(nb)
                        next_frontier.append(nb)
            frontier = next_frontier
            if not frontier:
                break

        collected: List[Entity] = []
        for c in visited:
            floor_entity = self._floor_entities.get(c)
            if floor_entity is not None:
                collected.append(floor_entity)
            ceiling_entity = self._ceiling_entities.get(c)
            if ceiling_entity is not None:
                collected.append(ceiling_entity)

            cx, cz = c
            for nx, nz in ((cx + 1, cz), (cx - 1, cz), (cx, cz + 1), (cx, cz - 1)):
                wall_entity = self._wall_entities.get((nx, nz))
                if wall_entity is not None:
                    collected.append(wall_entity)

        return collected

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
        if self.level == 7 and not self.door_unlocked:
            return False

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
