from __future__ import annotations

import math
import random
from typing import List

from ursina import Entity, Vec3, color, destroy, time

from maze import Cell, MazeManager
from monster import astar_path, is_position_visible


class ChildCharacter(Entity):
    """Level 10's fleeing child: a small humanoid that continuously wanders
    the maze via simple pathfinding, and flees (faster, toward a distant
    walkable cell) whenever the player-monster spots it within its own
    field of view."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.height = 1.0  # small child, roughly waist-high on the player-monster
        self.catch_distance = 0.9
        self.explore_speed = 2.2
        # Matches the player's own sprint speed from earlier levels
        # (PlayerController.walk_speed * sprint_multiplier = 6.0 * 1.65).
        self.flee_speed = 9.9
        self.fleeing = False
        self.spawned = False
        self.path_cells: List[Cell] = []
        # While fleeing, the path is periodically re-planned around the
        # player-monster's latest position so the child keeps running away
        # from it rather than committing to a single stale route that could
        # double back toward the player as it moves.
        self.flee_replan_timer = 0.0
        self.flee_replan_interval = 0.5
        # After the player-monster loses sight of the child, the child keeps
        # sprinting away for a short grace period (rather than immediately
        # dropping back to a casual wander) in case it's still nearby/about
        # to look back.
        self.flee_grace_timer = 0.0
        self.flee_grace_duration = 1.0
        self.walk_anim_phase = 0.0
        self._rng = random.Random(0)
        self.left_leg: Entity | None = None
        self.right_leg: Entity | None = None
        self.left_arm: Entity | None = None
        self.right_arm: Entity | None = None
        self.visual_parts: List[Entity] = []
        self._build_visual()

    def _build_visual(self) -> None:
        torso_color = color.rgb(58, 92, 196)   # blue torso/arms
        leg_color = color.rgb(101, 67, 38)     # brown legs
        head_color = color.rgb(233, 202, 164)  # beige head
        hair_color = color.rgb(90, 56, 30)     # brown hair tuft

        body = Entity(
            parent=self,
            model="cube",
            position=Vec3(0, 0.65, 0),
            scale=Vec3(0.26, 0.85, 0.2),
            color=torso_color,
        )
        head = Entity(
            parent=self,
            model="cube",
            position=Vec3(0, 1.24, 0),
            scale=Vec3(0.22, 0.22, 0.22),
            color=head_color,
        )
        hair = Entity(
            parent=self,
            model="cube",
            position=Vec3(0, 1.365, 0),
            scale=Vec3(0.12, 0.06, 0.12),
            color=hair_color,
        )
        self.left_leg = Entity(
            parent=self,
            model="cube",
            position=Vec3(-0.1, 0.28, 0),
            scale=Vec3(0.07, 0.58, 0.07),
            color=leg_color,
        )
        self.right_leg = Entity(
            parent=self,
            model="cube",
            position=Vec3(0.1, 0.28, 0),
            scale=Vec3(0.07, 0.58, 0.07),
            color=leg_color,
        )
        self.left_arm = Entity(
            parent=self,
            model="cube",
            position=Vec3(-0.18, 0.68, 0),
            scale=Vec3(0.06, 0.6, 0.06),
            color=torso_color,
        )
        self.right_arm = Entity(
            parent=self,
            model="cube",
            position=Vec3(0.18, 0.68, 0),
            scale=Vec3(0.06, 0.6, 0.06),
            color=torso_color,
        )
        self.visual_parts = [body, head, hair, self.left_leg, self.right_leg, self.left_arm, self.right_arm]

    def _set_limb_pose(self, swing_degrees: float) -> None:
        if self.left_leg is not None:
            self.left_leg.rotation_x = swing_degrees
        if self.right_leg is not None:
            self.right_leg.rotation_x = -swing_degrees
        if self.left_arm is not None:
            self.left_arm.rotation_x = -swing_degrees
        if self.right_arm is not None:
            self.right_arm.rotation_x = swing_degrees

    def reset(self) -> None:
        self.fleeing = False
        self.spawned = False
        self.enabled = False
        self.visible = False
        self.path_cells.clear()
        self.flee_replan_timer = 0.0
        self.flee_grace_timer = 0.0
        self.walk_anim_phase = 0.0
        self.position = Vec3(0, -1000, 0)
        self._set_limb_pose(0.0)

    def cleanup(self) -> None:
        for part in self.visual_parts:
            destroy(part)

    def place_at(self, position: Vec3, facing_position: Vec3 | None = None) -> None:
        self.position = position
        self.spawned = True
        self.visible = True
        self.enabled = True
        self.fleeing = False
        self.path_cells.clear()
        self.flee_replan_timer = 0.0
        self.flee_grace_timer = 0.0
        self._set_limb_pose(0.0)
        if facing_position is not None:
            to_target = Vec3(facing_position.x - position.x, 0.0, facing_position.z - position.z)
            if to_target.length() > 0.001:
                self.rotation_y = math.degrees(math.atan2(to_target.x, to_target.z))

    def _pick_wander_target(self, maze: MazeManager) -> None:
        """Pick a nearby walkable cell to explore toward, using the same
        simple pathfinding as the flee behavior."""
        child_cell = maze.cell_from_world(self.position)
        target_cell = maze.random_far_walkable_cell(child_cell, min_dist=3)
        self.path_cells = astar_path(maze, child_cell, target_cell)

    def _pick_flee_target(self, maze: MazeManager, player_cell: Cell) -> None:
        """Pick the single adjacent cell that most increases the child's
        distance from the player-monster's current cell (a local greedy
        step, re-evaluated frequently, rather than committing to one
        long-range path) -- this is what keeps the child from cutting back
        toward the player mid-route as it moves.

        If every reachable neighbor would bring the child *closer* to the
        player-monster (a dead end/cul-de-sac with the player blocking the
        only way out), the child has nowhere safe to go: it stays put
        (`path_cells` is left with just its current cell) instead of being
        forced to run toward/past the player."""
        child_cell = maze.cell_from_world(self.position)
        self.flee_replan_timer = self.flee_replan_interval

        def distance_from_player(cell: Cell) -> int:
            return abs(cell[0] - player_cell[0]) + abs(cell[1] - player_cell[1])

        current_distance = distance_from_player(child_cell)
        neighbors = list(maze.walkable_neighbors(child_cell))
        # Never step into the player-monster's own cell, even as a "farther"
        # option relative to some other reference point.
        safe_neighbors = [cell for cell in neighbors if cell != player_cell and distance_from_player(cell) >= current_distance]

        if not safe_neighbors:
            # Dead end: no direction leads away from (or even sideways to)
            # the player-monster. Stay put rather than running toward it.
            self.path_cells = [child_cell]
            return

        best_distance = max(distance_from_player(cell) for cell in safe_neighbors)
        best_candidates = [cell for cell in safe_neighbors if distance_from_player(cell) == best_distance]
        next_cell = self._rng.choice(best_candidates)
        self.path_cells = [child_cell, next_cell]

    def is_visible_to(self, maze: MazeManager, viewer_position: Vec3, viewer_forward: Vec3 | None = None) -> bool:
        """Whether this child can be seen from `viewer_position`. Level 10
        reuses this (inverted, with the child as the "viewer") to determine
        whether the player-monster is hidden from the child and may
        teleport."""
        return is_position_visible(maze, viewer_position, viewer_forward, self.world_position)

    def update_child(self, maze: MazeManager, player_position: Vec3, player_forward: Vec3 | None = None, run_elapsed: float = 0.0) -> None:
        if not self.spawned:
            return

        player_flat = Vec3(player_position.x, 0.0, player_position.z)
        # The child flees when *it* is within the player-monster's field of
        # view (i.e. the player-monster can see the child), not merely when
        # the child can see the player.
        child_in_player_sight = is_position_visible(maze, player_flat, player_forward, self.position)
        player_cell = maze.cell_from_world(player_flat)

        if child_in_player_sight:
            self.flee_grace_timer = self.flee_grace_duration
        elif self.flee_grace_timer > 0.0:
            self.flee_grace_timer -= time.dt

        # Keep sprinting/avoiding for a short grace period after losing
        # sight of the player-monster, instead of instantly relaxing back to
        # a casual wander the moment it looks away.
        should_flee = child_in_player_sight or self.flee_grace_timer > 0.0

        if should_flee:
            if not self.fleeing:
                self.fleeing = True
                self._pick_flee_target(maze, player_cell)
            else:
                # Keep re-evaluating the next hop away from the
                # player-monster's latest position while fleeing, so the
                # child reacts as the player moves (and immediately keeps
                # retrying, every frame, whenever it's currently stuck --
                # `path_cells` has fewer than 2 entries -- in case an escape
                # route has just opened up).
                self.flee_replan_timer -= time.dt
                if self.flee_replan_timer <= 0.0 or len(self.path_cells) < 2:
                    self._pick_flee_target(maze, player_cell)
        else:
            if self.fleeing:
                self.fleeing = False
                self.path_cells.clear()
            if len(self.path_cells) < 2:
                self._pick_wander_target(maze)

        if len(self.path_cells) >= 2:
            wx, wz = maze.world_from_cell(self.path_cells[1])
            next_waypoint = Vec3(wx, 0.0, wz)
        else:
            self._set_limb_pose(0.0)
            return

        to_target = next_waypoint - self.position
        if to_target.length() <= 0.06:
            # Reached this waypoint; drop it and keep following the rest of the path.
            self.path_cells.pop(0)
            return

        speed = self.flee_speed if self.fleeing else self.explore_speed
        step = min(speed * time.dt, to_target.length())
        direction = to_target.normalized()
        self.position += direction * step
        self.rotation_y = math.degrees(math.atan2(direction.x, direction.z))
        self.walk_anim_phase += time.dt * (3.2 + speed * 1.1)
        self._set_limb_pose(math.sin(self.walk_anim_phase) * 24.0)
