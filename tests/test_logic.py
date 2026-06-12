import unittest
import sys
from types import SimpleNamespace
from unittest.mock import patch

try:
    import pygame  # type: ignore  # noqa: F401
except ModuleNotFoundError:
    class _FakeMusic:
        def load(self, *_args, **_kwargs):
            return None

        def set_volume(self, *_args, **_kwargs):
            return None

        def play(self, *_args, **_kwargs):
            return None

        def stop(self, *_args, **_kwargs):
            return None

    class _FakeChannel:
        def set_volume(self, *_args, **_kwargs):
            return None

        def play(self, *_args, **_kwargs):
            return None

        def stop(self, *_args, **_kwargs):
            return None

    class _FakeSound:
        def __init__(self, *_args, **_kwargs):
            self.volume = 1.0

        def set_volume(self, volume):
            self.volume = volume

    sys.modules["pygame"] = SimpleNamespace(
        mixer=SimpleNamespace(
            init=lambda *args, **kwargs: None,
            quit=lambda: None,
            music=_FakeMusic(),
            Sound=_FakeSound,
            find_channel=lambda: _FakeChannel(),
            set_num_channels=lambda *_args, **_kwargs: None,
            get_num_channels=lambda: 8,
        )
    )

from audio import AudioManager, can_play_after_cooldown, clamp_volume
from core_logic import adjust_fov, format_mmss, monster_arm_reach_factor, phased_speed


class TestCoreLogic(unittest.TestCase):
    def test_format_mmss(self):
        self.assertEqual(format_mmss(0), "00:00")
        self.assertEqual(format_mmss(65.9), "01:05")
        self.assertEqual(format_mmss(3600), "60:00")

    def test_phased_speed(self):
        phases = [(0.0, 4.0), (30.0, 5.0), (60.0, 6.5), (120.0, 8.0)]
        self.assertEqual(phased_speed(0, phases, 9.0), 4.0)
        self.assertEqual(phased_speed(45, phases, 9.0), 5.0)
        self.assertEqual(phased_speed(61, phases, 9.0), 6.5)
        self.assertEqual(phased_speed(999, phases, 7.2), 7.2)

    def test_can_play_after_cooldown(self):
        self.assertTrue(can_play_after_cooldown(None, 0.0, 30.0))
        self.assertFalse(can_play_after_cooldown(10.0, 39.9, 30.0))
        self.assertTrue(can_play_after_cooldown(10.0, 40.0, 30.0))
        self.assertTrue(can_play_after_cooldown(10.0, 45.0, 30.0))

    def test_clamp_volume(self):
        self.assertEqual(clamp_volume(-1.0), 0.0)
        self.assertEqual(clamp_volume(0.0), 0.0)
        self.assertEqual(clamp_volume(0.42), 0.42)
        self.assertEqual(clamp_volume(1.0), 1.0)
        self.assertEqual(clamp_volume(9.0), 1.0)

    def test_adjust_fov(self):
        self.assertEqual(adjust_fov(86.0, 1.0, 1.0, speed=10.0), 96.0)
        self.assertEqual(adjust_fov(86.0, -1.0, 1.0, speed=10.0), 76.0)
        self.assertEqual(adjust_fov(108.0, 1.0, 1.0, speed=10.0), 110.0)
        self.assertEqual(adjust_fov(56.0, -1.0, 1.0, speed=10.0), 55.0)

    def test_monster_arm_reach_factor(self):
        self.assertEqual(monster_arm_reach_factor(3.0), 0.0)
        self.assertEqual(monster_arm_reach_factor(1.0), 1.0)
        mid = monster_arm_reach_factor(1.8)
        self.assertGreater(mid, 0.0)
        self.assertLess(mid, 1.0)

    @patch("audio.pygame.mixer.init")
    def test_audio_manager_default_mix(self, _mock_init):
        manager = AudioManager()
        self.assertEqual(manager.ambient_volume, 1.0)
        self.assertEqual(manager.sfx_volume, 0.3)

    @patch("audio.pygame.mixer.init")
    def test_audio_manager_clamps_mix_values(self, _mock_init):
        manager = AudioManager(ambient_volume=4.0, sfx_volume=-2.0)
        self.assertEqual(manager.ambient_volume, 1.0)
        self.assertEqual(manager.sfx_volume, 0.0)

    @patch("audio.pygame.mixer.init")
    def test_audio_manager_play_monster_scream(self, _mock_init):
        manager = AudioManager()
        manager.monster_scream_sound = object()
        self.assertTrue(manager.play_monster_scream(10.0))
        self.assertFalse(manager.play_monster_scream(11.0))
        self.assertTrue(manager.play_monster_scream(13.0))

    def test_reach_factor_scream_threshold_behavior(self):
        threshold = 0.62
        self.assertGreaterEqual(monster_arm_reach_factor(1.4), threshold)
        self.assertLess(monster_arm_reach_factor(1.8), threshold)


if __name__ == "__main__":
    unittest.main()
