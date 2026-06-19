from __future__ import annotations

from ursina import Entity, Vec3, camera, clamp, held_keys, mouse, raycast, time

from audio import get_audio_manager
from core_logic import adjust_fov


class PlayerController(Entity):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.walk_speed = 6.0
        self.exhausted_walk_speed = 2.0
        self.sprint_multiplier = 1.65
        self.height = 1.7
        self.collider_radius = 0.45
        self.look_speed = 200.0
        self.mouse_look_speed = 200.0
        self.mouse_sensitivity_step = 10.0
        self.mouse_sensitivity_min = 20.0
        self.mouse_sensitivity_max = 220.0
        self.invert_y = False
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

        self.audio = get_audio_manager()

        camera.parent = self
        camera.position = Vec3(0, self.height, 0)
        camera.rotation = (0, 0, 0)
        camera.fov = self.default_fov
        mouse.locked = True
        mouse.visible = False

    def set_active(self, active: bool) -> None:
        self.enabled = active
        self.cursor_locked = active
        mouse.locked = active
        mouse.visible = not active
        if not active and self.audio.footstep_playing:
            self.audio.stop_footstep_loop()
        if active:
            camera.fov = self.user_fov

    def update(self):
        if not self.enabled:
            return

        yaw_input = held_keys["right arrow"] - held_keys["left arrow"]
        pitch_input = held_keys["up arrow"] - held_keys["down arrow"]
        fov_input = held_keys["e"] - held_keys["q"]
        mouse_x, mouse_y = self._xy_from_input(mouse.velocity)

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

    @staticmethod
    def _xy_from_input(value: object) -> tuple[float, float]:
        if hasattr(value, "x") and hasattr(value, "y"):
            return float(getattr(value, "x")), float(getattr(value, "y"))
        if isinstance(value, (tuple, list)) and len(value) >= 2:
            return float(value[0]), float(value[1])
        return 0.0, 0.0

    def input(self, key: str) -> None:
        if key == "i":
            self.invert_y = not self.invert_y
            return
        if key == "o":
            self.mouse_look_speed = max(self.mouse_sensitivity_min, self.mouse_look_speed - self.mouse_sensitivity_step)
            return
        if key == "p":
            self.mouse_look_speed = min(self.mouse_sensitivity_max, self.mouse_look_speed + self.mouse_sensitivity_step)