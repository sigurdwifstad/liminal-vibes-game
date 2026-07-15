from __future__ import annotations

import heapq
import math
import random
from typing import Dict, List, Optional

from ursina import Entity, Vec3, color, destroy, time

from audio import get_audio_manager
from core_logic import monster_arm_reach_factor
from maze import Cell, MazeManager

# Precomputed constant – half-angle of the player's visible cone (52°).
_VIS_CONE_COS: float = math.cos(math.radians(52.0))


class MonsterController(Entity):
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
        self.path_refresh_interval_near = 0.40
        self.path_refresh_interval_mid = 0.65
        self.path_refresh_interval_far = 0.90
        self.catch_distance = 1.2
        self.max_speed = 8.0
        self.level_speeds: List[float] = [2.0, 4.0, 6.0, 6.2]  # indexed by level-1, capped at last entry
        self.current_speed = 0.0
        self.would_catch_player = False
        self.walk_anim_phase = 0.0
        self.visual_parts: List[Entity] = []
        self.left_leg: Entity | None = None
        self.right_leg: Entity | None = None
        self.left_arm: Entity | None = None
        self.right_arm: Entity | None = None
        self._rng = random.Random(0)
        self.teleport_timer = 3.0
        self.teleport_cooldown = 3.2
        self.teleport_out_of_sight_chance = 0.38
        self.arm_reach_start_distance = 2.6
        self.arm_full_reach_distance = 1.0
        self.arm_scream_threshold = 0.62
        self.audio = get_audio_manager()
        self._was_visible_to_player = False
        self._was_reaching_close = False
        self._build_visual()

    def _build_visual(self) -> None:
        body = Entity(parent=self, model="cube", position=Vec3(0, 1.2, 0), scale=Vec3(0.45, 1.6, 0.35), color=color.black)
        head = Entity(parent=self, model="cube", position=Vec3(0, 2.2, 0), scale=Vec3(0.36, 0.36, 0.36), color=color.black)

        # Front-only scary face: black mask, red eyes, jagged grin, and white fangs.
        face_z = 0.54
        front_z = 0.58
        Entity(parent=head, model="cube", position=Vec3(0.0, 0.0, face_z), scale=Vec3(0.94, 0.94, 0.08), color=color.black)
        Entity(parent=head, model="cube", position=Vec3(-0.22, 0.21, front_z), scale=Vec3(0.18, 0.16, 0.05), color=color.rgb(230, 0, 0))
        Entity(parent=head, model="cube", position=Vec3(0.22, 0.21, front_z), scale=Vec3(0.18, 0.16, 0.05), color=color.rgb(230, 0, 0))
        Entity(parent=head, model="cube", position=Vec3(-0.24, -0.22, front_z), scale=Vec3(0.14, 0.08, 0.05), color=color.rgb(90, 0, 0))
        Entity(parent=head, model="cube", position=Vec3(-0.12, -0.30, front_z), scale=Vec3(0.14, 0.08, 0.05), color=color.rgb(90, 0, 0))
        Entity(parent=head, model="cube", position=Vec3(0.0, -0.34, front_z), scale=Vec3(0.14, 0.08, 0.05), color=color.rgb(90, 0, 0))
        Entity(parent=head, model="cube", position=Vec3(0.12, -0.30, front_z), scale=Vec3(0.14, 0.08, 0.05), color=color.rgb(90, 0, 0))
        Entity(parent=head, model="cube", position=Vec3(0.24, -0.22, front_z), scale=Vec3(0.14, 0.08, 0.05), color=color.rgb(90, 0, 0))
        Entity(parent=head, model="cube", position=Vec3(-0.12, -0.36, 0.6), scale=Vec3(0.06, 0.16, 0.05), color=color.white)
        Entity(parent=head, model="cube", position=Vec3(-0.24, -0.34, 0.6), scale=Vec3(0.05, 0.14, 0.05), color=color.white)
        Entity(parent=head, model="cube", position=Vec3(-0.06, -0.38, 0.6), scale=Vec3(0.05, 0.16, 0.05), color=color.white)
        Entity(parent=head, model="cube", position=Vec3(0.0, -0.39, 0.6), scale=Vec3(0.06, 0.18, 0.05), color=color.white)
        Entity(parent=head, model="cube", position=Vec3(0.06, -0.38, 0.6), scale=Vec3(0.05, 0.16, 0.05), color=color.white)
        Entity(parent=head, model="cube", position=Vec3(0.12, -0.36, 0.6), scale=Vec3(0.06, 0.16, 0.05), color=color.white)
        Entity(parent=head, model="cube", position=Vec3(0.24, -0.34, 0.6), scale=Vec3(0.05, 0.14, 0.05), color=color.white)

        self.left_leg = Entity(parent=self, model="cube", position=Vec3(-0.2, 0.55, 0), scale=Vec3(0.1, 1.1, 0.1), color=color.black)
        self.right_leg = Entity(parent=self, model="cube", position=Vec3(0.2, 0.55, 0), scale=Vec3(0.1, 1.1, 0.1), color=color.black)
        self.left_arm = Entity(parent=self, model="cube", position=Vec3(-0.38, 1.3, 0), scale=Vec3(0.09, 1.2, 0.09), color=color.black)
        self.right_arm = Entity(parent=self, model="cube", position=Vec3(0.38, 1.3, 0), scale=Vec3(0.09, 1.2, 0.09), color=color.black)
        self.left_arm_default_position = Vec3(-0.38, 1.3, 0)
        self.right_arm_default_position = Vec3(0.38, 1.3, 0)
        self.left_arm_default_scale = Vec3(0.09, 1.2, 0.09)
        self.right_arm_default_scale = Vec3(0.09, 1.2, 0.09)
        self.visual_parts = [body, head, self.left_leg, self.right_leg, self.left_arm, self.right_arm]

    def _set_limb_pose(self, swing_degrees: float, reach_factor: float = 0.0) -> None:
        if self.left_leg is not None:
            self.left_leg.rotation_x = swing_degrees
        if self.right_leg is not None:
            self.right_leg.rotation_x = -swing_degrees
        if self.left_arm is not None:
            swing_rotation = -swing_degrees * 0.7
            self.left_arm.rotation_x = swing_rotation * (1.0 - reach_factor) + (-102.0 * reach_factor)
            self.left_arm.position = self.left_arm_default_position + Vec3(0.1 * reach_factor, 0.06 * reach_factor, 0.36 * reach_factor)
            self.left_arm.scale = self.left_arm_default_scale + Vec3(0.0, 0.22 * reach_factor, 0.0)
        if self.right_arm is not None:
            swing_rotation = swing_degrees * 0.7
            self.right_arm.rotation_x = swing_rotation * (1.0 - reach_factor) + (-102.0 * reach_factor)
            self.right_arm.position = self.right_arm_default_position + Vec3(-0.1 * reach_factor, 0.06 * reach_factor, 0.36 * reach_factor)
            self.right_arm.scale = self.right_arm_default_scale + Vec3(0.0, 0.22 * reach_factor, 0.0)

    def reset(self) -> None:
        self.spawned = False
        self.visible = False
        self.enabled = False
        self.path_cells.clear()
        # Stagger path refreshes against other AI to reduce frame spikes.
        self.path_refresh_timer = self.path_refresh_interval * 0.25
        self.position = Vec3(0, -1000, 0)
        self.current_speed = 0.0
        self.would_catch_player = False
        self.walk_anim_phase = 0.0
        self.teleport_timer = self.teleport_cooldown
        self._was_visible_to_player = False
        self._was_reaching_close = False
        self._set_limb_pose(0.0, 0.0)

    def _is_visible_to_player(self, maze: MazeManager, player_position: Vec3, player_forward: Vec3 | None, target_position: Vec3) -> bool:
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
        # Approximate player's visible cone to avoid obvious in-view spawns.
        return forward.dot(to_target_n) >= _VIS_CONE_COS

    def _pick_hidden_cell(self, maze: MazeManager, player_position: Vec3, player_forward: Vec3 | None, min_dist: int, max_dist: int) -> Cell | None:
        player_cell = maze.cell_from_world(player_position)
        hidden: List[Cell] = []
        for cell in maze.walkable_cells:
            dist = abs(cell[0] - player_cell[0]) + abs(cell[1] - player_cell[1])
            if dist < min_dist or dist > max_dist:
                continue
            wx, wz = maze.world_from_cell(cell)
            if not self._is_visible_to_player(maze, player_position, player_forward, Vec3(wx, 0, wz)):
                hidden.append(cell)

        if hidden:
            return self._rng.choice(hidden)

        # Keep spawn/teleport out of current line of sight even when distance filters fail.
        for cell in maze.walkable_cells:
            wx, wz = maze.world_from_cell(cell)
            if not self._is_visible_to_player(maze, player_position, player_forward, Vec3(wx, 0, wz)):
                hidden.append(cell)
        if hidden:
            return self._rng.choice(hidden)
        return None

    def cleanup(self) -> None:
        for part in self.visual_parts:
            destroy(part)

    def _cell_to_waypoint(self, maze: MazeManager, cell: Cell) -> Vec3:
        wx, wz = maze.world_from_cell(cell)
        return Vec3(wx, 0.0, wz)

    def _astar(self, maze: MazeManager, start: Cell, goal: Cell, max_nodes: int = 1200) -> List[Cell]:
        if start == goal:
            return [start]

        open_heap: List[Tuple[float, Cell]] = []
        heapq.heappush(open_heap, (0.0, start))
        came_from: Dict[Cell, Optional[Cell]] = {start: None}
        g_score: Dict[Cell, float] = {start: 0.0}
        visited = 0

        def heuristic(a: Cell, b: Cell) -> float:
            return abs(a[0] - b[0]) + abs(a[1] - b[1])

        while open_heap and visited < max_nodes:
            _, current = heapq.heappop(open_heap)
            visited += 1
            if current == goal:
                out: List[Cell] = [current]
                while came_from[current] is not None:
                    current = came_from[current]  # type: ignore[assignment]
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

    def update_monster(
        self,
        maze: MazeManager,
        player_position: Vec3,
        run_elapsed: float,
        player_forward: Vec3 | None = None,
        can_catch_player: bool = True,
        level: int = 1,
    ) -> bool:
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
            return False

        player_flat = Vec3(player_position.x, 0.0, player_position.z)
        distance_to_player = (player_flat - self.position).length()
        reach_factor = monster_arm_reach_factor(
            distance_to_player,
            reach_start_distance=self.arm_reach_start_distance,
            full_reach_distance=self.arm_full_reach_distance,
        )
        is_reaching_close = reach_factor >= self.arm_scream_threshold
        if is_reaching_close and not self._was_reaching_close:
            self.audio.play_monster_scream(run_elapsed)
        self._was_reaching_close = is_reaching_close

        self.would_catch_player = distance_to_player <= self.catch_distance
        if can_catch_player and self.would_catch_player:
            self._set_limb_pose(0.0, reach_factor)
            return True

        is_visible = self._is_visible_to_player(maze, player_position, player_forward, self.position)
        if is_visible and not self._was_visible_to_player:
            self.audio.play_monster_appearing(run_elapsed)
        self._was_visible_to_player = is_visible

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
            monster_cell = maze.cell_from_world(self.position)
            player_cell = maze.cell_from_world(player_position)
            # Avoid loading/unloading large chunk rings every refresh; this can stall the frame loop.
            self.path_cells = self._astar(maze, monster_cell, player_cell)
            cell_gap = abs(monster_cell[0] - player_cell[0]) + abs(monster_cell[1] - player_cell[1])
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
            idx = max(0, min(level - 1, len(self.level_speeds) - 1))
            speed = self.level_speeds[idx]
            self.current_speed = speed
            step = min(speed * time.dt, to_target.length())
            direction = to_target.normalized()
            self.position += direction * step
            yaw = math.degrees(math.atan2(direction.x, direction.z))
            self.rotation_y = yaw
            self.walk_anim_phase += time.dt * (2.8 + speed * 1.25)
            self._set_limb_pose(math.sin(self.walk_anim_phase) * 28.0, reach_factor)
        else:
            self.current_speed = 0.0
            self._set_limb_pose(0.0, reach_factor)

        return False
