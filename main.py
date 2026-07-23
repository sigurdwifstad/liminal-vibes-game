from __future__ import annotations

import argparse
import random

from ursina import AmbientLight, DirectionalLight, Entity, Text, Ursina, Vec3, application, camera, color, scene, time, window

from audio import get_audio_manager
from core_logic import format_mmss
from game_state import GameStateUI
from maze import MazeManager
from monster import MonsterController
from spider_monster import SpiderController
from player import PlayerController


_ACTIVE_GAME: LiminalVibesGame | None = None


class LiminalVibesGame:
    def __init__(self, test: bool = False, test_level_5_only: bool = False, start_level: int = 1):
        self.test = test
        self.test_level_5_only = test_level_5_only
        self.start_level = max(1, int(start_level))
        self.level = self.start_level
        self.maze: MazeManager | None = None
        self.player: PlayerController | None = None
        self.monster: MonsterController | None = None
        self.spider: SpiderController | None = None
        self._spider_drained_this_encounter = False
        self.ui = GameStateUI()
        self.audio = get_audio_manager()

        self._last_hud_color_key: str = ""   # throttle redundant stamina-bar color writes

        self._stamina_bar_x = -0.78
        self._stamina_bar_y = -0.45
        self._stamina_bar_w = 0.34
        self._stamina_bar_h = 0.03
        self.stamina_bg = Entity(parent=camera.ui, model="quad", position=Vec3(self._stamina_bar_x, self._stamina_bar_y, 0), scale=Vec3(self._stamina_bar_w, self._stamina_bar_h, 1), color=color.rgba(18, 18, 18, 180), origin=(-0.5, 0.5))
        self.stamina_fill = Entity(parent=camera.ui, model="quad", position=Vec3(self._stamina_bar_x, self._stamina_bar_y, -0.001), scale=Vec3(self._stamina_bar_w, self._stamina_bar_h * 0.82, 1), color=color.rgb(110, 210, 120), origin=(-0.5, 0.5))
        self.stamina_label = Text(parent=camera.ui, text="STAMINA", position=(-0.94, -0.44), scale=0.9, color=color.rgb(240, 240, 235))

        self.test_hud = Text(
            parent=camera.ui,
            text="",
            position=(0.58, 0.45),
            scale=0.9,
            color=color.rgb(245, 245, 240),
            enabled=self.test,
        )

        self._setup_lighting()
        self.start_new_run()

    def _setup_lighting(self) -> None:
        scene.fog_density = (20, 130)
        scene.fog_color = color.rgb(195, 195, 170)
        AmbientLight(color=color.rgba(212, 210, 198, 0.5))
        key = DirectionalLight(color=color.rgba(240, 232, 210, 0.32))
        key.look_at(Vec3(0.6, -1.0, 0.8))

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
        if self.level == 5 and self.maze.monster_start_cell is not None:
            self.monster.spawn_delay_seconds = float("inf")
            mx, mz = self.maze.world_from_cell(self.maze.monster_start_cell)
            self.monster.place_at(Vec3(mx, 0.0, mz))
        else:
            self.monster.spawn_delay_seconds = 0.0 if self.test else 40.0

        if self.spider is None:
            self.spider = SpiderController(position=Vec3(0, -1000, 0))
        self._spider_drained_this_encounter = False
        self.spider.reset()
        self.spider.spawn_delay_seconds = float("inf") if self.level == 5 else (0.0 if self.test else 40.0)
        self.ui.set_level(self.level)

        if self.level == 5:
            self.audio.play_intense_sequence()

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

    def start_new_run(self) -> None:
        self.level = self.start_level
        self.ui.start_new_run(level=self.level)
        self.audio.play_ambient_loop()
        self._load_level()

    def _advance_level(self) -> None:
        self.level += 1
        self.ui.on_level_completed(level=self.level)
        self._load_level()

    def update(self) -> None:
        self.ui.update()
        if self.ui.run.running:
            assert self.player is not None and self.maze is not None and self.monster is not None and self.spider is not None
            level_test_mode = self._is_test_mode_for_level()
            if self.maze.player_reached_exit(self.player.world_position):
                self._advance_level()
                return

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
        self.stamina_bg.enabled = is_running
        self.stamina_fill.enabled = is_running
        self.stamina_label.enabled = is_running

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
            self.start_new_run()


def update() -> None:
    if _ACTIVE_GAME is not None:
        _ACTIVE_GAME.update()


def input(key: str) -> None:
    if _ACTIVE_GAME is not None:
        _ACTIVE_GAME.input(key)


def main(test: bool = False, test_level_5_only: bool = False, start_level: int = 1) -> None:
    app = Ursina(borderless=False, fullscreen=True)
    window.title = "Liminal Spaces"
    window.color = color.rgb(130, 130, 115)
    window.exit_button.visible = True
    window.fps_counter.enabled = True

    global _ACTIVE_GAME
    _ACTIVE_GAME = LiminalVibesGame(test=test, test_level_5_only=test_level_5_only, start_level=start_level)

    app.run()


def run(test: bool = False, test_level_5_only: bool = False, start_level: int = 1) -> None:
    main(test=test, test_level_5_only=test_level_5_only, start_level=start_level)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Liminal Spaces")
    parser.add_argument("--test", action="store_true", help="Enable test mode with immediate monster spawn")
    parser.add_argument("--test-level-5", action="store_true", help="Enable test mode only when level 5 is reached")
    parser.add_argument("--start-level", type=int, default=1, help="Start a new run at the given level (for example: 5)")
    args = parser.parse_args()
    main(test=args.test, test_level_5_only=args.test_level_5, start_level=args.start_level)
