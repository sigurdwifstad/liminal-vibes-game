from __future__ import annotations

import argparse
import math
import random

from ursina import AmbientLight, DirectionalLight, PointLight, Entity, Text, Texture, Ursina, Vec3, application, camera, color, destroy, scene, time, window

from panda3d.core import PNMImage, Texture as PandaTexture

from audio import get_audio_manager
from child import ChildCharacter
from core_logic import format_mmss
from game_state import GameStateUI
from maze import MazeManager
from monster import MonsterController, is_position_visible
from spider_monster import SpiderController
from player import PlayerController


_ACTIVE_GAME: LiminalVibesGame | None = None


def _build_level10_vein_overlay_texture(size: int = 256) -> Texture:
    """Procedurally generate a screen-space overlay texture for level 10:
    transparent near the center, thickening into dark-red vein-like
    branches toward the screen edges. Used (together with a flat red tint)
    to convey that the player has become the monster, without needing any
    external art assets."""
    img = PNMImage(size, size)
    img.addAlpha()
    for y in range(size):
        for x in range(size):
            img.setXel(x, y, 0.4, 0.0, 0.0)
            img.setAlpha(x, y, 0.0)

    center = size / 2.0
    for y in range(size):
        for x in range(size):
            dx = (x - center) / center
            dy = (y - center) / center
            dist = math.sqrt(dx * dx + dy * dy)
            edge_alpha = max(0.0, (dist - 0.55) / 0.85)
            if edge_alpha > 0.0:
                img.setAlpha(x, y, min(0.65, edge_alpha))

    rng = random.Random("level10_veins")
    for _ in range(18):
        edge = rng.choice(("top", "bottom", "left", "right"))
        if edge in ("top", "bottom"):
            px = rng.uniform(0, size)
            py = 0.0 if edge == "top" else float(size - 1)
            dir_x = rng.uniform(-0.6, 0.6)
            dir_y = 1.0 if edge == "top" else -1.0
        else:
            py = rng.uniform(0, size)
            px = 0.0 if edge == "left" else float(size - 1)
            dir_x = 1.0 if edge == "left" else -1.0
            dir_y = rng.uniform(-0.6, 0.6)

        length = rng.randint(int(size * 0.22), int(size * 0.5))
        for step in range(length):
            dir_x += rng.uniform(-0.18, 0.18)
            dir_y += rng.uniform(-0.18, 0.18)
            px += dir_x
            py += dir_y
            ix, iy = int(px), int(py)
            if not (0 <= ix < size and 0 <= iy < size):
                break
            fade = 1.0 - (step / length)
            img.setXel(ix, iy, 0.6, 0.0, 0.0)
            img.setAlpha(ix, iy, 0.55 * fade)

    panda_tex = PandaTexture("level10_veins")
    panda_tex.load(img)
    texture = Texture(panda_tex)
    texture.filtering = "linear"
    return texture


