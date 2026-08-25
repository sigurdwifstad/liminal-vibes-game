from __future__ import annotations

import time as pytime
from dataclasses import dataclass

from ursina import Entity, Text, Vec3, camera, color, time, window

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


@dataclass(frozen=True)
class UIScreenLayout:
    aspect_ratio: float
    left_x: float
    right_x: float
    fullscreen_scale: Vec3


_DEFAULT_UI_ASPECT_RATIO = 16.0 / 9.0
_HUD_MARGIN_X = 0.03
_FULLSCREEN_OVERLAY_BLEED_X = 0.25
_FULLSCREEN_OVERLAY_BLEED_Y = 0.30


def _window_aspect_ratio() -> float:
    aspect_ratio = getattr(window, "aspect_ratio", None)
    if isinstance(aspect_ratio, (int, float)) and aspect_ratio > 0:
        return float(aspect_ratio)

    size = getattr(window, "size", None)
    if isinstance(size, (tuple, list)) and len(size) >= 2:
        width, height = size[0], size[1]
        if height:
            return float(width) / float(height)

    width = getattr(size, "x", None)
    height = getattr(size, "y", None)
    if isinstance(width, (int, float)) and isinstance(height, (int, float)) and height > 0:
        return float(width) / float(height)

    return _DEFAULT_UI_ASPECT_RATIO


def get_ui_screen_layout() -> UIScreenLayout:
    aspect_ratio = _window_aspect_ratio()
    half_width = aspect_ratio * 0.5
    return UIScreenLayout(
        aspect_ratio=aspect_ratio,
        left_x=-half_width + _HUD_MARGIN_X,
        right_x=half_width - _HUD_MARGIN_X,
        fullscreen_scale=Vec3(aspect_ratio + _FULLSCREEN_OVERLAY_BLEED_X, 1.0 + _FULLSCREEN_OVERLAY_BLEED_Y, 1),
    )


