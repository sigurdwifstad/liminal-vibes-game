from __future__ import annotations

from pathlib import Path
import random
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
            self.ambient_channel = None
            self.footstep_channel = None
            self.monster_appearing_channel = None
            self.monster_scream_channel = None
            self.spider_walking_channel = None
            self.spider_attack_channel = None
            self._last_monster_scream_index = None
            self.ambient_playing = False
            self.footstep_playing = False
            self.spider_walking_playing = False
            self.monster_appearing_cooldown_seconds = 30.0
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
        self._last_monster_scream_index: Optional[int] = None
        self.monster_appearing_cooldown_seconds = 30.0
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
                print(f"Loaded footstep sound from {footstep_path}")
            else:
                print(f"Warning: Footstep sound not found at {footstep_path}")
                self.footstep_sound = None

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
        except Exception as e:
            print(f"Warning: Could not load audio files: {e}")
            self.ambient_sound = None
            self.footstep_sound = None
            self.monster_appearing_sound = None
            self.monster_scream_sounds = []
            self.spider_walking_sound = None
            self.spider_attack_sound = None

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
        if self.monster_appearing_sound is not None:
            self.monster_appearing_sound.set_volume(self.sfx_volume)
        for scream_sound in self.monster_scream_sounds:
            scream_sound.set_volume(self.sfx_volume)
        if self.spider_walking_sound is not None:
            self.spider_walking_sound.set_volume(self.sfx_volume)
        if self.spider_attack_sound is not None:
            self.spider_attack_sound.set_volume(self.sfx_volume)

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
        if not self.available or self.footstep_sound is None:
            return

        if not self.footstep_playing:
            try:
                # Find an available channel and play on it
                channel = pygame.mixer.find_channel()
                if channel is None:
                    # If no channel available, reserve one
                    pygame.mixer.set_num_channels(pygame.mixer.get_num_channels() + 1)
                    channel = pygame.mixer.find_channel()

                if channel is not None:
                    channel.set_volume(self.sfx_volume)
                    channel.play(self.footstep_sound, loops=-1)
                    self.footstep_channel = channel  # Keep reference
                    self.footstep_playing = True
                else:
                    print("Warning: Could not find available audio channel for footsteps")
            except Exception as e:
                print(f"Warning: Failed to play footstep loop: {e}")

    def stop_footstep_loop(self) -> None:
        """Stop looping footstep sounds"""
        if self.footstep_channel is not None:
            try:
                self.footstep_channel.stop()
                self.footstep_playing = False
            except Exception as e:
                print(f"Warning: Failed to stop footstep loop: {e}")

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

    def play_monster_appearing(self, current_time: float) -> bool:
        """Play the monster-appearing stinger if its cooldown has elapsed."""
        if not self.available or self.monster_appearing_sound is None:
            return False
        if not can_play_after_cooldown(
            self.last_monster_appearing_at,
            current_time,
            self.monster_appearing_cooldown_seconds,
        ):
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

    def cleanup(self) -> None:
        """Clean up audio resources"""
        if self.available:
            self.stop_ambient()
            self.stop_footstep_loop()
            self.stop_spider_walking_loop()
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