class LiminalVibesGame:
    # Hard distance cutoff for lamp point lights, expressed in grid cells.
    _LIGHT_MAX_DISTANCE_CELLS = 2.0
    # How many walkable-graph hops away from a lamp's own cell may still receive its
    # light. Kept in step with `_LIGHT_MAX_DISTANCE_CELLS` so the light-linking reach
    # roughly matches the real falloff distance.
    _LIGHT_LINK_HOPS = 2

    def __init__(self, test: bool = False, test_level_5_only: bool = False, start_level: int = 1, lamp_brightness: float = 0.35):
        self.test = test
        self.test_level_5_only = test_level_5_only
        self.start_level = max(1, int(start_level))
        self.lamp_brightness = self._clamp_lamp_brightness(lamp_brightness)
        self.level = self.start_level
        self.maze: MazeManager | None = None
        self.player: PlayerController | None = None
        self.monster: MonsterController | None = None
        self.spider: SpiderController | None = None
        self.child: ChildCharacter | None = None
        self._spider_drained_this_encounter = False
        self._level9_hug_played = False
        self._level9_transition_active = False
        self._level10_out_of_sight = False
        self._level10_endgame_triggered = False
        self.ui = GameStateUI()
        self.audio = get_audio_manager()
        self.point_lights: list[PointLight] = []
        self.sun_light: DirectionalLight | None = None

        self._last_hud_color_key: str = ""   # throttle redundant stamina-bar color writes

        self._stamina_bar_x = -0.88
        self._stamina_bar_y = -0.45
        self._stamina_bar_w = 0.34
        self._stamina_bar_h = 0.03
        self.stamina_bg = Entity(parent=camera.ui, model="quad", position=Vec3(self._stamina_bar_x, self._stamina_bar_y, 0), scale=Vec3(self._stamina_bar_w, self._stamina_bar_h, 1), color=color.rgba(18, 18, 18, 180), origin=(-0.5, 0.5))
        self.stamina_fill = Entity(parent=camera.ui, model="quad", position=Vec3(self._stamina_bar_x, self._stamina_bar_y, -0.001), scale=Vec3(self._stamina_bar_w, self._stamina_bar_h * 0.82, 1), color=color.rgb(110, 210, 120), origin=(-0.5, 0.5))

        self.test_hud = Text(
            parent=camera.ui,
            text="",
            position=(0.58, 0.45),
            scale=0.9,
            color=color.rgb(245, 245, 240),
            enabled=self.test,
        )

        self.teleport_hint = Text(
            parent=camera.ui,
            text="Press SHIFT to teleport",
            position=(0, -0.44),
            origin=(0, 0),
            scale=1.1,
            color=color.rgb(230, 230, 225),
            enabled=False,
        )

        # Level 10: the player has become the monster. A flat red tint plus a
        # procedurally-generated red "vein" texture along the screen borders
        # (both screen-space overlays parented to camera.ui) evoke the
        # monster's own bloodshot vision instead of a literal arms model.
        self.level10_vision_tint = Entity(
            parent=camera.ui,
            model="quad",
            position=Vec3(0, 0, 0.06),
            scale=Vec3(2.2, 1.3, 1),
            color=color.rgba(160, 0, 0, 30),
            enabled=False,
        )
        self.level10_vein_overlay = Entity(
            parent=camera.ui,
            model="quad",
            position=Vec3(0, 0, 0.05),
            scale=Vec3(2.2, 1.3, 1),
            texture=_build_level10_vein_overlay_texture(),
            color=color.rgba(255, 255, 255, 255),
            enabled=False,
        )

        self._setup_lighting()
        self.start_new_run()

    def _setup_lighting(self) -> None:
        scene.fog_density = (20, 130)
        scene.fog_color = color.rgb(195, 195, 170)
        AmbientLight(color=color.rgba(214, 212, 202, 0.2))

    @staticmethod
    def _clamp_lamp_brightness(value: float) -> float:
        return max(0.0, min(1.0, float(value)))

    def set_lamp_brightness(self, value: float) -> None:
        self.lamp_brightness = self._clamp_lamp_brightness(value)
        self._setup_point_lights_from_lamps()

    def _lamp_light_color(self):
        intensity = self._clamp_lamp_brightness(self.lamp_brightness)
        return color.rgb(
            max(0, min(255, round(248 * intensity))),
            max(0, min(255, round(246 * intensity))),
            max(0, min(255, round(236 * intensity))),
        )

    def _setup_point_lights_from_lamps(self) -> None:
        for light in self.point_lights:
            destroy(light)
        self.point_lights.clear()

        if self.maze is None:
            return

        self.lamp_brightness = self._clamp_lamp_brightness(self.lamp_brightness)
        if self.lamp_brightness <= 0.0:
            return

        # Real distance falloff: Ursina's PointLight does not expose `.range` or
        # `.brightness` attributes, so assigning them (as this code used to do)
        # silently created inert Python instance attributes that never reached the
        # underlying Panda3D light node. Panda3D's default point-light attenuation
        # is (1, 0, 0) -- i.e. constant, no falloff -- so every lamp was previously
        # shining at full, undiminished strength regardless of distance.
        #
        # Tuned so illumination falls to ~5% by ~1.75 cells, and is hard-cut at
        # `_light_max_distance_cells` cells.
        falloff_distance = self.maze.cell_size * 1.75
        quadratic_term = 19.0 / (falloff_distance ** 2)
        max_distance = self.maze.cell_size * self._LIGHT_MAX_DISTANCE_CELLS

        lamp_color = self._lamp_light_color()
        for cell, lamp_pos in zip(self.maze.lamp_cells, self.maze.lamp_positions):
            light = PointLight(color=lamp_color)
            light.position = lamp_pos

            underlying = getattr(light, "_light", None)
            if underlying is not None and hasattr(underlying, "setAttenuation"):
                underlying.setAttenuation((1.0, 0.0, quadratic_term))
                underlying.setMaxDistance(max_distance)

            # Light-linking: Ursina's PointLight attaches itself globally
            # (`render.setLight(...)`) in its constructor, which means Panda3D lights
            # *every* piece of geometry in the scene with it, with no regard for
            # solid walls in between -- light passes straight through walls. Ursina's
            # PointLight also has no shadow-casting support (unlike DirectionalLight),
            # and shadow-casting dozens/hundreds of point lights via cube-map shadow
            # buffers would be far too expensive for a maze that can have hundreds of
            # lamps (up to a 61x61 grid). Instead, detach the light from the global
            # scene root and re-link it only to the geometry that is actually
            # reachable from the lamp's own cell via the walkable-cell graph. This
            # keeps each lamp's influence confined to its own connected corridor
            # segment, matching the physical intuition that a wall backing onto an
            # unconnected, unlit area of the maze should stay dark.
            if hasattr(light, "get_child"):
                light_np = light.get_child(0)
                if not light_np.is_empty():
                    light_np.get_top().clear_light(light_np)
                    for entity in self.maze.entities_near_cell(cell, hops=self._LIGHT_LINK_HOPS):
                        entity.set_light(light_np)

            self.point_lights.append(light)

    def _random_seed(self) -> int:
        return random.randint(1, 2_000_000_000)

    def _is_test_mode_for_level(self, level: int | None = None) -> bool:
        current_level = self.level if level is None else level
        return self.test or (self.test_level_5_only and current_level == 5)

    def _load_level(self) -> None:
        if self.maze is not None:
            self.maze.clear_all()

        if self.spider is not None:
            self.spider.reset()

        seed = self._random_seed()
        self.maze = MazeManager(seed=seed, level=self.level, cell_size=4.0, test=self.test)
        self._setup_point_lights_from_lamps()
        self._setup_level7_sun_light()

        if self.player is None:
            self.player = PlayerController(position=Vec3(0, 0, 0))
        self.player.set_maze(self.maze)

        sx, sz = self.maze.world_from_cell(self.maze.start_cell)
        self.player.position = Vec3(sx, 0, sz)
        self.player.rotation_y = self.maze.player_spawn_rotation_y
        self.player.pitch = 0
        self._restore_player_camera()
        self.player.set_active(True)

        if self.monster is None:
            self.monster = MonsterController(position=Vec3(0, -1000, 0))
        self.monster.reset()
        if self.level == 7 and self.maze.pyramid_monster_cell is not None:
            self.monster.spawn_delay_seconds = float("inf")
            mx, mz = self.maze.world_from_cell(self.maze.pyramid_monster_cell)
            sx, sz = self.maze.world_from_cell(self.maze.start_cell)
            # Face the monster toward the player's approach (away from the
            # pyramid), so it looms over them front-on rather than showing its back.
            self.monster.place_crucified(Vec3(mx, 0.0, mz), facing_position=Vec3(sx, 0.0, sz))
        elif self.level == 5 and self.maze.monster_start_cell is not None:
            self.monster.spawn_delay_seconds = float("inf")
            mx, mz = self.maze.world_from_cell(self.maze.monster_start_cell)
            self.monster.place_at(Vec3(mx, 0.0, mz))
        elif self.level == 9 and self.maze.monster_start_cell is not None:
            # Level 9's friendly monster stands motionless at the far end of the
            # hallway; it is never advanced by `update_monster` (see `update`),
            # so it never chases or catches the player.
            self.monster.spawn_delay_seconds = float("inf")
            mx, mz = self.maze.world_from_cell(self.maze.monster_start_cell)
            sx, sz = self.maze.world_from_cell(self.maze.start_cell)
            self.monster.place_at(Vec3(mx, 0.0, mz))
            to_player = Vec3(sx - mx, 0.0, sz - mz)
            if to_player.length() > 0.001:
                self.monster.rotation_y = math.degrees(math.atan2(to_player.x, to_player.z))
        elif self.level == 10:
            # Level 10: the player has become the monster, so the regular
            # scary monster never spawns/chases here (see `_update_level10`).
            self.monster.spawn_delay_seconds = float("inf")
        else:
            self.monster.spawn_delay_seconds = 0.0 if self.test else 40.0

        if self.spider is None:
            self.spider = SpiderController(position=Vec3(0, -1000, 0))
        self._spider_drained_this_encounter = False
        self.spider.reset()
        self.spider.spawn_delay_seconds = float("inf") if self.level in (5, 7, 9, 10) else (0.0 if self.test else 40.0)
        self.ui.set_level(self.level)

        if self.child is None:
            self.child = ChildCharacter(position=Vec3(0, -1000, 0))
        self.child.reset()
        self._level10_out_of_sight = False
        self._level10_endgame_triggered = False
        self.player.no_sprint = self.level == 10
        self.player.use_monster_footstep = self.level == 10
        self.level10_vision_tint.enabled = self.level == 10
        self.level10_vein_overlay.enabled = self.level == 10
        if self.level == 10:
            # The child spawns at the far end of the maze (the same anchor
            # point normally reserved for the exit door), facing the player's
            # start position.
            cx, cz = self.maze.world_from_cell(self.maze.exit_cell)
            sx, sz = self.maze.world_from_cell(self.maze.start_cell)
            self.child.place_at(Vec3(cx, 0.0, cz), facing_position=Vec3(sx, 0.0, sz))

        self._level9_hug_played = False
        if self.level == 5:
            self.audio.play_intense_sequence()
        elif self.level == 7:
            self.audio.stop_ambient()
            self.audio.play_dark_drone_loop()
            self.audio.start_einkvan_sequence()
        else:
            if self.audio.dark_drone_playing:
                self.audio.stop_dark_drone_loop()
            self.audio.play_ambient_loop()

    def _setup_level7_sun_light(self) -> None:
        if self.sun_light is not None:
            destroy(self.sun_light)
            self.sun_light = None

        if self.maze is None or self.level != 7:
            return

        # Level 7 is a wide-open outdoor space with no lamps, so it needs its own
        # broad "sky" light instead of the lamp point lights used indoors.
        self.sun_light = DirectionalLight(shadows=False)
        self.sun_light.color = color.rgb(232, 224, 198)
        self.sun_light.rotation = Vec3(48, -35, 0)

    def _restore_player_camera(self) -> None:
        if self.player is None:
            return
        camera.parent = self.player
        camera.position = Vec3(0, self.player.height, 0)
        camera.rotation = Vec3(self.player.pitch, 0, 0)

    def _show_death_closeup(self) -> None:
        if self.monster is None:
            return
        focus = self.monster.world_position + Vec3(0, 2.0, 0)
        camera.parent = scene
        camera.position = focus + self.monster.forward * 0.95 + Vec3(0, 0.06, 0)
        camera.look_at(focus)
        camera.rotation = Vec3(camera.rotation_x, camera.rotation_y, 0)

    def start_new_run(self, level: int | None = None) -> None:
        """Begin a fresh run. `level` defaults to `self.start_level` (the
        CLI --start-level, used for the very first run / dev testing); an
        explicit `level` overrides that -- used by the "R" restart key to
        always return to level 1 regardless of how the run was launched."""
        self.level = self.start_level if level is None else level
        self.ui.start_new_run(level=self.level)
        self.audio.play_ambient_loop()
        self._load_level()

    def _advance_level(self) -> None:
        self.level += 1
        self.ui.on_level_completed(level=self.level)
        self._load_level()

    def _start_level9_transition(self) -> None:
        if self.player is None:
            return
        self._level9_transition_active = True
        self.player.set_active(False)
        self.ui.start_level9_transition()

    def _update_level9_transition(self) -> None:
        if self.ui.level9_transition_request_level_load and not self.ui.level9_transition_level_loaded:
            self.level += 1
            self._load_level()
            assert self.player is not None
            self.player.set_active(False)
            self.ui.mark_level9_transition_level_loaded()

        if self.ui.level9_transition_finished:
            self._level9_transition_active = False
            self.ui.complete_level9_transition()
            assert self.player is not None
            self.player.set_active(True)

    def _update_level9(self) -> None:
        """Level 9 ("Give the monster a hug"): the friendly monster never
        chases, so this replaces the normal monster/spider AI updates. Playing
        `monster_hug.wav` once the player is three cells away from the
        monster, and advancing the level once the player touches it."""
        assert self.player is not None and self.maze is not None and self.monster is not None
        if self.maze.monster_start_cell is None:
            return

        monster_x, monster_z = self.maze.world_from_cell(self.maze.monster_start_cell)
        player_pos = self.player.world_position
        remaining_distance = math.hypot(monster_x - player_pos.x, monster_z - player_pos.z)

        self.monster.update_friendly(player_pos, self.ui.run.survival_seconds)

        hug_trigger_distance = self.maze.cell_size * 3.0
        if not self._level9_hug_played and remaining_distance <= hug_trigger_distance:
            self._level9_hug_played = True
            self.audio.play_monster_hug()

        if remaining_distance <= self.monster.catch_distance:
            self._start_level9_transition()

    def _update_level10(self) -> None:
        """Level 10 ("The final level"): the player has become the monster,
        chasing a small child who wanders the maze and flees (at sprint
        speed) whenever the player-monster spots it within its own field of
        view. The regular monster/spider AI is fully disabled here (see
        `_load_level`); this replaces it with the child's wander/flee AI,
        the "out of sight of the child" check that gates the teleport
        prompt/ability, and the catch -> monster scream -> freeze/fade/
        "END GAME" finale."""
        assert self.player is not None and self.maze is not None and self.child is not None
        if self._level10_endgame_triggered:
            return

        player_pos = self.player.world_position
        player_flat = Vec3(player_pos.x, 0.0, player_pos.z)

        # Check the catch distance *before* letting the child move this frame,
        # otherwise a fleeing child could dodge out of catch range within the
        # same frame the player reaches it.
        distance_to_child = (player_flat - self.child.position).length()
        if distance_to_child <= self.child.catch_distance:
            self._level10_endgame_triggered = True
            self.player.set_active(False)
            self.audio.play_monster_scream(self.ui.run.survival_seconds)
            self.audio.play_endgame()
            self.ui.on_endgame_caught()
            return

        self.child.update_child(self.maze, player_pos, self.player.forward, self.ui.run.survival_seconds)

        is_player_visible_to_child = is_position_visible(self.maze, self.child.world_position, self.child.forward, player_pos)
        self._level10_out_of_sight = not is_player_visible_to_child

    def _teleport_player(self) -> None:
        """Level 10: teleport the player-monster to a random walkable cell,
        available only while out of the child's sight (see `_update_level10`
        and `input`). Plays the `monster_appearing` stinger as the
        player-monster reappears elsewhere in the maze."""
        if self.player is None or self.maze is None:
            return
        player_cell = self.maze.cell_from_world(self.player.world_position)
        target_cell = self.maze.random_far_walkable_cell(player_cell, min_dist=10)
        tx, tz = self.maze.world_from_cell(target_cell)
        self.player.position = Vec3(tx, 0.0, tz)
        self.audio.play_monster_appearing(self.ui.run.survival_seconds)

    def update(self) -> None:
        self.ui.update()
        if self._level9_transition_active:
            self._update_level9_transition()
            self._update_hud()
            return

        if self.ui.run.running:
            assert self.player is not None and self.maze is not None and self.monster is not None and self.spider is not None
            level_test_mode = self._is_test_mode_for_level()
            if self.level != 10 and self.maze.player_reached_exit(self.player.world_position):
                self._advance_level()
                return

            if self.level == 7:
                if self.audio.update_einkvan_sequence():
                    self.maze.unlock_pyramid_door()
            elif self.level == 9:
                self._update_level9()
            elif self.level == 10:
                self._update_level10()
            else:
                caught = self.monster.update_monster(
                    self.maze,
                    self.player.world_position,
                    self.ui.run.survival_seconds,
                    self.player.forward,
                    can_catch_player=not level_test_mode,
                    level=self.level,
                )
                if caught:
                    self.player.set_active(False)
                    self._show_death_closeup()
                    self.ui.on_player_caught()
                    return

                if self.level != 5:
                    spider_drains = self.spider.update_spider(
                        self.maze,
                        self.player.world_position,
                        self.ui.run.survival_seconds,
                        self.player.forward,
                        level=self.level,
                    )
                    if spider_drains and not self._spider_drained_this_encounter:
                        self._spider_drained_this_encounter = True
                        self.player.stamina = 0.0
                        if not self.player.exhausted:
                            self.player.audio.play_exhausted()
                        self.player.exhausted = True
                        return
                    elif not spider_drains:
                        self._spider_drained_this_encounter = False
        self._update_hud()

    # Precomputed stamina bar colors – avoids allocating new color objects every frame.
    _STAMINA_COLORS = {
        "exhausted": color.rgb(210, 55, 55),
        "green":     color.rgb(110, 210, 120),
        "yellow":    color.rgb(220, 190, 90),
        "red":       color.rgb(225, 95, 85),
    }

    def _update_hud(self) -> None:
        if self.player is None or self.monster is None:
            return

        is_running = self.ui.run.running
        is_level_10 = self.level == 10
        self.stamina_bg.enabled = is_running and not is_level_10
        self.stamina_fill.enabled = is_running and not is_level_10
        self.teleport_hint.enabled = is_running and is_level_10 and self._level10_out_of_sight

        if is_level_10:
            self._update_test_hud()
            return

        ratio = self.player.stamina_ratio
        self.stamina_fill.scale_x = self._stamina_bar_w * max(0.001, ratio)

        # Only assign a new color when the bracket changes to avoid per-frame GPU state writes.
        if self.player.exhausted:
            color_key = "exhausted"
        elif ratio > 0.55:
            color_key = "green"
        elif ratio > 0.25:
            color_key = "yellow"
        else:
            color_key = "red"

        if color_key != self._last_hud_color_key:
            self.stamina_fill.color = self._STAMINA_COLORS[color_key]
            self._last_hud_color_key = color_key

        self._update_test_hud()

    def _update_test_hud(self) -> None:
        if self._is_test_mode_for_level():
            self.test_hud.enabled = True
            would_kill = "YES" if self.monster.would_catch_player else "NO"
            fps = int(1.0 / max(0.0001, time.dt))
            path_nodes = len(self.monster.path_cells)
            self.test_hud.text = (
                "TEST MODE (INVINCIBLE)\n"
                f"Elapsed: {format_mmss(self.ui.run.survival_seconds)}\n"
                f"Level: {self.level}\n"
                f"FPS: {fps}\n"
                f"Monster speed: {self.monster.current_speed:.2f}\n"
                f"Would kill: {would_kill}\n"
                f"Path nodes: {path_nodes}"
            )
        else:
            self.test_hud.enabled = False

    def input(self, key: str) -> None:
        if key in ("escape", "esc"):
            application.quit()
            return

        if key == "r" and not self.ui.run.running:
            self.start_new_run(level=1)
            return

        if key in ("shift", "left shift", "right shift"):
            if self.level == 10 and self.ui.run.running and self._level10_out_of_sight:
                self._teleport_player()