class GameStateUI:
    def __init__(self):
        self.run = RunState(running=True, start_time=pytime.time())
        self._last_layout_aspect_ratio: float | None = None
        self.hud_time = Text(text="00:00", position=(0, 0.45), scale=1.2, color=color.white)
        self.hud_level = Text(text="Level 1", position=(0, 0.40), scale=1.1, color=color.rgb(242, 242, 235))
        self.level_banner_timer = 0.0
        self.level_banner = Text(text="", position=(0, 0.22), origin=(0, 0), scale=1.9, color=color.rgb(240, 230, 170), enabled=False)
        self.level_intro = Text(
            text="WASD keys to move\nSHIFT to sprint",
            position=(0, 0.10),
            origin=(0, 0),
            scale=1.3,
            color=color.rgb(245, 245, 238),
            enabled=False,
        )
        self.level_intro_timer = 0.0
        self.level_intro_duration = 10.0

        self.game_over_root = Entity(parent=camera.ui, enabled=False)
        self.game_over_backdrop = Entity(
            parent=self.game_over_root,
            model="quad",
            position=Vec3(0, 0, 0.01),
            scale=Vec3(1, 1, 1),
            color=color.rgba(0, 0, 0, 0),
        )
        self.game_over_title = Text(
            parent=self.game_over_root,
            text="GAME OVER",
            position=(0, 0.1),
            origin=(0, 0),
            scale=3,
            color=color.rgb(255, 70, 70),
            enabled=False,
        )
        self.game_over_time = Text(
            parent=self.game_over_root,
            text="Survived: 00:00",
            position=(0, 0),
            origin=(0, 0),
            scale=1.6,
            color=color.white,
            enabled=False,
        )
        self.game_over_hint = Text(
            parent=self.game_over_root,
            text="Press R to restart, ESC to quit",
            position=(0, -0.08),
            origin=(0, 0),
            scale=1.2,
            color=color.rgb(230, 230, 230),
            enabled=False,
        )
        # After being caught on a regular level, the screen holds for a
        # few seconds, then fades to black; the restart/quit hint only
        # appears once the fade has fully finished (mirrors the level 10
        # "END GAME" fade sequence in `_update_endgame`).
        self.game_over_fade_timer = 0.0
        self.game_over_fade_delay = 3.0
        self.game_over_fade_duration = 1.5

        self.loading_root = Entity(parent=camera.ui, enabled=False)
        self.loading_backdrop = Entity(
            parent=self.loading_root,
            model="quad",
            position=Vec3(0, 0, 0),
            scale=Vec3(1, 1, 1),
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

        # Level 10's finale: player-monster catches the fleeing child, the
        # screen freezes and fades to black behind an "END GAME" title.
        self.endgame_active = False
        self.endgame_fade_timer = 0.0
        self.endgame_fade_duration = 2.5
        self.endgame_hold_seconds = 3.5
        self.endgame_finished = False
        self.endgame_root = Entity(parent=camera.ui, enabled=False)
        self.endgame_backdrop = Entity(
            parent=self.endgame_root,
            model="quad",
            position=Vec3(0, 0, 0),
            scale=Vec3(1, 1, 1),
            color=color.rgba(0, 0, 0, 0),
        )
        self.endgame_text = Text(
            parent=self.endgame_root,
            text="END OF GAME",
            position=(0, 0.05),
            origin=(0, 0),
            scale=4,
            color=color.white,
            enabled=False,
        )
        self.endgame_hint = Text(
            parent=self.endgame_root,
            text="Press R to restart, ESC to quit",
            position=(0, -0.12),
            origin=(0, 0),
            scale=1.2,
            color=color.rgb(230, 230, 230),
            enabled=False,
        )

        self.level9_transition_messages = (
            "You feel the cold embrace of the creature.",
            "At first, an immense darkness overwhelms you.",
            "But then, a sense of calmness rushes over you.",
            "It seems you have come home at last.",
            "And you see the world from a new perspective.",
        )
        self.level9_transition_fade_duration = 1.5
        self.level9_transition_black_hold_seconds = 3.0
        self.level9_transition_sentence_duration = 3.0
        self.level9_transition_reveal_duration = 1.5
        self.level9_transition_active = False
        self.level9_transition_request_level_load = False
        self.level9_transition_level_loaded = False
        self.level9_transition_finished = False
        self.level9_transition_elapsed = 0.0
        self.level9_transition_reveal_timer = 0.0
        self.level9_transition_root = Entity(parent=camera.ui, enabled=False)
        self.level9_transition_backdrop = Entity(
            parent=self.level9_transition_root,
            model="quad",
            position=Vec3(0, 0, 0.02),
            scale=Vec3(1, 1, 1),
            color=color.rgba(0, 0, 0, 0),
        )
        self.level9_transition_text = Text(
            parent=self.level9_transition_root,
            text="",
            position=(0, 0.02),
            origin=(0, 0),
            scale=1.15,
            color=color.rgb(240, 240, 235),
            enabled=False,
        )
        self.refresh_layout(force=True)

    def refresh_layout(self, force: bool = False) -> None:
        layout = get_ui_screen_layout()
        if not force and self._last_layout_aspect_ratio is not None and abs(layout.aspect_ratio - self._last_layout_aspect_ratio) < 0.001:
            return

        self._last_layout_aspect_ratio = layout.aspect_ratio
        self.hud_time.position = (layout.left_x, 0.45)
        self.hud_level.position = (layout.left_x, 0.40)
        self.game_over_backdrop.scale = layout.fullscreen_scale
        self.loading_backdrop.scale = layout.fullscreen_scale
        self.endgame_backdrop.scale = layout.fullscreen_scale
        self.level9_transition_backdrop.scale = layout.fullscreen_scale

    def start_new_run(self, level: int = 1) -> None:
        self.run.running = True
        self.run.start_time = pytime.time()
        self.run.end_time = 0.0
        self.run.level = level
        self.loading_root.enabled = False
        self.game_over_root.enabled = False
        self.game_over_backdrop.color = color.rgba(0, 0, 0, 0)
        self.game_over_title.enabled = False
        self.game_over_time.enabled = False
        self.game_over_hint.enabled = False
        self.game_over_fade_timer = 0.0
        self.endgame_active = False
        self.endgame_finished = False
        self.endgame_root.enabled = False
        self.endgame_hint.enabled = False
        self._reset_level9_transition()
        self.hud_time.enabled = True
        self.hud_level.enabled = True
        self.hud_time.text = "00:00"
        self.hud_level.text = f"Level {self.run.level}"
        self.level_banner.enabled = False
        self.level_banner_timer = 0.0
        self.level_intro.enabled = level == 1
        self.level_intro_timer = self.level_intro_duration if level == 1 else 0.0

    def set_level(self, level: int) -> None:
        self.run.level = level
        self.hud_level.text = f"Level {level}"
        if level != 1:
            self.level_intro.enabled = False
            self.level_intro_timer = 0.0

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
        self.game_over_backdrop.color = color.rgba(0, 0, 0, 0)
        self.game_over_title.enabled = False
        self.game_over_time.enabled = False
        self.game_over_hint.enabled = False
        self.game_over_fade_timer = 0.0
        self.game_over_time.text = f"Survived: {format_mmss(self.run.survival_seconds)}"

    def on_endgame_caught(self) -> None:
        """Level 10's finale: the player-monster has caught the child. Freeze
        the run and start the freeze/fade-to-black/"END GAME" sequence (see
        `_update_endgame`); the caller is responsible for triggering the
        `endgame.mp3` audio cue once (via `AudioManager.play_endgame`). The
        screen then holds indefinitely -- the run stays frozen until the
        player presses R (restart, handled generically since `run.running`
        is False) or ESC (quit)."""
        self.run.running = False
        self.run.end_time = pytime.time()
        self.hud_time.enabled = False
        self.hud_level.enabled = False
        self.level_banner.enabled = False
        self.loading_root.enabled = False
        self.game_over_root.enabled = False
        self.endgame_active = True
        self.endgame_finished = False
        self.endgame_fade_timer = 0.0
        self.endgame_backdrop.color = color.rgba(0, 0, 0, 0)
        self.endgame_text.enabled = False
        self.endgame_hint.enabled = False
        self.endgame_root.enabled = True

    def start_level9_transition(self) -> None:
        self.hud_time.enabled = False
        self.hud_level.enabled = False
        self.level_banner.enabled = False
        self.level_intro.enabled = False
        self.loading_root.enabled = False
        self.game_over_root.enabled = False
        self.endgame_root.enabled = False
        self.level9_transition_active = True
        self.level9_transition_request_level_load = False
        self.level9_transition_level_loaded = False
        self.level9_transition_finished = False
        self.level9_transition_elapsed = 0.0
        self.level9_transition_reveal_timer = 0.0
        self.level9_transition_backdrop.color = color.rgba(0, 0, 0, 0)
        self.level9_transition_text.text = ""
        self.level9_transition_text.enabled = False
        self.level9_transition_root.enabled = True

    def mark_level9_transition_level_loaded(self) -> None:
        self.level9_transition_level_loaded = True
        self.level9_transition_request_level_load = False
        self.level9_transition_reveal_timer = 0.0
        self.level9_transition_text.text = ""
        self.level9_transition_text.enabled = False
        self.level9_transition_backdrop.color = color.rgba(0, 0, 0, 255)

    def complete_level9_transition(self) -> None:
        self._reset_level9_transition()
        self.hud_time.enabled = True
        self.hud_level.enabled = True

    def show_loading(self, level: int) -> None:
        self.loading_title.text = f"LOADING LEVEL {level}"
        self.loading_hint.text = "Generating maze and preloading geometry..."
        self.loading_root.enabled = True

    def hide_loading(self) -> None:
        self.loading_root.enabled = False

    def update(self) -> None:
        self.refresh_layout()
        if self.level9_transition_active:
            self._update_level9_transition()
            return

        if self.level_intro.enabled and self.level_intro_timer <= 0.0:
            self.level_intro.enabled = False
            self.level_intro_timer = 0.0

        if self.level_intro_timer > 0.0:
            self.level_intro_timer -= time.dt
            if self.level_intro_timer <= 0.0:
                self.level_intro.enabled = False
                self.level_intro_timer = 0.0

        if self.run.running:
            self.hud_time.text = format_mmss(self.run.survival_seconds)
            if self.level_banner_timer > 0.0:
                self.level_banner_timer -= time.dt
                if self.level_banner_timer <= 0.0:
                    self.level_banner.enabled = False
        elif self.game_over_root.enabled and not self.game_over_hint.enabled:
            self._update_game_over()
        elif self.endgame_active and not self.endgame_finished:
            self._update_endgame()

    def _update_game_over(self) -> None:
        self.game_over_fade_timer += time.dt
        fade_elapsed = self.game_over_fade_timer - self.game_over_fade_delay
        if fade_elapsed <= 0.0:
            return

        fade_progress = max(0.0, min(1.0, fade_elapsed / self.game_over_fade_duration))
        self.game_over_backdrop.color = color.rgba(0, 0, 0, round(255 * fade_progress))
        if fade_progress >= 1.0:
            self.game_over_title.enabled = True
            self.game_over_time.enabled = True
            self.game_over_hint.enabled = True

    def _update_endgame(self) -> None:
        self.endgame_fade_timer += time.dt
        fade_progress = max(0.0, min(1.0, self.endgame_fade_timer / self.endgame_fade_duration))
        self.endgame_backdrop.color = color.rgba(0, 0, 0, round(255 * fade_progress))

        if fade_progress >= 1.0 and not self.endgame_text.enabled:
            self.endgame_text.enabled = True

        if self.endgame_fade_timer >= self.endgame_fade_duration + self.endgame_hold_seconds:
            # The fade/reveal animation is done; the "END GAME" screen now
            # holds indefinitely until the player presses R or ESC (handled
            # by the generic input() restart/quit logic in main.py).
            self.endgame_hint.enabled = True
            self.endgame_finished = True

    def _update_level9_transition(self) -> None:
        if not self.level9_transition_level_loaded:
            self.level9_transition_elapsed += time.dt
            fade_progress = max(0.0, min(1.0, self.level9_transition_elapsed / self.level9_transition_fade_duration))
            self.level9_transition_backdrop.color = color.rgba(0, 0, 0, round(255 * fade_progress))

            if self.level9_transition_elapsed < self.level9_transition_black_hold_seconds:
                self.level9_transition_text.enabled = False
                return

            sentence_elapsed = self.level9_transition_elapsed - self.level9_transition_black_hold_seconds
            total_sentence_duration = self.level9_transition_sentence_duration * len(self.level9_transition_messages)
            if sentence_elapsed < total_sentence_duration:
                index = min(int(sentence_elapsed / self.level9_transition_sentence_duration), len(self.level9_transition_messages) - 1)
                self.level9_transition_text.text = self.level9_transition_messages[index]
                self.level9_transition_text.enabled = True
                self.level9_transition_backdrop.color = color.rgba(0, 0, 0, 255)
                return

            self.level9_transition_text.text = ""
            self.level9_transition_text.enabled = False
            self.level9_transition_backdrop.color = color.rgba(0, 0, 0, 255)
            self.level9_transition_request_level_load = True
            return

        self.level9_transition_reveal_timer += time.dt
        fade_progress = max(0.0, min(1.0, self.level9_transition_reveal_timer / self.level9_transition_reveal_duration))
        self.level9_transition_backdrop.color = color.rgba(0, 0, 0, round(255 * (1.0 - fade_progress)))
        if fade_progress >= 1.0:
            self.level9_transition_finished = True

    def _reset_level9_transition(self) -> None:
        self.level9_transition_active = False
        self.level9_transition_request_level_load = False
        self.level9_transition_level_loaded = False
        self.level9_transition_finished = False
        self.level9_transition_elapsed = 0.0
        self.level9_transition_reveal_timer = 0.0
        self.level9_transition_root.enabled = False
        self.level9_transition_backdrop.color = color.rgba(0, 0, 0, 0)
        self.level9_transition_text.text = ""
        self.level9_transition_text.enabled = False
