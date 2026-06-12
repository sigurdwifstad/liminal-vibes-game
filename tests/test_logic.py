import unittest
from unittest.mock import patch

from audio import AudioManager, can_play_after_cooldown, clamp_volume
from core_logic import format_mmss, phased_speed


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


if __name__ == "__main__":
    unittest.main()