def update() -> None:
    if _ACTIVE_GAME is not None:
        _ACTIVE_GAME.update()


def input(key: str) -> None:
    if _ACTIVE_GAME is not None:
        _ACTIVE_GAME.input(key)


def main(test: bool = False, test_level_5_only: bool = False, start_level: int = 1, lamp_brightness: float = 0.8) -> None:
    app = Ursina(borderless=False, fullscreen=True)
    window.title = "Liminal Vibes"
    window.color = color.rgb(130, 130, 115)
    window.exit_button.visible = True
    window.fps_counter.enabled = True

    global _ACTIVE_GAME
    _ACTIVE_GAME = LiminalVibesGame(
        test=test,
        test_level_5_only=test_level_5_only,
        start_level=start_level,
        lamp_brightness=lamp_brightness,
    )

    app.run()


def run(test: bool = False, test_level_5_only: bool = False, start_level: int = 1, lamp_brightness: float = 0.35) -> None:
    main(test=test, test_level_5_only=test_level_5_only, start_level=start_level, lamp_brightness=lamp_brightness)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Liminal Spaces")
    parser.add_argument("--test", action="store_true", help="Enable test mode with immediate monster spawn")
    parser.add_argument("--test-level-5", action="store_true", help="Enable test mode only when level 5 is reached")
    parser.add_argument("--start-level", type=int, default=1, help="Start a new run at the given level (for example: 5)")
    parser.add_argument("--lamp-brightness", type=float, default=1.0, help="Lamp point light intensity from 0.0 (off) to 1.0 (full)")
    args = parser.parse_args()
    main(test=args.test, test_level_5_only=args.test_level_5, start_level=args.start_level, lamp_brightness=args.lamp_brightness)
