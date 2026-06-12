from __future__ import annotations

from ursina import Entity, Vec3, camera, clamp, held_keys, mouse, raycast, time

from audio import get_audio_manager


class PlayerController(Entity):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.walk_speed = 6.0
        self.sprint_multiplier = 1.65
        self.height = 1.7
        self.collider_radius = 0.45
        self.look_speed = 110.0
        self.pitch = 0.0
        self.cursor_locked = True
        self.enabled = True
        self.stamina_max = 5.0
        self.stamina = self.stamina_max
        self.stamina_drain_rate = 1.35
        self.stamina_refill_rate = 0.95
        self.sprinting = False

        self.audio = get_audio_manager()

        camera.parent = self
        camera.position = Vec3(0, self.height, 0)
        camera.rotation = (0, 0, 0)
        mouse.locked = False
        mouse.visible = True

    def set_active(self, active: bool) -> None:
        self.enabled = active
        self.cursor_locked = active
        mouse.locked = False
        mouse.visible = True

    def update(self):
        if not self.enabled:
            return

        yaw_input = held_keys["right arrow"] - held_keys["left arrow"]
        pitch_input = held_keys["up arrow"] - held_keys["down arrow"]

        self.rotation_y += yaw_input * self.look_speed * time.dt
        self.pitch = clamp(self.pitch + pitch_input * self.look_speed * time.dt, -89, 89)
        camera.rotation_x = self.pitch

        forward_input = held_keys["w"] - held_keys["s"]
        strafe_input = held_keys["d"] - held_keys["a"]

        move_direction = (self.forward * forward_input + self.right * strafe_input)
        moving = move_direction.length() > 0
        if moving:
            move_direction = move_direction.normalized()

        sprint_key = held_keys["shift"] or held_keys["left shift"] or held_keys["right shift"]
        can_sprint = sprint_key and moving and self.stamina > 0.05
        self.sprinting = bool(can_sprint)
        if self.sprinting:
            speed = self.walk_speed * self.sprint_multiplier
            self.stamina = max(0.0, self.stamina - self.stamina_drain_rate * time.dt)
        else:
            speed = self.walk_speed
            self.stamina = min(self.stamina_max, self.stamina + self.stamina_refill_rate * time.dt)

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

