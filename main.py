from __future__ import annotations

import argparse
import random

from ursina import AmbientLight, DirectionalLight, Entity, Text, Ursina, Vec3, application, camera, color, scene, time, window

from audio import get_audio_manager
from core_logic import format_mmss
from game_state import GameStateUI
from maze import MazeManager
from monster import MonsterController
from player import PlayerController


_ACTIVE_GAME: LiminalVibesGame | None = None


class LiminalVibesGame:
    def __init__(self, test: bool = False):
        self.test = test
        self.level = 1
        self.maze: MazeManager | None = None
        self.player: PlayerController | None = None
        self.monster: MonsterController | None = None
        self.ui = GameStateUI()
        self.audio = get_audio_manager()

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

    def _load_level(self) -> None:
        if self.maze is not None:
            self.maze.clear_all()

        seed = self._random_seed()
        self.maze = MazeManager(seed=seed, level=self.level, cell_size=4.0, test=self.test)

        if self.player is None:
            self.player = PlayerController(position=Vec3(0, 0, 0))

        self._restore_player_camera()

        sx, sz = self.maze.world_from_cell(self.maze.start_cell)
        self.player.position = Vec3(sx, 0, sz)
        self.player.rotation = Vec3(0, 0, 0)
        self.player.pitch = 0
        self.player.set_active(True)

        if self.monster is None:
            self.monster = MonsterController(position=Vec3(0, -1000, 0))
        self.monster.spawn_delay_seconds = 0.0 if self.test else 40.0
        self.monster.reset()
        self.ui.set_level(self.level)

    def _restore_player_camera(self) -> None:
        if self.player is None:
            return
        camera.parent = self.player
        camera.position = Vec3(0, self.player.height, 0)
        camera.rotation = Vec3(self.player.pitch, 0, 0)

    def _show_death_closeup(self) -> None:
        if self.monster is None:
            return
        focus = self.monster.world_position + Vec3(0, 1.8, 0)
        camera.parent = scene
        camera.position = focus + self.monster.forward * 0.95 + Vec3(0, 0.06, 0)
        camera.look_at(focus)

    def start_new_run(self) -> None:
        self.level = 1
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
            assert self.player is not None and self.maze is not None and self.monster is not None
            if self.maze.player_reached_exit(self.player.world_position):
                self._advance_level()
                return

            caught = self.monster.update_monster(
                self.maze,
                self.player.world_position,
                self.ui.run.survival_seconds,
                self.player.forward,
                can_catch_player=not self.test,
                level=self.level,
            )
            if caught:
                self.player.set_active(False)
                self._show_death_closeup()
                self.ui.on_player_caught()
        self._update_hud()

    def _update_hud(self) -> None:
        if self.player is None or self.monster is None:
            return

        is_running = self.ui.run.running
        self.stamina_bg.enabled = is_running
        self.stamina_fill.enabled = is_running
        self.stamina_label.enabled = is_running

        ratio = self.player.stamina_ratio
        self.stamina_fill.scale_x = self._stamina_bar_w * max(0.001, ratio)
        if self.player.exhausted:
            self.stamina_fill.color = color.rgb(210, 55, 55)
        elif ratio > 0.55:
            self.stamina_fill.color = color.rgb(110, 210, 120)
        elif ratio > 0.25:
            self.stamina_fill.color = color.rgb(220, 190, 90)
        else:
            self.stamina_fill.color = color.rgb(225, 95, 85)

        if self.test:
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


def main(test: bool = False) -> None:
    app = Ursina(borderless=False, fullscreen=True)
    window.title = "Liminal Spaces"
    window.color = color.rgb(130, 130, 115)
    window.exit_button.visible = True
    window.fps_counter.enabled = True

    global _ACTIVE_GAME
    _ACTIVE_GAME = LiminalVibesGame(test=test)

    app.run()


def run(test: bool = False) -> None:
    main(test=test)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Liminal Spaces")
    parser.add_argument("--test", action="store_true", help="Enable test mode with immediate monster spawn")
    args = parser.parse_args()
    main(test=args.test)
