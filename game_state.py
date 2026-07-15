from __future__ import annotations

import time as pytime
from dataclasses import dataclass

from ursina import Entity, Text, Vec3, camera, color, time

from core_logic import format_mmss


@dataclass
class RunState:
    running: bool = True
    start_time: float = 0.0
    end_time: float = 0.0
    level: int = 1

    @property
    def survival_seconds(self) -> float:
        if self.running:
            return max(0.0, pytime.time() - self.start_time)
        return max(0.0, self.end_time - self.start_time)


class GameStateUI:
    def __init__(self):
        self.run = RunState(running=True, start_time=pytime.time())
        self.hud_time = Text(text="00:00", position=(-0.86, 0.45), scale=1.2, color=color.white)
        self.hud_level = Text(text="Level 1", position=(-0.86, 0.40), scale=1.1, color=color.rgb(242, 242, 235))
        self.level_banner_timer = 0.0
        self.level_banner = Text(text="", position=(0, 0.22), origin=(0, 0), scale=1.9, color=color.rgb(240, 230, 170), enabled=False)

        self.game_over_root = Entity(enabled=False)
        self.game_over_title = Text(
            parent=self.game_over_root,
            text="GAME OVER",
            position=(0, 0.1),
            origin=(0, 0),
            scale=3,
            color=color.rgb(255, 70, 70),
        )
        self.game_over_time = Text(
            parent=self.game_over_root,
            text="Survived: 00:00",
            position=(0, 0),
            origin=(0, 0),
            scale=1.6,
            color=color.white,
        )
        self.game_over_hint = Text(
            parent=self.game_over_root,
            text="Press R to restart",
            position=(0, -0.08),
            origin=(0, 0),
            scale=1.2,
            color=color.rgb(230, 230, 230),
        )

        self.loading_root = Entity(parent=camera.ui, enabled=False)
        self.loading_backdrop = Entity(
            parent=self.loading_root,
            model="quad",
            position=Vec3(0, 0, 0),
            scale=Vec3(2.2, 1.3, 1),
            color=color.rgba(8, 8, 8, 235),
        )
        self.loading_title = Text(
            parent=self.loading_root,
            text="LOADING NEXT LEVEL",
            position=(0, 0.06),
            origin=(0, 0),
            scale=1.9,
            color=color.rgb(245, 245, 238),
        )
        self.loading_hint = Text(
            parent=self.loading_root,
            text="Generating maze...",
            position=(0, -0.03),
            origin=(0, 0),
            scale=1.1,
            color=color.rgb(210, 210, 205),
        )

    def start_new_run(self, level: int = 1) -> None:
        self.run.running = True
        self.run.start_time = pytime.time()
        self.run.end_time = 0.0
        self.run.level = level
        self.loading_root.enabled = False
        self.game_over_root.enabled = False
        self.hud_time.enabled = True
        self.hud_level.enabled = True
        self.hud_time.text = "00:00"
        self.hud_level.text = f"Level {self.run.level}"
        self.level_banner.enabled = False
        self.level_banner_timer = 0.0

    def set_level(self, level: int) -> None:
        self.run.level = level
        self.hud_level.text = f"Level {level}"

    def on_level_completed(self, level: int) -> None:
        self.set_level(level)
        self.level_banner.text = f"LEVEL {level}"
        self.level_banner.enabled = True
        self.level_banner_timer = 2.0

    def on_player_caught(self) -> None:
        self.run.running = False
        self.run.end_time = pytime.time()
        self.hud_time.enabled = False
        self.hud_level.enabled = False
        self.level_banner.enabled = False
        self.loading_root.enabled = False
        self.game_over_root.enabled = True
        self.game_over_time.text = f"Survived: {format_mmss(self.run.survival_seconds)}"

    def show_loading(self, level: int) -> None:
        self.loading_title.text = f"LOADING LEVEL {level}"
        self.loading_hint.text = "Generating maze and preloading geometry..."
        self.loading_root.enabled = True

    def hide_loading(self) -> None:
        self.loading_root.enabled = False

    def update(self) -> None:
        if self.run.running:
            self.hud_time.text = format_mmss(self.run.survival_seconds)
            if self.level_banner_timer > 0.0:
                self.level_banner_timer -= time.dt
                if self.level_banner_timer <= 0.0:
                    self.level_banner.enabled = False
