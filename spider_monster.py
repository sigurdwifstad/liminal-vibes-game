from __future__ import annotations

import math
import random
from typing import List

from ursina import Entity, Vec3, color, destroy, time

from audio import get_audio_manager
from maze import Cell, MazeManager

# Precomputed constant – half-angle of the player's visible cone (52°).
_VIS_CONE_COS: float = math.cos(math.radians(52.0))


class SpiderController(Entity):
    """A spider monster that drains player stamina and disappears instead of killing."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.spawn_delay_seconds = 40.0
        self.spawned = False
        self.spawned_at = 0.0
        self.visible = False
        self.enabled = False
        self.path_cells: List[Cell] = []
        self.path_refresh_timer = 0.0
        self.path_refresh_interval = 0.45
        self.path_refresh_interval_near = 0.38
        self.path_refresh_interval_mid = 0.60
        self.path_refresh_interval_far = 0.82
        self.catch_distance = 0.8
        self.current_speed = 6.0
        self.would_catch_player = False
        self.walk_anim_phase = 0.0
        self.visual_parts: List[Entity] = []
        self.legs: List[Entity] = []
        self._leg_base_z_rotations: List[float] = []
        self._rng = random.Random(0)
        self.teleport_timer = 3.0
        self.teleport_cooldown = 3.2
        self.teleport_out_of_sight_chance = 0.38
        self._was_visible_to_player = False
        self._draining = False
        self._drain_complete = False
        self._drain_delay = 0.0
        self.audio = get_audio_manager()
        self._build_visual()

    def _build_visual(self) -> None:
        """Create spider: abdomen + cephalothorax + head spheres, red eyes, white fangs, 8 animated legs."""
        # Abdomen – large rear sphere
        abdomen = Entity(parent=self, model="sphere",
                         position=Vec3(0, 0.46, -0.32),
                         scale=Vec3(0.64, 0.60, 0.70),
                         color=color.black)
        self.visual_parts.append(abdomen)

        # Cephalothorax – smaller front body sphere
        thorax = Entity(parent=self, model="sphere",
                        position=Vec3(0, 0.46, 0.16),
                        scale=Vec3(0.44, 0.40, 0.46),
                        color=color.black)
        self.visual_parts.append(thorax)

        # Head – small sphere at the very front
        head = Entity(parent=self, model="sphere",
                      position=Vec3(0, 0.60, 0.43),
                      scale=Vec3(0.27, 0.25, 0.26),
                      color=color.black)
        self.visual_parts.append(head)

        # Red glowing eyes
        left_eye = Entity(parent=head, model="sphere",
                          position=Vec3(-0.28, 0.12, 0.50),
                          scale=Vec3(0.30, 0.28, 0.20),
                          color=color.rgb(230, 0, 0))
        right_eye = Entity(parent=head, model="sphere",
                           position=Vec3(0.28, 0.12, 0.50),
                           scale=Vec3(0.30, 0.28, 0.20),
                           color=color.rgb(230, 0, 0))
        self.visual_parts.extend([left_eye, right_eye])

        # White fangs
        left_fang = Entity(parent=head, model="cube",
                           position=Vec3(-0.18, -0.44, 0.50),
                           scale=Vec3(0.11, 0.28, 0.09),
                           color=color.white)
        right_fang = Entity(parent=head, model="cube",
                            position=Vec3(0.18, -0.44, 0.50),
                            scale=Vec3(0.11, 0.28, 0.09),
                            color=color.white)
        self.visual_parts.extend([left_fang, right_fang])

        # 8 legs (4 pairs), each made from a single long segment.
        # Each tuple: (abs_x, y, z, hip_z_rotation_degrees)
        leg_data = [
            (0.24, 0.54, 0.24, -30),   # front pair
            (0.24, 0.53, 0.10, -34),   # second pair
            (0.23, 0.52, -0.08, -34),  # third pair
            (0.23, 0.52, -0.24, -30),  # rear pair
        ]
        leg_thickness = 0.07
        upper_length = 0.96
        upper_half = upper_length * 0.5

        for (x, y, z, rz) in leg_data:
            # Hip pivots anchor to torso; leg segments hang down from each pivot.
            ll_hip = Entity(parent=self, position=Vec3(-x, y, z), rotation=Vec3(0, 0, -rz))
            rl_hip = Entity(parent=self, position=Vec3(x, y, z), rotation=Vec3(0, 0, rz))

            ll = Entity(parent=ll_hip, model="cube",
                        position=Vec3(0, -upper_half, 0),
                        scale=Vec3(leg_thickness, upper_length, leg_thickness),
                        color=color.black)
            rl = Entity(parent=rl_hip, model="cube",
                        position=Vec3(0, -upper_half, 0),
                        scale=Vec3(leg_thickness, upper_length, leg_thickness),
                        color=color.black)

            self.legs.extend([ll_hip, rl_hip])
            self._leg_base_z_rotations.extend([-rz, rz])
            self.visual_parts.extend([ll, rl])

    def _set_leg_pose(self, phase: float) -> None:
        """Animate single-segment legs at the hip joints."""
        for i, leg in enumerate(self.legs):
            pair_index = i // 2          # 0-3 for the four pairs
            side = i % 2                 # 0=left, 1=right
            leg_phase = phase + pair_index * (math.pi / 2.0) + side * math.pi
            swing_x = math.sin(leg_phase) * 32.0
            leg.rotation = Vec3(swing_x, 0, self._leg_base_z_rotations[i])

    def reset(self) -> None:
        self.spawned = False
        self.visible = False
        self.enabled = False
        self.audio.stop_spider_walking_loop()
        self.path_cells.clear()
        # Offset spider path refresh timing so both AI do not spike on the same frame.
        self.path_refresh_timer = self.path_refresh_interval * 0.75
        self.position = Vec3(0, -1000, 0)
        self.current_speed = 0.0
        self.would_catch_player = False
        self.walk_anim_phase = 0.0
        self.teleport_timer = self.teleport_cooldown
        self._was_visible_to_player = False
        self._draining = False
        self._drain_complete = False
        self._drain_delay = 0.0
        self._set_leg_pose(0.0)

    def _is_visible_to_player(self, maze: MazeManager, player_position: Vec3, player_forward: Vec3 | None, target_position: Vec3) -> bool:
        """Check if spider is visible to player."""
        player_cell = maze.cell_from_world(player_position)
        target_cell = maze.cell_from_world(target_position)
        if not maze.has_clear_line(player_cell, target_cell):
            return False

        forward = Vec3(0, 0, 1)
        if player_forward is not None and player_forward.length() > 0.001:
            forward = Vec3(player_forward.x, 0, player_forward.z).normalized()

        to_target = Vec3(target_position.x - player_position.x, 0, target_position.z - player_position.z)
        if to_target.length() < 0.001:
            return True

        to_target_n = to_target.normalized()
        return forward.dot(to_target_n) >= _VIS_CONE_COS

    def _is_in_forward_hemisphere(self, player_position: Vec3, player_forward: Vec3 | None, target_position: Vec3) -> bool:
        """Check if target is in front of the player (but not necessarily visible)."""
        forward = Vec3(0, 0, 1)
        if player_forward is not None and player_forward.length() > 0.001:
            forward = Vec3(player_forward.x, 0, player_forward.z).normalized()

        to_target = Vec3(target_position.x - player_position.x, 0, target_position.z - player_position.z)
        if to_target.length() < 0.001:
            return True

        return forward.dot(to_target.normalized()) > 0.0

    def _pick_hidden_cell(self, maze: MazeManager, player_position: Vec3, player_forward: Vec3 | None, min_dist: int, max_dist: int) -> Cell | None:
        """Pick a spawn cell hidden from player and only in front of them."""
        player_cell = maze.cell_from_world(player_position)
        hidden: List[Cell] = []
        for cell in maze.walkable_cells:
            dist = abs(cell[0] - player_cell[0]) + abs(cell[1] - player_cell[1])
            if dist < min_dist or dist > max_dist:
                continue
            wx, wz = maze.world_from_cell(cell)
            target_position = Vec3(wx, 0, wz)
            if self._is_in_forward_hemisphere(player_position, player_forward, target_position) and not self._is_visible_to_player(maze, player_position, player_forward, target_position):
                hidden.append(cell)

        if hidden:
            return self._rng.choice(hidden)

        # If no forward-hidden cells exist, fall back to any hidden cell so the spider can still spawn.
        for cell in maze.walkable_cells:
            wx, wz = maze.world_from_cell(cell)
            target_position = Vec3(wx, 0, wz)
            if not self._is_visible_to_player(maze, player_position, player_forward, target_position):
                hidden.append(cell)
        if hidden:
            return self._rng.choice(hidden)
        return None

    def cleanup(self) -> None:
        self.audio.stop_spider_walking_loop()
        for part in self.visual_parts:
            destroy(part)

    def _cell_to_waypoint(self, maze: MazeManager, cell: Cell) -> Vec3:
        wx, wz = maze.world_from_cell(cell)
        return Vec3(wx, 0.0, wz)

    def _astar(self, maze: MazeManager, start: Cell, goal: Cell, max_nodes: int = 1200) -> List[Cell]:
        """Simple A* pathfinding."""
        import heapq

        if start == goal:
            return [start]

        open_heap: List[tuple[float, Cell]] = []
        heapq.heappush(open_heap, (0.0, start))
        came_from: dict[Cell, Cell | None] = {start: None}
        g_score: dict[Cell, float] = {start: 0.0}
        visited = 0

        def heuristic(a: Cell, b: Cell) -> float:
            return abs(a[0] - b[0]) + abs(a[1] - b[1])

        while open_heap and visited < max_nodes:
            _, current = heapq.heappop(open_heap)
            visited += 1
            if current == goal:
                out: List[Cell] = [current]
                while came_from[current] is not None:
                    current = came_from[current]
                    out.append(current)
                out.reverse()
                return out

            for nb in maze.walkable_neighbors(current):
                tentative = g_score[current] + 1.0
                if nb not in g_score or tentative < g_score[nb]:
                    came_from[nb] = current
                    g_score[nb] = tentative
                    f = tentative + heuristic(nb, goal)
                    heapq.heappush(open_heap, (f, nb))

        return [start]

    def _closest_walkable_to_target(self, maze: MazeManager, target: Cell, avoid: Cell | None = None) -> Cell:
        best_cell = target
        best_dist = float("inf")
        fallback: Cell | None = None
        for cell in maze.walkable_cells:
            dist = abs(cell[0] - target[0]) + abs(cell[1] - target[1])
            if avoid is not None and cell == avoid:
                if fallback is None or dist < abs(fallback[0] - target[0]) + abs(fallback[1] - target[1]):
                    fallback = cell
                continue
            if dist < best_dist:
                best_dist = dist
                best_cell = cell

        if best_dist == float("inf") and fallback is not None:
            return fallback
        return best_cell

    def update_spider(
        self,
        maze: MazeManager,
        player_position: Vec3,
        run_elapsed: float,
        player_forward: Vec3 | None = None,
        level: int = 1,
    ) -> bool:
        """
        Update spider behavior. Returns True if spider caught the player (drained stamina).
        """
        # Only spawn at level 3+ (unless in test mode, indicated by spawn_delay_seconds = 0)
        if level < 3 and self.spawn_delay_seconds > 0:
            self.audio.stop_spider_walking_loop()
            return False

        if not self.spawned and run_elapsed >= self.spawn_delay_seconds:
            self._rng.seed(maze.seed + int(run_elapsed * 1000.0))
            spawn_cell = self._pick_hidden_cell(maze, player_position, player_forward, min_dist=8, max_dist=32)
            if spawn_cell is None:
                return False
            sx, sz = maze.world_from_cell(spawn_cell)
            self.position = Vec3(sx, 0.0, sz)
            self.spawned = True
            self.visible = True
            self.enabled = True
            self.spawned_at = run_elapsed
            self.teleport_timer = self.teleport_cooldown

        if not self.spawned:
            self.audio.stop_spider_walking_loop()
            return False

        # If already drained stamina, disappear
        if self._drain_complete:
            self.audio.stop_spider_walking_loop()
            return False

        player_flat = Vec3(player_position.x, 0.0, player_position.z)
        distance_to_player = (player_flat - self.position).length()

        self.would_catch_player = distance_to_player <= self.catch_distance
        if self.would_catch_player and not self._draining:
            self.audio.play_spider_attack(run_elapsed)
            self.audio.stop_spider_walking_loop()
            self._draining = True
            self._drain_delay = 0.15
            return True

        # Stay visible for a brief moment after starting drain so main.py can process it
        if self._draining:
            self.audio.stop_spider_walking_loop()
            self._drain_delay -= time.dt
            if self._drain_delay <= 0.0:
                self._drain_complete = True
                self.enabled = False
                self.visible = False
                self.spawned = False
                self.audio.stop_spider_walking_loop()
                return False
            return True

        is_visible = self._is_visible_to_player(maze, player_position, player_forward, self.position)
        self._was_visible_to_player = is_visible
        if is_visible:
            self.audio.play_spider_walking_loop()
        else:
            self.audio.stop_spider_walking_loop()

        if not is_visible:
            self.teleport_timer -= time.dt
            if self.teleport_timer <= 0.0 and self._rng.random() < self.teleport_out_of_sight_chance:
                teleport_cell = self._pick_hidden_cell(maze, player_position, player_forward, min_dist=7, max_dist=26)
                if teleport_cell is not None:
                    tx, tz = maze.world_from_cell(teleport_cell)
                    self.position = Vec3(tx, 0.0, tz)
                    self.path_cells.clear()
            if self.teleport_timer <= 0.0:
                self.teleport_timer = self.teleport_cooldown + self._rng.uniform(-0.8, 1.0)
        else:
            self.teleport_timer = min(self.teleport_cooldown, self.teleport_timer + time.dt * 0.4)

        self.path_refresh_timer -= time.dt
        if self.path_refresh_timer <= 0.0:
            spider_cell = maze.cell_from_world(self.position)
            player_cell = maze.cell_from_world(player_position)
            self.path_cells = self._astar(maze, spider_cell, player_cell)
            cell_gap = abs(spider_cell[0] - player_cell[0]) + abs(spider_cell[1] - player_cell[1])
            if cell_gap >= 18:
                self.path_refresh_timer = self.path_refresh_interval_far
            elif cell_gap >= 10:
                self.path_refresh_timer = self.path_refresh_interval_mid
            else:
                self.path_refresh_timer = self.path_refresh_interval_near

        if len(self.path_cells) >= 2:
            next_waypoint = self._cell_to_waypoint(maze, self.path_cells[1])
        else:
            next_waypoint = player_flat

        to_target = next_waypoint - self.position
        if to_target.length() > 0.03:
            self.current_speed = 6.0
            step = min(self.current_speed * time.dt, to_target.length())
            direction = to_target.normalized()
            self.position += direction * step
            yaw = math.degrees(math.atan2(direction.x, direction.z))
            self.rotation_y = yaw
            self.walk_anim_phase += time.dt * (2.8 + self.current_speed * 1.25)
            self._set_leg_pose(self.walk_anim_phase)
        else:
            self.current_speed = 0.0
            self._set_leg_pose(0.0)

        return False






















