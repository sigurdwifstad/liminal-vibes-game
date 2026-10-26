from __future__ import annotations

import math

from ursina import Entity, Vec3, color, time

from furniture import get_fabric_texture
from maze import Cell, MazeManager
from monster import MonsterController, astar_path, is_position_visible


class WeepingAngel(Entity):
    CATCH_DISTANCE = 1.35
    MOVE_SPEED = 30.0

    def __init__(self, audio, **kwargs):
        super().__init__(**kwargs)
        self.audio = audio
        self.spawned = False
        self.path_cells: list[Cell] = []
        self.path_refresh_timer = 0.0
        self._build_visual()
        self.enabled = False
        self.visible = False

    def _build_visual(self) -> None:
        Entity(
            parent=self,
            model="cube",
            position=Vec3(0, 1.25, 0),
            scale=Vec3(0.85, 2.5, 0.75),
            color=color.rgba(0, 0, 0, 0),
            collider="box",
        )
        # Reuse the level-7 monster's model (arms stretched out to the sides) at
        # regular size; it is only used as a static visual and never updated.
        self.model_entity = MonsterController(parent=self, position=Vec3(0, 0, 0))
        self.model_entity.crucified_scale = 1.0
        self.model_entity.place_crucified(Vec3(0, 0, 0))
        self.model_entity.position = Vec3(0, 0, 0)
        fabric = get_fabric_texture()
        for part in self.model_entity.visual_parts:
            part.texture = fabric
            part.texture_scale = (2, 2)
            # The face mask (a textured child of the head) is browned too; the
            # eyes, mouth and fangs are untextured and stay as they were.
            for child in part.children:
                if getattr(child, "texture", None) is not None:
                    child.texture = fabric

    def reset(self) -> None:
        self.spawned = False
        self.enabled = False
        self.visible = False
        self.position = Vec3(0, -1000, 0)
        self.path_cells.clear()
        self.path_refresh_timer = 0.0
        self.audio.stop_weeping_angel()

    def place_at(self, position: Vec3, facing_position: Vec3) -> None:
        self.position = position
        self.spawned = True
        self.enabled = True
        self.visible = True
        self.path_cells.clear()
        self.path_refresh_timer = 0.0
        direction = Vec3(facing_position.x - position.x, 0.0, facing_position.z - position.z)
        if direction.length() > 0.001:
            self.rotation_y = math.degrees(math.atan2(direction.x, direction.z))

    def update_angel(self, maze: MazeManager, player_position: Vec3, player_forward: Vec3) -> bool:
        if not self.spawned:
            return False

        distance = math.hypot(
            player_position.x - self.position.x,
            player_position.z - self.position.z,
        )
        if distance <= self.CATCH_DISTANCE:
            self.audio.stop_weeping_angel()
            return True

        # The sound loops constantly in level 10, whether or not the angel is seen.
        self.audio.play_weeping_angel()
        visible_to_player = is_position_visible(maze, player_position, player_forward, self.position)
        if visible_to_player:
            return False

        self.path_refresh_timer -= time.dt
        if self.path_refresh_timer <= 0.0:
            start = maze.navigation_cell_for_position(self.position)
            goal = maze.navigation_cell_for_position(player_position)
            self.path_cells = astar_path(maze, start, goal, max_nodes=4000)
            self.path_refresh_timer = 0.25

        if len(self.path_cells) < 2:
            return False

        waypoint = maze.world_from_cell(self.path_cells[1])
        target = Vec3(waypoint[0], self.position.y, waypoint[1])
        direction = target - self.position
        if direction.length() <= 0.04:
            self.path_cells.pop(0)
            return False

        direction = direction.normalized()
        step = min(self.MOVE_SPEED * time.dt, (target - self.position).length())
        candidate = self.position + direction * step
        if maze.can_occupy_position(candidate, radius=0.35, ignore_furniture=True):
            self.position = candidate
            self.rotation_y = math.degrees(math.atan2(direction.x, direction.z))
        return False
