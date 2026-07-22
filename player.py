from __future__ import annotations

from typing import TYPE_CHECKING

from ursina import Entity, Vec3, application, camera, clamp, held_keys, mouse, raycast, time

from audio import get_audio_manager
from core_logic import adjust_fov

if TYPE_CHECKING:
    from maze import MazeManager


class PlayerController(Entity):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.walk_speed = 6.0
        self.exhausted_walk_speed = 2.0
        self.sprint_multiplier = 1.65
        self.height = 1.7
        self.collider_radius = 0.45
        self.look_speed = 200.0
        self.mouse_look_speed = 0.16
        self.mouse_sensitivity_step = 0.02
        self.mouse_sensitivity_min = 0.04
        self.mouse_sensitivity_max = 0.60
        self.mouse_deadzone_pixels = 0.5
        self.invert_y = True
        self.fov_adjust_speed = 34.0
        self.fov_smooth_speed = 10.0
        self.sprint_fov_kick = 6.5
        self.min_fov = 55.0
        self.max_fov = 110.0
        self.default_fov = 86.0
        self.user_fov = self.default_fov
        self.pitch = 0.0
        self.cursor_locked = True
        self.enabled = True
        self.stamina_max = 5.0
        self.stamina = self.stamina_max
        self.stamina_drain_rate = 1.35
        self.stamina_refill_rate = 0.95
        self.sprinting = False
        self.exhausted = False  # True from stamina=0 until fully refilled
        self.current_maze: MazeManager | None = None
        self._mouse_pointer_centered = False
        self._mouse_bias_x = 0.0
        self._mouse_bias_y = 0.0

        self.audio = get_audio_manager()

        camera.parent = self
        camera.position = Vec3(0, self.height, 0)
        camera.rotation = (0, 0, 0)
        camera.fov = self.default_fov
        mouse.locked = False
        mouse.visible = False

    def set_active(self, active: bool) -> None:
        self.enabled = active
        self.cursor_locked = active
        mouse.locked = False
        mouse.visible = not active
        self._mouse_pointer_centered = False
        self._mouse_bias_x = 0.0
        self._mouse_bias_y = 0.0
        if active:
            self._center_pointer()
        if not active and self.audio.footstep_playing:
            self.audio.stop_footstep_loop()
        if active:
            camera.fov = self.user_fov

    def set_maze(self, maze: MazeManager | None) -> None:
        self.current_maze = maze

    def update(self):
        if not self.enabled:
            return

        yaw_input = held_keys["right arrow"] - held_keys["left arrow"]
        pitch_input = held_keys["up arrow"] - held_keys["down arrow"]
        fov_input = held_keys["e"] - held_keys["q"]
        mouse_x, mouse_y = self._mouse_delta_pixels()

        self.rotation_y += yaw_input * self.look_speed * time.dt + mouse_x * self.mouse_look_speed
        mouse_pitch_dir = 1.0 if self.invert_y else -1.0
        self.pitch = clamp(
            self.pitch + pitch_input * self.look_speed * time.dt + mouse_y * self.mouse_look_speed * mouse_pitch_dir,
            -89,
            89,
        )
        camera.rotation_x = self.pitch
        self.user_fov = adjust_fov(
            self.user_fov,
            fov_input,
            time.dt,
            speed=self.fov_adjust_speed,
            min_fov=self.min_fov,
            max_fov=self.max_fov,
        )

        forward_input = held_keys["w"] - held_keys["s"]
        strafe_input = held_keys["d"] - held_keys["a"]

        move_direction = (self.forward * forward_input + self.right * strafe_input)
        moving = move_direction.length() > 0
        if moving:
            move_direction = move_direction.normalized()

        sprint_key = held_keys["shift"] or held_keys["left shift"] or held_keys["right shift"]
        can_sprint = sprint_key and moving and self.stamina > 0.0 and not self.exhausted
        self.sprinting = bool(can_sprint)
        if self.sprinting:
            speed = self.walk_speed * self.sprint_multiplier
            self.stamina = max(0.0, self.stamina - self.stamina_drain_rate * time.dt)
            if self.stamina <= 0.0:
                self.exhausted = True
                self.sprinting = False
                speed = self.exhausted_walk_speed
        else:
            speed = self.walk_speed if not self.exhausted else self.exhausted_walk_speed
            self.stamina = min(self.stamina_max, self.stamina + self.stamina_refill_rate * time.dt)
            if self.exhausted and self.stamina >= self.stamina_max:
                self.exhausted = False

        target_fov = self.user_fov + (self.sprint_fov_kick if self.sprinting else 0.0)
        blend = min(1.0, max(0.0, self.fov_smooth_speed * time.dt))
        camera.fov += (target_fov - camera.fov) * blend

        # Handle footstep sounds - loop while moving, stop when not moving
        if moving:
            if not self.audio.footstep_playing:
                self.audio.play_footstep_loop()
        else:
            if self.audio.footstep_playing:
                self.audio.stop_footstep_loop()

        step = move_direction * speed * time.dt
        self._try_move(Vec3(step.x, 0, 0))
        self._try_move(Vec3(0, 0, step.z))

    @property
    def stamina_ratio(self) -> float:
        if self.stamina_max <= 0:
            return 0.0
        return max(0.0, min(1.0, self.stamina / self.stamina_max))

    def _try_move(self, delta: Vec3) -> None:
        if delta.length() <= 0:
            return

        if self.current_maze is not None:
            candidate = self.position + delta
            if self._can_occupy(candidate):
                self.position = candidate
            return

        direction = delta.normalized()
        probe_origin = self.world_position + Vec3(0, 1.0, 0)
        hit = raycast(
            probe_origin,
            direction,
            distance=delta.length() + self.collider_radius,
            ignore=(self,),
        )
        if not hit.hit:
            self.position += delta

    def _can_occupy(self, candidate_position: Vec3) -> bool:
        maze = self.current_maze
        if maze is None:
            return True

        # Sample center + perimeter points to approximate circular collider occupancy.
        r = self.collider_radius * 0.92
        diagonal = r * 0.7
        probes = (
            (0.0, 0.0),
            (r, 0.0),
            (-r, 0.0),
            (0.0, r),
            (0.0, -r),
            (diagonal, diagonal),
            (diagonal, -diagonal),
            (-diagonal, diagonal),
            (-diagonal, -diagonal),
        )
        for ox, oz in probes:
            probe = Vec3(candidate_position.x + ox, 0.0, candidate_position.z + oz)
            if not maze.is_walkable_cell(maze.cell_from_world(probe)):
                return False
        return True

    @staticmethod
    def _xy_from_input(value: object) -> tuple[float, float]:
        if hasattr(value, "x") and hasattr(value, "y"):
            return float(getattr(value, "x")), float(getattr(value, "y"))
        if hasattr(value, "get_x") and hasattr(value, "get_y"):
            return float(getattr(value, "get_x")()), float(getattr(value, "get_y")())
        if hasattr(value, "getX") and hasattr(value, "getY"):
            return float(getattr(value, "getX")()), float(getattr(value, "getY")())
        if isinstance(value, (tuple, list)) and len(value) >= 2:
            return float(value[0]), float(value[1])
        return 0.0, 0.0

    def _get_window(self):
        base = getattr(application, "base", None)
        if base is None:
            return None
        return getattr(base, "win", None)

    def _window_size(self) -> tuple[float, float]:
        win = self._get_window()
        if win is None:
            return 0.0, 0.0
        props = win.get_properties()
        if hasattr(props, "get_x_size") and hasattr(props, "get_y_size"):
            return float(props.get_x_size()), float(props.get_y_size())
        if hasattr(props, "getXSize") and hasattr(props, "getYSize"):
            return float(props.getXSize()), float(props.getYSize())
        return 0.0, 0.0

    def _center_pointer(self) -> None:
        win = self._get_window()
        width, height = self._window_size()
        if win is None or width <= 0.0 or height <= 0.0:
            return
        win.move_pointer(0, int(width * 0.5), int(height * 0.5))
        self._mouse_pointer_centered = True

    def _mouse_delta_pixels(self) -> tuple[float, float]:
        win = self._get_window()
        if win is None:
            return 0.0, 0.0

        width, height = self._window_size()
        if width <= 0.0 or height <= 0.0:
            return 0.0, 0.0

        center_x = width * 0.5
        center_y = height * 0.5

        if not self._mouse_pointer_centered:
            self._center_pointer()
            return 0.0, 0.0

        pointer = win.get_pointer(0)
        x, y = self._xy_from_input(pointer)
        dx = x - center_x
        dy = y - center_y

        # Gradually cancel the small warp-feedback residue from the backend/window manager.
        if abs(dx) <= self.mouse_deadzone_pixels and abs(dy) <= self.mouse_deadzone_pixels:
            self._mouse_bias_x = self._mouse_bias_x * 0.9 + dx * 0.1
            self._mouse_bias_y = self._mouse_bias_y * 0.9 + dy * 0.1

        dx -= self._mouse_bias_x
        dy -= self._mouse_bias_y

        if abs(dx) < self.mouse_deadzone_pixels:
            dx = 0.0
        if abs(dy) < self.mouse_deadzone_pixels:
            dy = 0.0

        win.move_pointer(0, int(center_x), int(center_y))
        return dx, dy

    def input(self, key: str) -> None:
        if key == "i":
            self.invert_y = not self.invert_y
            return
        if key == "o":
            self.mouse_look_speed = max(self.mouse_sensitivity_min, self.mouse_look_speed - self.mouse_sensitivity_step)
            return
        if key == "p":
            self.mouse_look_speed = min(self.mouse_sensitivity_max, self.mouse_look_speed + self.mouse_sensitivity_step)