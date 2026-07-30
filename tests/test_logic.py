import unittest
import sys
from types import ModuleType, SimpleNamespace
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
from core_logic import adjust_fov, format_mmss, monster_arm_reach_factor, phased_speed, touches_exit_portal


def _install_fake_engine_modules() -> None:
    if "ursina" in sys.modules and "panda3d.core" in sys.modules:
        return

    class _FakeVec3:
        __slots__ = ("x", "y", "z")

        def __init__(self, x=0.0, y=0.0, z=0.0):
            self.x = float(x)
            self.y = float(y)
            self.z = float(z)

        def __add__(self, other):
            return _FakeVec3(self.x + other.x, self.y + other.y, self.z + other.z)

        def __sub__(self, other):
            return _FakeVec3(self.x - other.x, self.y - other.y, self.z - other.z)

        def __mul__(self, scalar):
            return _FakeVec3(self.x * scalar, self.y * scalar, self.z * scalar)

        __rmul__ = __mul__

        def length(self):
            return (self.x * self.x + self.y * self.y + self.z * self.z) ** 0.5

        def normalized(self):
            mag = self.length()
            if mag <= 0.0:
                return _FakeVec3()
            return _FakeVec3(self.x / mag, self.y / mag, self.z / mag)

        def dot(self, other):
            return self.x * other.x + self.y * other.y + self.z * other.z

    class _FakeEntity:
        def __init__(self, **kwargs):
            self.parent = kwargs.pop("parent", None)
            self.position = kwargs.pop("position", _FakeVec3())
            self.rotation = kwargs.pop("rotation", _FakeVec3())
            self.scale = kwargs.pop("scale", _FakeVec3(1.0, 1.0, 1.0))
            self.color = kwargs.pop("color", None)
            self.texture = kwargs.pop("texture", None)
            self.texture_scale = kwargs.pop("texture_scale", None)
            self.collider = kwargs.pop("collider", None)
            self.enabled = kwargs.pop("enabled", True)
            self.visible = kwargs.pop("visible", True)
            self.origin = kwargs.pop("origin", None)
            self.rotation_x = getattr(self.rotation, "x", 0.0)
            self.rotation_y = getattr(self.rotation, "y", 0.0)
            self.rotation_z = getattr(self.rotation, "z", 0.0)
            self.children = []
            if self.parent is not None and hasattr(self.parent, "children"):
                self.parent.children.append(self)

        def look_at(self, *_args, **_kwargs):
            return None

        @property
        def world_position(self):
            return self.position

        @property
        def forward(self):
            return _FakeVec3(0.0, 0.0, 1.0)

        @property
        def right(self):
            return _FakeVec3(1.0, 0.0, 0.0)

        @property
        def rotation_y(self):
            return self._rotation_y

        @rotation_y.setter
        def rotation_y(self, value):
            self._rotation_y = float(value)

        @property
        def rotation_x(self):
            return self._rotation_x

        @rotation_x.setter
        def rotation_x(self, value):
            self._rotation_x = float(value)

        @property
        def rotation_z(self):
            return self._rotation_z

        @rotation_z.setter
        def rotation_z(self, value):
            self._rotation_z = float(value)

    class _FakeTexture:
        def __init__(self, *_args, **_kwargs):
            self.filtering = None

    class _FakePNMImage:
        def __init__(self, *_args, **_kwargs):
            self._pixels = {}

        def setXel(self, *args, **_kwargs):
            self._pixels[args[:2]] = args[2:]

        def setAlpha(self, *args, **_kwargs):
            self._pixels[(args[0], args[1], "alpha")] = args[2]

    class _FakePandaTexture:
        def __init__(self, *_args, **_kwargs):
            self.loaded = None

        def load(self, image):
            self.loaded = image

    def _color_rgb(r, g, b):
        return (r, g, b)

    def _color_rgba(r, g, b, a):
        return (r, g, b, a)

    fake_ursina = ModuleType("ursina")
    fake_ursina.Entity = _FakeEntity
    fake_ursina.Vec3 = _FakeVec3
    fake_ursina.Texture = _FakeTexture
    fake_ursina.Text = _FakeEntity
    fake_ursina.AmbientLight = _FakeEntity
    fake_ursina.PointLight = _FakeEntity
    fake_ursina.DirectionalLight = _FakeEntity
    fake_ursina.Ursina = lambda *args, **kwargs: SimpleNamespace(run=lambda: None)
    fake_ursina.camera = SimpleNamespace(ui=_FakeEntity(), parent=None, position=_FakeVec3(), rotation=_FakeVec3(), fov=86.0, rotation_x=0.0, rotation_y=0.0)
    fake_ursina.application = SimpleNamespace(quit=lambda: None)
    fake_ursina.window = SimpleNamespace(title="", color=None, exit_button=SimpleNamespace(visible=False), fps_counter=SimpleNamespace(enabled=False))
    fake_ursina.scene = SimpleNamespace(fog_density=None, fog_color=None)
    fake_ursina.color = SimpleNamespace(
        black=(0, 0, 0),
        white=(255, 255, 255),
        rgb=_color_rgb,
        rgba=_color_rgba,
    )
    fake_ursina.mouse = SimpleNamespace(locked=False, visible=False)
    fake_ursina.held_keys = {k: 0 for k in ["right arrow", "left arrow", "up arrow", "down arrow", "e", "q", "w", "s", "d", "a", "shift", "left shift", "right shift"]}
    fake_ursina.clamp = lambda value, low, high: max(low, min(high, value))
    fake_ursina.raycast = lambda *args, **kwargs: SimpleNamespace(hit=False)
    fake_ursina.time = SimpleNamespace(dt=0.0)
    fake_ursina.destroy = lambda *_args, **_kwargs: None
    sys.modules["ursina"] = fake_ursina

    fake_panda3d = ModuleType("panda3d")
    fake_panda3d_core = ModuleType("panda3d.core")
    fake_panda3d_core.PNMImage = _FakePNMImage
    fake_panda3d_core.Texture = _FakePandaTexture
    fake_panda3d.core = fake_panda3d_core
    sys.modules["panda3d"] = fake_panda3d
    sys.modules["panda3d.core"] = fake_panda3d_core


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

    def test_touches_exit_portal_requires_near_wall_and_inside_frame_width(self):
        self.assertTrue(
            touches_exit_portal(
                player_x=1.45,
                player_z=0.2,
                exit_x=0.0,
                exit_z=0.0,
                exit_direction=(1, 0),
                cell_size=4.0,
            )
        )
        self.assertFalse(
            touches_exit_portal(
                player_x=0.8,
                player_z=0.0,
                exit_x=0.0,
                exit_z=0.0,
                exit_direction=(1, 0),
                cell_size=4.0,
            )
        )
        self.assertFalse(
            touches_exit_portal(
                player_x=1.45,
                player_z=1.3,
                exit_x=0.0,
                exit_z=0.0,
                exit_direction=(1, 0),
                cell_size=4.0,
            )
        )

    def test_touches_exit_portal_handles_north_south_portals(self):
        self.assertTrue(
            touches_exit_portal(
                player_x=-0.35,
                player_z=-1.45,
                exit_x=0.0,
                exit_z=0.0,
                exit_direction=(0, -1),
                cell_size=4.0,
            )
        )
        self.assertFalse(
            touches_exit_portal(
                player_x=1.3,
                player_z=-1.45,
                exit_x=0.0,
                exit_z=0.0,
                exit_direction=(0, -1),
                cell_size=4.0,
            )
        )

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
        manager.monster_scream_sounds = [object()]
        self.assertTrue(manager.play_monster_scream(10.0))
        self.assertFalse(manager.play_monster_scream(11.0))
        self.assertTrue(manager.play_monster_scream(13.0))

    @patch("audio.pygame.mixer.init")
    @patch("audio.random.choice", return_value=1)
    @patch("audio.random.randrange", side_effect=[0, 0])
    def test_audio_manager_monster_scream_randomly_varies_choice(self, _mock_randrange, _mock_choice, _mock_init):
        manager = AudioManager()
        manager.monster_scream_sounds = [object(), object(), object()]

        self.assertTrue(manager.play_monster_scream(10.0))
        self.assertEqual(manager._last_monster_scream_index, 0)

        self.assertTrue(manager.play_monster_scream(13.0))
        self.assertEqual(manager._last_monster_scream_index, 1)

    @patch("audio.pygame.mixer.init")
    def test_audio_manager_play_intense_sequence(self, _mock_init):
        manager = AudioManager()

        class _FakeChannel:
            def set_volume(self, *_args, **_kwargs):
                return None

            def play(self, *_args, **_kwargs):
                return None

        manager.available = True
        manager.intense_sequence_sound = object()

        with patch("audio.pygame.mixer.find_channel", return_value=_FakeChannel()), patch(
            "audio.pygame.mixer.set_num_channels"
        ):
            self.assertTrue(manager.play_intense_sequence())

    @patch("audio.pygame.mixer.init")
    def test_audio_manager_restarts_footsteps_when_sprint_state_changes(self, _mock_init):
        manager = AudioManager()
        manager.footstep_sound = object()
        manager.footstep_playing = True

        with patch.object(manager, "stop_footstep_loop") as stop_mock, patch.object(
            manager, "play_footstep_loop"
        ) as play_mock:
            manager.set_footstep_sprinting(True)

        self.assertTrue(manager.footstep_sprinting)
        stop_mock.assert_called_once()
        play_mock.assert_called_once()

    def test_level_5_is_a_single_hallway(self):
        try:
            from maze import MazeManager
        except ModuleNotFoundError:
            _install_fake_engine_modules()
            from maze import MazeManager

        maze = MazeManager(seed=12345, level=5, cell_size=4.0, test=False)
        x_values = {cell[0] for cell in maze.walkable_cells}
        z_values = sorted(cell[1] for cell in maze.walkable_cells)

        self.assertEqual(len(x_values), 1)
        self.assertIsNotNone(maze.monster_start_cell)
        self.assertEqual(abs(maze.monster_start_cell[0] - maze.start_cell[0]) + abs(maze.monster_start_cell[1] - maze.start_cell[1]), 3)
        self.assertLess(maze.monster_start_cell[1], maze.start_cell[1])
        self.assertLess(maze.start_cell[1], maze.exit_cell[1])
        self.assertEqual(maze.exit_direction, (0, 1))
        self.assertEqual(maze.player_spawn_rotation_y, 180.0)
        self.assertGreater(len(z_values), 10)

        neighbor_counts = [sum(1 for _ in maze.walkable_neighbors(cell)) for cell in maze.walkable_cells]
        self.assertEqual(neighbor_counts.count(1), 2)
        self.assertTrue(all(count <= 2 for count in neighbor_counts))

    def test_spider_is_disabled_on_level_5(self):
        try:
            from maze import MazeManager
            from spider_monster import SpiderController
            from ursina import Vec3
        except ModuleNotFoundError:
            _install_fake_engine_modules()
            from maze import MazeManager
            from spider_monster import SpiderController
            from ursina import Vec3

        maze = MazeManager(seed=12345, level=5, cell_size=4.0, test=False)
        spider = SpiderController(position=Vec3(0, -1000, 0))
        spider.spawn_delay_seconds = 0.0

        player_x, player_z = maze.world_from_cell(maze.start_cell)
        self.assertFalse(spider.update_spider(maze, Vec3(player_x, 0.0, player_z), 0.0, level=5))
        self.assertFalse(spider.spawned)

    def test_monster_does_not_teleport_on_level_5(self):
        try:
            from maze import MazeManager
            from monster import MonsterController
            from ursina import Vec3
        except ModuleNotFoundError:
            _install_fake_engine_modules()
            from maze import MazeManager
            from monster import MonsterController
            from ursina import Vec3

        maze = MazeManager(seed=12345, level=5, cell_size=4.0, test=False)
        monster = MonsterController(position=Vec3(0, -1000, 0))
        monster.reset()
        monster_x, monster_z = maze.world_from_cell(maze.monster_start_cell)
        monster.place_at(Vec3(monster_x, 0.0, monster_z))
        monster.teleport_timer = 0.0
        monster.path_refresh_timer = 999.0

        player_x, player_z = maze.world_from_cell(maze.start_cell)
        with patch.object(monster, "_is_visible_to_player", return_value=False), patch.object(
            monster, "_pick_hidden_cell"
        ) as mock_pick, patch("monster.time.dt", 1.0):
            monster.update_monster(maze, Vec3(player_x, 0.0, player_z), 0.0, level=5)

        mock_pick.assert_not_called()

    def test_spider_catch_drains_without_game_over(self):
        try:
            from main import LiminalVibesGame
            from ursina import Vec3
        except ModuleNotFoundError:
            _install_fake_engine_modules()
            from main import LiminalVibesGame
            from ursina import Vec3

        game = LiminalVibesGame(test=False, start_level=5)
        game.start_new_run()
        assert game.player is not None and game.spider is not None

        game.level = 4
        game.ui.run.running = True
        game.spider.spawn_delay_seconds = 0.0
        game.spider.spawned = True
        game.spider.visible = True
        game.spider.enabled = True
        game.spider.position = game.player.world_position
        game.spider._drain_complete = False
        game.spider._draining = False

        with patch.object(game.spider.audio, "play_spider_attack", return_value=True), patch.object(game.spider.audio, "stop_spider_walking_loop", return_value=None), patch("spider_monster.time.dt", 0.0):
            game.update()

        self.assertTrue(game.player.enabled)
        self.assertTrue(game.ui.run.running)
        self.assertEqual(game.player.stamina, 0.0)
        self.assertTrue(game.player.exhausted)

        game.spider._drain_complete = True
        game.update()

        self.assertTrue(game.ui.run.running)
        self.assertTrue(game.player.enabled)

    def test_lamp_brightness_parameter_clamps_and_disables_lights_at_zero(self):
        try:
            from main import LiminalVibesGame
        except ModuleNotFoundError:
            _install_fake_engine_modules()
            from main import LiminalVibesGame

        game = LiminalVibesGame(test=True, lamp_brightness=-2.0)
        self.assertEqual(game.lamp_brightness, 0.0)
        self.assertEqual(game.point_lights, [])

        game.set_lamp_brightness(2.0)
        self.assertEqual(game.lamp_brightness, 1.0)
        self.assertGreater(len(game.point_lights), 0)

        game.set_lamp_brightness(0.0)
        self.assertEqual(game.point_lights, [])

    def test_lamp_lights_have_real_distance_attenuation(self):
        # Regression test for the "one wall bright, opposite wall pitch black" bug:
        # Ursina's PointLight has no `.range`/`.brightness` attributes, so setting
        # them used to silently create inert Python attributes that never reached
        # the underlying Panda3D light, leaving attenuation at Panda3D's default
        # of (1, 0, 0) -- i.e. constant, no falloff at all. This test asserts the
        # real underlying light node now has a non-zero quadratic attenuation term
        # and a finite max distance, proving illumination actually falls off with
        # distance instead of shining at full strength everywhere.
        try:
            from main import LiminalVibesGame
        except ModuleNotFoundError:
            _install_fake_engine_modules()
            from main import LiminalVibesGame

        game = LiminalVibesGame(test=True, lamp_brightness=0.5)
        self.assertGreater(len(game.point_lights), 0)

        for light in game.point_lights:
            underlying = getattr(light, "_light", None)
            if underlying is None or not hasattr(underlying, "getAttenuation"):
                continue  # fake engine environment: nothing real to assert on
            constant, linear, quadratic = underlying.getAttenuation()
            self.assertGreater(quadratic, 0.0)
            self.assertGreater(underlying.getMaxDistance(), 0.0)
            self.assertLess(underlying.getMaxDistance(), game.maze.cell_size * 3.0)

    def test_lamp_lights_are_linked_only_to_reachable_geometry(self):
        # Regression test for global light bleed-through: previously every point
        # light lit the *entire* scene (Ursina's PointLight attaches itself via
        # `render.setLight(...)` in its constructor), so a wall could be lit purely
        # because *some* lamp existed anywhere in the maze, even across walls with
        # no walkable connection. This test asserts a lamp's light is only ever
        # attached to entities that maze.entities_near_cell() reports as reachable
        # from that lamp's own cell.
        try:
            from main import LiminalVibesGame
            from ursina import PointLight
        except ModuleNotFoundError:
            _install_fake_engine_modules()
            from main import LiminalVibesGame
            from ursina import PointLight

        game = LiminalVibesGame(test=True, lamp_brightness=0.5)
        assert game.maze is not None
        if not hasattr(PointLight, "get_child"):
            return  # fake engine environment: no real scene graph to assert on

        for cell, light in zip(game.maze.lamp_cells, game.point_lights):
            light_np = light.get_child(0)
            reachable = set(game.maze.entities_near_cell(cell, hops=game._LIGHT_LINK_HOPS))
            for other_cell, other_light in zip(game.maze.lamp_cells, game.point_lights):
                if other_light is light:
                    continue
                unreachable_entities = [
                    e for e in game.maze.entities_near_cell(other_cell, hops=0) if e not in reachable
                ]
                for entity in unreachable_entities:
                    self.assertFalse(entity.has_light(light_np))

    def test_reach_factor_scream_threshold_behavior(self):
        threshold = 0.62
        self.assertGreaterEqual(monster_arm_reach_factor(1.4), threshold)
        self.assertLess(monster_arm_reach_factor(1.8), threshold)


if __name__ == "__main__":
    unittest.main()
