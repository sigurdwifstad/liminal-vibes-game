from __future__ import annotations

import time as pytime
from dataclasses import dataclass

from ursina import Entity, Text, color, time

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

    def start_new_run(self, level: int = 1) -> None:
        self.run.running = True
        self.run.start_time = pytime.time()
        self.run.end_time = 0.0
        self.run.level = level
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
        self.game_over_root.enabled = True
        self.game_over_time.text = f"Survived: {format_mmss(self.run.survival_seconds)}"

    def update(self) -> None:
        if self.run.running:
            self.hud_time.text = format_mmss(self.run.survival_seconds)
            if self.level_banner_timer > 0.0:
                self.level_banner_timer -= time.dt
                if self.level_banner_timer <= 0.0:
                    self.level_banner.enabled = False
