from __future__ import annotations

from pathlib import Path
import random
import time
from typing import Optional

import pygame


def can_play_after_cooldown(last_played_at: Optional[float], current_time: float, cooldown_seconds: float) -> bool:
    if last_played_at is None:
        return True
    return (current_time - last_played_at) >= cooldown_seconds


def clamp_volume(volume: float) -> float:
    return max(0.0, min(1.0, float(volume)))


class AudioManager:
    def __init__(self, ambient_volume: float = 1.0, sfx_volume: float = 0.3):
        self.ambient_volume = clamp_volume(ambient_volume)
        self.sfx_volume = clamp_volume(sfx_volume)
        self.footstep_sprint_playback_rate = 1.4
        # Initialize pygame mixer
        try:
            pygame.mixer.init(buffer=512)
        except Exception as e:
            # Handle case where mixer can't initialize
            print(f"Warning: Pygame mixer init failed: {e}")
            self.available = False
            self.ambient_sound = None
            self.footstep_sound = None
            self.monster_appearing_sound = None
            self.monster_scream_sounds = []
            self.spider_walking_sound = None
            self.spider_attack_sound = None
            self.intense_sequence_sound = None
            self.dark_drone_sound = None
            self.einkvan_sounds = []
            self.exhausted_sound = None
            self.ambient_channel = None
            self.footstep_channel = None
            self.monster_appearing_channel = None
            self.monster_scream_channel = None
            self.spider_walking_channel = None
            self.spider_attack_channel = None
            self.intense_sequence_channel = None
            self.dark_drone_channel = None
            self.einkvan_channel = None
            self.exhausted_channel = None
            self.footstep_sprint_sound = None
            self.footstep_sprinting = False
            self._last_monster_scream_index = None
            self.ambient_playing = False
            self.footstep_playing = False
            self.spider_walking_playing = False
            self.dark_drone_playing = False
            self._einkvan_index = -1
            self.einkvan_sequence_finished = False
            self._einkvan_start_at: Optional[float] = None
            self.einkvan_lead_in_seconds = 10.0
            self.monster_appearing_cooldown_seconds = 10.0
            self.last_monster_appearing_at = None
            self.monster_scream_cooldown_seconds = 2.8
            self.last_monster_scream_at = None
            self.spider_attack_cooldown_seconds = 0.8
            self.last_spider_attack_at = None
            return

        self.available = True
        self.resources_path = Path(__file__).parent / "resources"

        # Music/ambient track - use pygame.mixer.music for better looping
        self.ambient_channel = None
        self.ambient_playing = False
        self.ambient_sound = None

        # Footstep sounds - will use a dedicated channel for looping
        self.footstep_channel = None
        self.footstep_sound = None
        self.footstep_sprint_sound = None
        self.footstep_sprinting = False
        self.footstep_playing = False

        self.monster_appearing_channel = None
        self.monster_appearing_sound = None
        self.monster_scream_channel = None
        self.monster_scream_sounds = []
        self.spider_walking_channel = None
        self.spider_walking_sound = None
        self.spider_walking_playing = False
        self.spider_attack_channel = None
        self.spider_attack_sound = None
        self.intense_sequence_channel = None
        self.intense_sequence_sound = None
        self.dark_drone_channel = None
        self.dark_drone_sound = None
        self.dark_drone_playing = False
        self.einkvan_channel = None
        self.einkvan_sounds = []
        self.exhausted_channel = None
        self.exhausted_sound = None
        self._einkvan_index = -1
        self.einkvan_sequence_finished = False
        self._einkvan_start_at: Optional[float] = None
        self.einkvan_lead_in_seconds = 10.0
        self._last_monster_scream_index: Optional[int] = None
        self.monster_appearing_cooldown_seconds = 10.0
        self.last_monster_appearing_at: Optional[float] = None
        self.monster_scream_cooldown_seconds = 2.8
        self.last_monster_scream_at: Optional[float] = None
        self.spider_attack_cooldown_seconds = 0.8
        self.last_spider_attack_at: Optional[float] = None

        self._load_sounds()

    def _load_sounds(self) -> None:
        if not self.available:
            return

        try:
            ambient_path = self.resources_path / "ambient.wav"
            if ambient_path.exists():
                # For music, we'll use the path directly with pygame.mixer.music
                self.ambient_sound = str(ambient_path)
                print(f"Loaded ambient sound from {ambient_path}")
            else:
                print(f"Warning: Ambient sound not found at {ambient_path}")
                self.ambient_sound = None

            footstep_path = self.resources_path / "footsteps.mp3"
            if footstep_path.exists():
                self.footstep_sound = pygame.mixer.Sound(str(footstep_path))
                self.footstep_sound.set_volume(self.sfx_volume)
                self.footstep_sprint_sound = self._build_playback_rate_sound(
                    self.footstep_sound, self.footstep_sprint_playback_rate
                )
                print(f"Loaded footstep sound from {footstep_path}")
            else:
                print(f"Warning: Footstep sound not found at {footstep_path}")
                self.footstep_sound = None
                self.footstep_sprint_sound = None

            monster_appearing_path = self.resources_path / "monster_appearing.mp3"
            if monster_appearing_path.exists():
                self.monster_appearing_sound = pygame.mixer.Sound(str(monster_appearing_path))
                self.monster_appearing_sound.set_volume(self.sfx_volume)
                print(f"Loaded monster appearing sound from {monster_appearing_path}")
            else:
                print(f"Warning: Monster appearing sound not found at {monster_appearing_path}")
                self.monster_appearing_sound = None

            self.monster_scream_sounds = []
            for index in range(1, 4):
                monster_scream_path = self.resources_path / f"monster_scream_{index}.mp3"
                if not monster_scream_path.exists():
                    print(f"Warning: Monster scream sound not found at {monster_scream_path}")
                    continue

                scream_sound = pygame.mixer.Sound(str(monster_scream_path))
                scream_sound.set_volume(self.sfx_volume)
                self.monster_scream_sounds.append(scream_sound)
                print(f"Loaded monster scream sound from {monster_scream_path}")

            spider_walking_path = self.resources_path / "spider_walking.mp3"
            if spider_walking_path.exists():
                self.spider_walking_sound = pygame.mixer.Sound(str(spider_walking_path))
                self.spider_walking_sound.set_volume(self.sfx_volume)
                print(f"Loaded spider walking sound from {spider_walking_path}")
            else:
                print(f"Warning: Spider walking sound not found at {spider_walking_path}")
                self.spider_walking_sound = None

            spider_attack_path = self.resources_path / "spider_attack.mp3"
            if spider_attack_path.exists():
                self.spider_attack_sound = pygame.mixer.Sound(str(spider_attack_path))
                self.spider_attack_sound.set_volume(self.sfx_volume)
                print(f"Loaded spider attack sound from {spider_attack_path}")
            else:
                print(f"Warning: Spider attack sound not found at {spider_attack_path}")
                self.spider_attack_sound = None

            intense_sequence_path = self.resources_path / "intense_sequence.mp3"
            if intense_sequence_path.exists():
                self.intense_sequence_sound = pygame.mixer.Sound(str(intense_sequence_path))
                self.intense_sequence_sound.set_volume(self.sfx_volume)
                print(f"Loaded intense sequence sound from {intense_sequence_path}")
            else:
                print(f"Warning: Intense sequence sound not found at {intense_sequence_path}")
                self.intense_sequence_sound = None

            dark_drone_path = self.resources_path / "dark_drone.mp3"
            if dark_drone_path.exists():
                self.dark_drone_sound = pygame.mixer.Sound(str(dark_drone_path))
                self.dark_drone_sound.set_volume(self.sfx_volume*1.5)  # Slightly louder for ambiencew
                print(f"Loaded dark drone sound from {dark_drone_path}")
            else:
                print(f"Warning: Dark drone sound not found at {dark_drone_path}")
                self.dark_drone_sound = None

            self.einkvan_sounds = []
            for index in range(1, 5):
                einkvan_path = self.resources_path / f"einkvan_{index}.wav"
                if not einkvan_path.exists():
                    print(f"Warning: Einkvan sound not found at {einkvan_path}")
                    continue

                einkvan_sound = pygame.mixer.Sound(str(einkvan_path))
                einkvan_sound.set_volume(self.sfx_volume)
                self.einkvan_sounds.append(einkvan_sound)
                print(f"Loaded einkvan sound from {einkvan_path}")

            exhausted_path = self.resources_path / "exhausted.mp3"
            if exhausted_path.exists():
                self.exhausted_sound = pygame.mixer.Sound(str(exhausted_path))
                self.exhausted_sound.set_volume(self.sfx_volume)
                print(f"Loaded exhausted sound from {exhausted_path}")
            else:
                print(f"Warning: Exhausted sound not found at {exhausted_path}")
                self.exhausted_sound = None
        except Exception as e:
            print(f"Warning: Could not load audio files: {e}")
            self.ambient_sound = None
            self.footstep_sound = None
            self.footstep_sprint_sound = None
            self.monster_appearing_sound = None
            self.monster_scream_sounds = []
            self.spider_walking_sound = None
            self.spider_attack_sound = None
            self.intense_sequence_sound = None
            self.dark_drone_sound = None
            self.einkvan_sounds = []
            self.exhausted_sound = None

    def _current_footstep_sound(self):
        if self.footstep_sprinting and self.footstep_sprint_sound is not None:
            return self.footstep_sprint_sound
        return self.footstep_sound

    def _build_playback_rate_sound(self, source_sound, playback_rate: float):
        if playback_rate <= 1.0:
            return None
        if not hasattr(source_sound, "get_raw"):
            return None
        if not hasattr(pygame.mixer, "get_init"):
            return None

        mixer_init = pygame.mixer.get_init()
        if not mixer_init:
            return None

        try:
            _frequency, sample_format, channel_count = mixer_init
            sample_width = abs(int(sample_format)) // 8
            frame_size = sample_width * int(channel_count)
            if frame_size <= 0:
                return None

            source_bytes = source_sound.get_raw()
            frame_count = len(source_bytes) // frame_size
            if frame_count < 2:
                return None

            sped_up_frame_count = max(1, int(frame_count / playback_rate))
            sped_up_bytes = bytearray(sped_up_frame_count * frame_size)
            for dest_frame in range(sped_up_frame_count):
                src_frame = min(frame_count - 1, int(dest_frame * playback_rate))
                src_start = src_frame * frame_size
                src_end = src_start + frame_size
                dest_start = dest_frame * frame_size
                sped_up_bytes[dest_start : dest_start + frame_size] = source_bytes[src_start:src_end]

            sprint_sound = pygame.mixer.Sound(buffer=bytes(sped_up_bytes))
            sprint_sound.set_volume(self.sfx_volume)
            return sprint_sound
        except Exception:
            return None

    def play_ambient_loop(self) -> None:
        """Play ambient sound in a loop using pygame.mixer.music"""
        if not self.available or self.ambient_sound is None:
            return

        if not self.ambient_playing:
            try:
                # Use pygame.mixer.music for continuous looping
                pygame.mixer.music.load(self.ambient_sound)
                pygame.mixer.music.set_volume(self.ambient_volume)
                pygame.mixer.music.play(loops=-1)  # -1 means loop forever
                self.ambient_playing = True
                print("Ambient sound started (using music)")
            except Exception as e:
                print(f"Warning: Failed to play ambient sound: {e}")
                self.ambient_playing = False

    def set_ambient_volume(self, volume: float) -> None:
        self.ambient_volume = clamp_volume(volume)
        if not self.available:
            return
        try:
            pygame.mixer.music.set_volume(self.ambient_volume)
        except Exception as e:
            print(f"Warning: Failed to set ambient sound volume: {e}")

    def set_sfx_volume(self, volume: float) -> None:
        self.sfx_volume = clamp_volume(volume)
        if self.footstep_sound is not None:
            self.footstep_sound.set_volume(self.sfx_volume)
        if self.footstep_sprint_sound is not None:
            self.footstep_sprint_sound.set_volume(self.sfx_volume)
        if self.monster_appearing_sound is not None:
            self.monster_appearing_sound.set_volume(self.sfx_volume)
        for scream_sound in self.monster_scream_sounds:
            scream_sound.set_volume(self.sfx_volume)
        if self.spider_walking_sound is not None:
            self.spider_walking_sound.set_volume(self.sfx_volume)
        if self.spider_attack_sound is not None:
            self.spider_attack_sound.set_volume(self.sfx_volume)
        if self.intense_sequence_sound is not None:
            self.intense_sequence_sound.set_volume(self.sfx_volume)

    def stop_ambient(self) -> None:
        """Stop the ambient sound"""
        if self.ambient_playing:
            try:
                pygame.mixer.music.stop()
                self.ambient_playing = False
                print("Ambient sound stopped")
            except Exception as e:
                print(f"Warning: Failed to stop ambient sound: {e}")

    def play_footstep_loop(self) -> None:
        """Start looping footstep sounds"""
        if not self.available:
            return

        if not self.footstep_playing:
            try:
                footstep_sound = self._current_footstep_sound()
                if footstep_sound is None:
                    return
                # Find an available channel and play on it
                channel = pygame.mixer.find_channel()
                if channel is None:
                    # If no channel available, reserve one
                    pygame.mixer.set_num_channels(pygame.mixer.get_num_channels() + 1)
                    channel = pygame.mixer.find_channel()

                if channel is not None:
                    channel.set_volume(self.sfx_volume)
                    channel.play(footstep_sound, loops=-1)
                    self.footstep_channel = channel  # Keep reference
                    self.footstep_playing = True
                else:
                    print("Warning: Could not find available audio channel for footsteps")
            except Exception as e:
                print(f"Warning: Failed to play footstep loop: {e}")

    def set_footstep_sprinting(self, sprinting: bool) -> None:
        sprinting = bool(sprinting)
        if sprinting == self.footstep_sprinting:
            return
        self.footstep_sprinting = sprinting

        if self.footstep_playing:
            self.stop_footstep_loop()
            self.play_footstep_loop()

    def stop_footstep_loop(self) -> None:
        """Stop looping footstep sounds"""
        if self.footstep_channel is not None:
            try:
                self.footstep_channel.stop()
            except Exception as e:
                print(f"Warning: Failed to stop footstep loop: {e}")
        self.footstep_channel = None
        self.footstep_playing = False

    def play_spider_walking_loop(self) -> None:
        """Start looping spider walking sounds without restarting when already active."""
        if not self.available or self.spider_walking_sound is None:
            return

        if not self.spider_walking_playing:
            try:
                channel = pygame.mixer.find_channel()
                if channel is None:
                    pygame.mixer.set_num_channels(pygame.mixer.get_num_channels() + 1)
                    channel = pygame.mixer.find_channel()

                if channel is not None:
                    channel.set_volume(self.sfx_volume)
                    channel.play(self.spider_walking_sound, loops=-1)
                    self.spider_walking_channel = channel
                    self.spider_walking_playing = True
                else:
                    print("Warning: Could not find available audio channel for spider walking")
            except Exception as e:
                print(f"Warning: Failed to play spider walking loop: {e}")

    def stop_spider_walking_loop(self) -> None:
        """Stop looping spider walking sounds."""
        if self.spider_walking_channel is not None:
            try:
                self.spider_walking_channel.stop()
            except Exception as e:
                print(f"Warning: Failed to stop spider walking loop: {e}")
        self.spider_walking_playing = False
        self.spider_walking_channel = None

    def play_dark_drone_loop(self) -> None:
        """Start looping the level-7 dark drone ambience without restarting
        when it's already playing."""
        if not self.available or self.dark_drone_sound is None:
            return

        if not self.dark_drone_playing:
            try:
                channel = pygame.mixer.find_channel()
                if channel is None:
                    pygame.mixer.set_num_channels(pygame.mixer.get_num_channels() + 1)
                    channel = pygame.mixer.find_channel()

                if channel is not None:
                    channel.set_volume(self.sfx_volume)
                    channel.play(self.dark_drone_sound, loops=-1)
                    self.dark_drone_channel = channel
                    self.dark_drone_playing = True
                else:
                    print("Warning: Could not find available audio channel for dark drone")
            except Exception as e:
                print(f"Warning: Failed to play dark drone loop: {e}")

    def stop_dark_drone_loop(self) -> None:
        """Stop the looping level-7 dark drone ambience."""
        if self.dark_drone_channel is not None:
            try:
                self.dark_drone_channel.stop()
            except Exception as e:
                print(f"Warning: Failed to stop dark drone loop: {e}")
        self.dark_drone_playing = False
        self.dark_drone_channel = None

    def start_einkvan_sequence(self) -> None:
        """Arm the level-7 einkvan_1..4 sequence. Playback of the first clip is
        delayed by `einkvan_lead_in_seconds` of silence; call
        `update_einkvan_sequence()` every frame to advance it."""
        self._einkvan_index = -1
        self.einkvan_sequence_finished = False
        if self.einkvan_channel is not None:
            try:
                self.einkvan_channel.stop()
            except Exception as e:
                print(f"Warning: Failed to stop einkvan sequence: {e}")
        self.einkvan_channel = None
        self._einkvan_start_at = time.monotonic() + self.einkvan_lead_in_seconds

    def _advance_einkvan_sequence(self) -> None:
        if not self.available or not self.einkvan_sounds:
            self.einkvan_sequence_finished = True
            return

        self._einkvan_index += 1
        if self._einkvan_index >= len(self.einkvan_sounds):
            self.einkvan_sequence_finished = True
            self.einkvan_channel = None
            return

        try:
            channel = pygame.mixer.find_channel()
            if channel is None:
                pygame.mixer.set_num_channels(pygame.mixer.get_num_channels() + 1)
                channel = pygame.mixer.find_channel()

            if channel is None:
                print("Warning: Could not find available audio channel for einkvan sequence")
                self.einkvan_sequence_finished = True
                return

            channel.set_volume(self.sfx_volume)
            channel.play(self.einkvan_sounds[self._einkvan_index])
            self.einkvan_channel = channel
        except Exception as e:
            print(f"Warning: Failed to play einkvan sequence clip: {e}")
            self.einkvan_sequence_finished = True

    def update_einkvan_sequence(self) -> bool:
        """Poll the einkvan sequence once per frame. Waits out the initial
        silent lead-in, then advances to the next clip when the current one
        finishes, returning True exactly once: the frame the final clip
        finishes playing."""
        if self.einkvan_sequence_finished:
            return False

        if self._einkvan_index < 0:
            if self._einkvan_start_at is None:
                return False
            if time.monotonic() < self._einkvan_start_at:
                return False
            self._einkvan_start_at = None
            self._advance_einkvan_sequence()
            return self.einkvan_sequence_finished

        channel_busy = self.einkvan_channel is not None and self.einkvan_channel.get_busy()
        if channel_busy:
            return False

        self._advance_einkvan_sequence()
        return self.einkvan_sequence_finished

    def play_monster_appearing(self, current_time: float) -> bool:
        """Play the monster-appearing stinger.

        Gating is handled by the caller based on teleport state (the sound
        should play once per teleport, the first time the monster re-enters
        the player's line of sight), not by a time-based cooldown.
        """
        if not self.available or self.monster_appearing_sound is None:
            return False

        try:
            channel = pygame.mixer.find_channel()
            if channel is None:
                pygame.mixer.set_num_channels(pygame.mixer.get_num_channels() + 1)
                channel = pygame.mixer.find_channel()

            if channel is None:
                print("Warning: Could not find available audio channel for monster appearing")
                return False

            channel.set_volume(self.sfx_volume)
            channel.play(self.monster_appearing_sound)
            self.monster_appearing_channel = channel
            self.last_monster_appearing_at = current_time
            return True
        except Exception as e:
            print(f"Warning: Failed to play monster appearing sound: {e}")
            return False

    def play_monster_scream(self, current_time: float) -> bool:
        if not self.available or not self.monster_scream_sounds:
            return False
        if not can_play_after_cooldown(
            self.last_monster_scream_at,
            current_time,
            self.monster_scream_cooldown_seconds,
        ):
            return False

        try:
            channel = pygame.mixer.find_channel()
            if channel is None:
                pygame.mixer.set_num_channels(pygame.mixer.get_num_channels() + 1)
                channel = pygame.mixer.find_channel()

            if channel is None:
                print("Warning: Could not find available audio channel for monster scream")
                return False

            scream_index = random.randrange(len(self.monster_scream_sounds))
            if len(self.monster_scream_sounds) > 1 and scream_index == self._last_monster_scream_index:
                # Keep scream selection varied while remaining random.
                available_indices = [i for i in range(len(self.monster_scream_sounds)) if i != self._last_monster_scream_index]
                scream_index = random.choice(available_indices)

            channel.set_volume(self.sfx_volume)
            channel.play(self.monster_scream_sounds[scream_index])
            self.monster_scream_channel = channel
            self._last_monster_scream_index = scream_index
            self.last_monster_scream_at = current_time
            return True
        except Exception as e:
            print(f"Warning: Failed to play monster scream sound: {e}")
            return False

    def play_spider_attack(self, current_time: float) -> bool:
        """Play spider attack SFX with cooldown to avoid rapid retriggers."""
        if not self.available or self.spider_attack_sound is None:
            return False
        if not can_play_after_cooldown(
            self.last_spider_attack_at,
            current_time,
            self.spider_attack_cooldown_seconds,
        ):
            return False

        try:
            channel = pygame.mixer.find_channel()
            if channel is None:
                pygame.mixer.set_num_channels(pygame.mixer.get_num_channels() + 1)
                channel = pygame.mixer.find_channel()

            if channel is None:
                print("Warning: Could not find available audio channel for spider attack")
                return False

            channel.set_volume(self.sfx_volume)
            channel.play(self.spider_attack_sound)
            self.spider_attack_channel = channel
            self.last_spider_attack_at = current_time
            return True
        except Exception as e:
            print(f"Warning: Failed to play spider attack sound: {e}")
            return False

    def play_intense_sequence(self) -> bool:
        """Play the level-5 intense sequence when the hallway begins."""
        if not self.available or self.intense_sequence_sound is None:
            return False

        try:
            channel = pygame.mixer.find_channel()
            if channel is None:
                pygame.mixer.set_num_channels(pygame.mixer.get_num_channels() + 1)
                channel = pygame.mixer.find_channel()

            if channel is None:
                print("Warning: Could not find available audio channel for intense sequence")
                return False

            channel.set_volume(self.sfx_volume)
            channel.play(self.intense_sequence_sound)
            self.intense_sequence_channel = channel
            return True
        except Exception as e:
            print(f"Warning: Failed to play intense sequence sound: {e}")
            return False

    def play_exhausted(self) -> bool:
        """Play the exhausted stinger once when the player reaches the exhausted state."""
        if not self.available or self.exhausted_sound is None:
            return False

        try:
            channel = pygame.mixer.find_channel()
            if channel is None:
                pygame.mixer.set_num_channels(pygame.mixer.get_num_channels() + 1)
                channel = pygame.mixer.find_channel()

            if channel is None:
                print("Warning: Could not find available audio channel for exhausted sound")
                return False

            channel.set_volume(self.sfx_volume*20)
            channel.play(self.exhausted_sound)
            self.exhausted_channel = channel
            return True
        except Exception as e:
            print(f"Warning: Failed to play exhausted sound: {e}")
            return False

    def cleanup(self) -> None:
        """Clean up audio resources"""
        if self.available:
            self.stop_ambient()
            self.stop_footstep_loop()
            self.stop_spider_walking_loop()
            self.stop_dark_drone_loop()
            try:
                pygame.mixer.quit()
            except Exception:
                pass



# Global audio manager instance
_AUDIO_MANAGER: Optional[AudioManager] = None


def get_audio_manager(ambient_volume: Optional[float] = None, sfx_volume: Optional[float] = None) -> AudioManager:
    global _AUDIO_MANAGER
    if _AUDIO_MANAGER is None:
        _AUDIO_MANAGER = AudioManager(
            ambient_volume=1.0 if ambient_volume is None else ambient_volume,
            sfx_volume=0.3 if sfx_volume is None else sfx_volume,
        )
    else:
        if ambient_volume is not None:
            _AUDIO_MANAGER.set_ambient_volume(ambient_volume)
        if sfx_volume is not None:
            _AUDIO_MANAGER.set_sfx_volume(sfx_volume)
    return _AUDIO_MANAGER


