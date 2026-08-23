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

    class _FakeMesh:
        def __init__(self, *_args, **_kwargs):
            self.vertices = _kwargs.get("vertices")
            self.triangles = _kwargs.get("triangles")
            self.uvs = _kwargs.get("uvs")
            self.normals = _kwargs.get("normals")
            self.mode = _kwargs.get("mode")

    class _FakePNMImage:
        def __init__(self, *_args, **_kwargs):
            self._pixels = {}

        def addAlpha(self, *_args, **_kwargs):
            pass

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
    fake_ursina.Mesh = _FakeMesh
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
    def test_level_1_intro_hint_appears_then_fades(self):
        _install_fake_engine_modules()
        from game_state import GameStateUI

        ui = GameStateUI()
        ui.start_new_run(level=1)

        self.assertTrue(ui.level_intro.enabled)
        self.assertGreater(ui.level_intro_timer, 0.0)

        ui.level_intro_timer = 0.0
        ui.update()
        self.assertFalse(ui.level_intro.enabled)
        self.assertEqual(ui.level_intro_timer, 0.0)

    def test_regular_game_over_fades_to_black_then_shows_restart_hint(self):
        """After being caught on a regular level, the screen should hold for
        ~3 seconds (with GAME OVER/survival time/restart hint all hidden),
        then fade to black; all that text should only appear together once
        the fade has fully completed."""
        _install_fake_engine_modules()
        from game_state import GameStateUI
        from ursina import time as ursina_time

        ui = GameStateUI()
        ui.on_player_caught()

        self.assertFalse(ui.game_over_title.enabled)
        self.assertFalse(ui.game_over_time.enabled)
        self.assertFalse(ui.game_over_hint.enabled)
        self.assertEqual(ui.game_over_backdrop.color, (0, 0, 0, 0))

        # Still within the initial 3-second hold: no fade yet, no text.
        ursina_time.dt = 2.9
        ui.update()
        self.assertFalse(ui.game_over_title.enabled)
        self.assertFalse(ui.game_over_time.enabled)
        self.assertFalse(ui.game_over_hint.enabled)
        self.assertEqual(ui.game_over_backdrop.color, (0, 0, 0, 0))

        # Past the hold, partway through the fade: backdrop darkens, all
        # text stays hidden until the fade fully completes.
        ursina_time.dt = 0.2
        ui.update()
        self.assertFalse(ui.game_over_title.enabled)
        self.assertFalse(ui.game_over_time.enabled)
        self.assertFalse(ui.game_over_hint.enabled)
        self.assertGreater(ui.game_over_backdrop.color[3], 0)

        # Once the fade duration has fully elapsed, all the text appears together.
        ursina_time.dt = ui.game_over_fade_duration
        ui.update()
        self.assertTrue(ui.game_over_title.enabled)
        self.assertTrue(ui.game_over_time.enabled)
        self.assertTrue(ui.game_over_hint.enabled)
        self.assertEqual(ui.game_over_backdrop.color[3], 255)

    def test_level_9_transition_holds_black_cycles_text_and_then_reveals(self):
        _install_fake_engine_modules()
        from game_state import GameStateUI
        from ursina import time as ursina_time

        ui = GameStateUI()
        ui.start_level9_transition()

        self.assertTrue(ui.level9_transition_active)
        self.assertFalse(ui.level9_transition_text.enabled)

        ursina_time.dt = 2.9
        ui.update()
        self.assertFalse(ui.level9_transition_text.enabled)
        self.assertGreater(ui.level9_transition_backdrop.color[3], 0)

        ursina_time.dt = 0.2
        ui.update()
        self.assertTrue(ui.level9_transition_text.enabled)
        self.assertEqual(ui.level9_transition_text.text, ui.level9_transition_messages[0])

        ursina_time.dt = ui.level9_transition_sentence_duration
        ui.update()
        self.assertEqual(ui.level9_transition_text.text, ui.level9_transition_messages[1])

        ursina_time.dt = ui.level9_transition_sentence_duration * (len(ui.level9_transition_messages) - 1)
        ui.update()
        self.assertTrue(ui.level9_transition_request_level_load)
        self.assertFalse(ui.level9_transition_text.enabled)
        self.assertEqual(ui.level9_transition_backdrop.color[3], 255)

        ui.mark_level9_transition_level_loaded()
        ursina_time.dt = ui.level9_transition_reveal_duration
        ui.update()
        self.assertTrue(ui.level9_transition_finished)
        self.assertEqual(ui.level9_transition_backdrop.color[3], 0)

        ui.complete_level9_transition()
        self.assertFalse(ui.level9_transition_active)
        self.assertTrue(ui.hud_time.enabled)
        self.assertTrue(ui.hud_level.enabled)

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

    def test_level_7_is_an_open_field_with_a_gated_pyramid_door(self):
        try:
            from maze import MazeManager
        except ModuleNotFoundError:
            _install_fake_engine_modules()
            from maze import MazeManager

        maze = MazeManager(seed=12345, level=7, cell_size=4.0, test=False)

        # Open field: no interior maze walls carved anywhere except the pyramid.
        self.assertIsNotNone(maze.pyramid_center_cell)
        self.assertIsNotNone(maze.pyramid_monster_cell)
        self.assertEqual(maze.player_spawn_rotation_y, 0.0)
        self.assertTrue(maze.is_walkable_cell(maze.start_cell))
        self.assertTrue(maze.is_walkable_cell(maze.exit_cell))
        # The pyramid's front face is a solid wall (blocking, not walkable).
        self.assertFalse(maze.is_walkable_cell(maze.exit_wall_cell))
        self.assertFalse(maze.is_walkable_cell(maze.pyramid_center_cell))

        # The monster stands between the player's start and the pyramid's door.
        start_to_door = abs(maze.exit_wall_cell[1] - maze.start_cell[1])
        start_to_monster = abs(maze.pyramid_monster_cell[1] - maze.start_cell[1])
        monster_to_door = abs(maze.exit_wall_cell[1] - maze.pyramid_monster_cell[1])
        self.assertLess(start_to_monster, start_to_door)
        self.assertGreater(monster_to_door, 0)

        # The door is locked until `unlock_pyramid_door()` is called.
        self.assertFalse(maze.door_unlocked)
        exit_wx, exit_wz = maze.world_from_cell(maze.exit_cell)
        from ursina import Vec3

        at_the_door = Vec3(exit_wx, 0.0, exit_wz + 1.9)
        self.assertFalse(maze.player_reached_exit(at_the_door))

        maze.unlock_pyramid_door()
        self.assertTrue(maze.door_unlocked)
        self.assertTrue(maze.player_reached_exit(at_the_door))

        # Calling it again is a harmless no-op.
        maze.unlock_pyramid_door()
        self.assertTrue(maze.door_unlocked)

    def test_spider_is_disabled_on_level_7(self):
        try:
            from maze import MazeManager
            from spider_monster import SpiderController
            from ursina import Vec3
        except ModuleNotFoundError:
            _install_fake_engine_modules()
            from maze import MazeManager
            from spider_monster import SpiderController
            from ursina import Vec3

        maze = MazeManager(seed=12345, level=7, cell_size=4.0, test=False)
        spider = SpiderController(position=Vec3(0, -1000, 0))
        spider.spawn_delay_seconds = 0.0

        player_x, player_z = maze.world_from_cell(maze.start_cell)
        self.assertFalse(spider.update_spider(maze, Vec3(player_x, 0.0, player_z), 0.0, level=7))
        self.assertFalse(spider.spawned)

    def test_crucified_monster_on_level_7_is_giant_static_and_non_lethal(self):
        try:
            from maze import MazeManager
            from monster import MonsterController
            from ursina import Vec3
        except ModuleNotFoundError:
            _install_fake_engine_modules()
            from maze import MazeManager
            from monster import MonsterController
            from ursina import Vec3

        maze = MazeManager(seed=12345, level=7, cell_size=4.0, test=False)
        monster = MonsterController(position=Vec3(0, -1000, 0))
        monster.reset()

        monster_x, monster_z = maze.world_from_cell(maze.pyramid_monster_cell)
        pyramid_x, pyramid_z = maze.world_from_cell(maze.pyramid_center_cell)
        monster.place_crucified(Vec3(monster_x, 0.0, monster_z), facing_position=Vec3(pyramid_x, 0.0, pyramid_z))

        self.assertTrue(monster.static_crucified)
        self.assertEqual(
            (monster.scale.x, monster.scale.y, monster.scale.z),
            (monster.crucified_scale, monster.crucified_scale, monster.crucified_scale),
        )

        before_position = monster.position
        # Even standing right on top of the player, and even with catching enabled,
        # the crucified monster never catches or moves.
        with patch("monster.time.dt", 1.0):
            caught = monster.update_monster(
                maze,
                Vec3(monster_x, 0.0, monster_z),
                999999.0,
                can_catch_player=True,
                level=7,
            )
        self.assertFalse(caught)
        self.assertEqual(monster.position, before_position)
        self.assertEqual(monster.current_speed, 0.0)

        monster.reset()
        self.assertFalse(monster.static_crucified)
        self.assertEqual((monster.scale.x, monster.scale.y, monster.scale.z), (1.0, 1.0, 1.0))

    def test_einkvan_sequence_unlocks_door_after_the_fourth_clip(self):
        try:
            from audio import AudioManager
        except ModuleNotFoundError:
            _install_fake_engine_modules()
            from audio import AudioManager

        class _FakeChannel:
            def __init__(self):
                self.busy = True

            def set_volume(self, *_args, **_kwargs):
                return None

            def play(self, *_args, **_kwargs):
                self.busy = True

            def get_busy(self):
                return self.busy

            def stop(self, *_args, **_kwargs):
                self.busy = False

        with patch("audio.pygame.mixer.init"):
            manager = AudioManager()
        manager.available = True
        manager.einkvan_sounds = [object(), object(), object(), object()]

        channel = _FakeChannel()
        fake_clock = {"now": 1000.0}

        def fake_monotonic():
            return fake_clock["now"]

        with patch("audio.pygame.mixer.find_channel", return_value=channel), patch("audio.pygame.mixer.set_num_channels"), patch(
            "audio.time.monotonic", side_effect=fake_monotonic
        ):
            manager.start_einkvan_sequence()
            self.assertFalse(manager.einkvan_sequence_finished)

            # No clip plays during the silent lead-in.
            self.assertFalse(manager.update_einkvan_sequence())
            self.assertEqual(manager._einkvan_index, -1)
            fake_clock["now"] += manager.einkvan_lead_in_seconds - 0.01
            self.assertFalse(manager.update_einkvan_sequence())
            self.assertEqual(manager._einkvan_index, -1)

            # Once the lead-in elapses, the first clip starts.
            fake_clock["now"] += 0.02
            self.assertFalse(manager.update_einkvan_sequence())
            self.assertEqual(manager._einkvan_index, 0)

            # While a clip is still playing, updates are no-ops.
            self.assertFalse(manager.update_einkvan_sequence())
            self.assertFalse(manager.update_einkvan_sequence())

            # Each time the "current" clip finishes, the sequence advances.
            channel.busy = False
            self.assertFalse(manager.update_einkvan_sequence())  # clip 1 -> clip 2
            channel.busy = False
            self.assertFalse(manager.update_einkvan_sequence())  # clip 2 -> clip 3
            channel.busy = False
            self.assertFalse(manager.update_einkvan_sequence())  # clip 3 -> clip 4
            channel.busy = False
            self.assertTrue(manager.update_einkvan_sequence())  # clip 4 finished
            self.assertTrue(manager.einkvan_sequence_finished)

            # Further polling stays finished and doesn't replay anything.
            self.assertFalse(manager.update_einkvan_sequence())

    def test_dark_drone_loop_starts_and_stops(self):
        try:
            from audio import AudioManager
        except ModuleNotFoundError:
            _install_fake_engine_modules()
            from audio import AudioManager

        class _FakeChannel:
            def set_volume(self, *_args, **_kwargs):
                return None

            def play(self, *_args, **_kwargs):
                return None

            def stop(self, *_args, **_kwargs):
                return None

        with patch("audio.pygame.mixer.init"):
            manager = AudioManager()
        manager.available = True
        manager.dark_drone_sound = object()

        with patch("audio.pygame.mixer.find_channel", return_value=_FakeChannel()), patch(
            "audio.pygame.mixer.set_num_channels"
        ):
            manager.play_dark_drone_loop()
            self.assertTrue(manager.dark_drone_playing)

            # Calling it again while already playing doesn't restart it.
            manager.play_dark_drone_loop()
            self.assertTrue(manager.dark_drone_playing)

            manager.stop_dark_drone_loop()
            self.assertFalse(manager.dark_drone_playing)
            self.assertIsNone(manager.dark_drone_channel)

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

    def test_level_10_uses_standard_maze_generation(self):
        """Level 10 ("The final level") is not a special-cased hallway/open
        field like levels 5/7/9 -- it uses the same procedural maze as the
        regular chase levels, giving the fleeing child room to run and the
        player-monster room to hide before teleporting."""
        try:
            from maze import MazeManager
        except ModuleNotFoundError:
            _install_fake_engine_modules()
            from maze import MazeManager

        maze = MazeManager(seed=12345, level=10, cell_size=4.0, test=False)

        # Standard grid size (17), not one of the special-cased sizes (35/101/45).
        self.assertEqual(maze.grid_size, 17)
        self.assertIsNone(maze.monster_start_cell)
        self.assertTrue(maze.is_walkable_cell(maze.start_cell))
        self.assertTrue(maze.is_walkable_cell(maze.exit_cell))
        # A real interior maze is carved (unlike level 7's open field): not
        # every walkable cell has 4 walkable neighbors.
        neighbor_counts = [sum(1 for _ in maze.walkable_neighbors(cell)) for cell in maze.walkable_cells]
        self.assertTrue(any(count < 4 for count in neighbor_counts))

    def test_child_wanders_via_pathfinding_when_player_not_in_sight(self):
        """The child never stands fully still: it continuously explores the
        maze via simple pathfinding, and only switches to (faster) fleeing
        once the player-monster spots it within the player-monster's own
        field of view."""
        try:
            from maze import MazeManager
            from child import ChildCharacter
            from ursina import Vec3
        except ModuleNotFoundError:
            _install_fake_engine_modules()
            from maze import MazeManager
            from child import ChildCharacter
            from ursina import Vec3

        maze = MazeManager(seed=12345, level=10, cell_size=4.0, test=False)
        child = ChildCharacter(position=Vec3(0, -1000, 0))
        cx, cz = maze.world_from_cell(maze.exit_cell)
        child.place_at(Vec3(cx, 0.0, cz))
        start_position = (child.position.x, child.position.z)

        # Player nowhere near / never in the player-monster's field of view of the child.
        far_player_pos = Vec3(-9999.0, 0.0, -9999.0)
        with patch("child.is_position_visible", return_value=False), patch("child.time.dt", 0.1):
            child.update_child(maze, far_player_pos, run_elapsed=0.0)

        self.assertFalse(child.fleeing)
        self.assertNotEqual((child.position.x, child.position.z), start_position)

    def test_child_flees_at_sprint_speed_once_spotted_by_player(self):
        try:
            from maze import MazeManager
            from child import ChildCharacter
            from ursina import Vec3
        except ModuleNotFoundError:
            _install_fake_engine_modules()
            from maze import MazeManager
            from child import ChildCharacter
            from ursina import Vec3

        maze = MazeManager(seed=12345, level=10, cell_size=4.0, test=False)
        child = ChildCharacter(position=Vec3(0, -1000, 0))
        cx, cz = maze.world_from_cell(maze.exit_cell)
        child.place_at(Vec3(cx, 0.0, cz))
        start_position = (child.position.x, child.position.z)

        near_player_pos = Vec3(cx + 1.0, 0.0, cz)
        with patch("child.is_position_visible", return_value=True), patch("child.time.dt", 0.1):
            child.update_child(maze, near_player_pos, run_elapsed=0.0)

        self.assertTrue(child.fleeing)
        self.assertNotEqual((child.position.x, child.position.z), start_position)
        # Matches the player's own sprint speed from earlier levels
        # (walk_speed 6.0 * sprint_multiplier 1.65).
        self.assertAlmostEqual(child.flee_speed, 6.0 * 1.65, places=5)
        self.assertGreater(child.flee_speed, child.explore_speed)

    def test_child_moves_away_from_player_over_time_while_fleeing(self):
        """Regression test: the child must not path straight through/toward
        the player-monster while fleeing (previously `random_far_walkable_cell`
        picked a target relative only to the child's own position, which
        could route the "flee" path right back past the player). Over
        several simulated frames while continuously in sight, the child's
        distance from the player should trend upward, never collapsing back
        toward zero."""
        try:
            from maze import MazeManager
            from child import ChildCharacter
            from ursina import Vec3
        except ModuleNotFoundError:
            _install_fake_engine_modules()
            from maze import MazeManager
            from child import ChildCharacter
            from ursina import Vec3

        maze = MazeManager(seed=12345, level=10, cell_size=4.0, test=False)
        child = ChildCharacter(position=Vec3(0, -1000, 0))
        cx, cz = maze.world_from_cell(maze.exit_cell)
        child.place_at(Vec3(cx, 0.0, cz))

        # Player standing right next to the child (stationary), always in sight.
        player_pos = Vec3(cx + 1.0, 0.0, cz)

        min_distance_seen = (child.position - player_pos).length()
        with patch("child.is_position_visible", return_value=True), patch("child.time.dt", 0.15):
            for _ in range(40):
                child.update_child(maze, player_pos, run_elapsed=0.0)
                distance = (child.position - player_pos).length()
                min_distance_seen = min(min_distance_seen, distance)

        final_distance = (child.position - player_pos).length()
        # The child should have put real distance between itself and the
        # player, and should not have ended up back on top of it.
        self.assertGreater(final_distance, min_distance_seen)
        self.assertGreater(final_distance, 2.0)

    def test_child_flee_trigger_uses_players_field_of_view_not_its_own(self):
        """The child must flee based on whether the *player-monster* can see
        it (player's forward direction / FOV cone), not whether the child
        itself can see the player. A player facing away from the child
        should not trigger fleeing, even at close range with a clear line
        of sight."""
        try:
            from maze import MazeManager
            from child import ChildCharacter
            from ursina import Vec3
        except ModuleNotFoundError:
            _install_fake_engine_modules()
            from maze import MazeManager
            from child import ChildCharacter
            from ursina import Vec3

        maze = MazeManager(seed=12345, level=10, cell_size=4.0, test=False)
        child = ChildCharacter(position=Vec3(0, -1000, 0))
        cx, cz = maze.world_from_cell(maze.exit_cell)
        child.place_at(Vec3(cx, 0.0, cz))

        near_player_pos = Vec3(cx, 0.0, cz + 1.0)

        # Player facing directly away from the child: the child is behind
        # the player-monster, out of its field of view.
        player_forward_away = Vec3(0.0, 0.0, 1.0)
        with patch("child.time.dt", 0.1):
            child.update_child(maze, near_player_pos, player_forward_away, run_elapsed=0.0)
        self.assertFalse(child.fleeing)

        # Same distance/line of sight, but the player-monster now faces the
        # child directly: fleeing should trigger.
        player_forward_toward_child = Vec3(0.0, 0.0, -1.0)
        with patch("child.time.dt", 0.1):
            child.update_child(maze, near_player_pos, player_forward_toward_child, run_elapsed=0.0)
        self.assertTrue(child.fleeing)

    def test_child_gets_stuck_in_dead_end_instead_of_running_toward_player(self):
        """If every walkable neighbor of the child's current cell is closer
        to the player-monster than the child's own cell (a true dead end
        with the player blocking the only way out), the child must freeze in
        place rather than being forced to step toward/past the player."""
        try:
            from maze import MazeManager
            from child import ChildCharacter
            from ursina import Vec3
        except ModuleNotFoundError:
            _install_fake_engine_modules()
            from maze import MazeManager
            from child import ChildCharacter
            from ursina import Vec3

        maze = MazeManager(seed=12345, level=10, cell_size=4.0, test=False)
        child = ChildCharacter(position=Vec3(0, -1000, 0))
        cx, cz = maze.world_from_cell(maze.exit_cell)
        child.place_at(Vec3(cx, 0.0, cz))
        child_cell = maze.cell_from_world(child.position)

        # A dead-end stub: the only neighbor of the child's cell is the
        # player's own cell, which is strictly closer to the player than the
        # child's current cell (impossible for any real neighbor to be
        # farther away, since it *is* the player's cell).
        player_cell = (child_cell[0] + 1, child_cell[1])
        original_walkable_neighbors = maze.walkable_neighbors
        maze.walkable_neighbors = lambda cell: [player_cell] if cell == child_cell else original_walkable_neighbors(cell)

        px, pz = maze.world_from_cell(player_cell)
        player_world = Vec3(px, 0.0, pz)

        start_position = Vec3(child.position.x, child.position.y, child.position.z)
        with patch("child.is_position_visible", return_value=True), patch("child.time.dt", 0.2):
            for _ in range(10):
                child.update_child(maze, player_world, run_elapsed=0.0)

        self.assertTrue(child.fleeing)
        # The child must not have moved at all -- it should be stuck, not
        # forced toward the player.
        self.assertAlmostEqual(child.position.x, start_position.x, places=4)
        self.assertAlmostEqual(child.position.z, start_position.z, places=4)

    def test_astar_path_steers_around_an_avoided_cell(self):
        try:
            from monster import astar_path
        except ModuleNotFoundError:
            _install_fake_engine_modules()
            from monster import astar_path

        class _OpenGridMaze:
            """Minimal stand-in exposing only what `astar_path` needs: an
            open grid with no walls, so there are genuine alternate routes
            around any single avoided cell."""

            def __init__(self, width: int, height: int):
                self.width = width
                self.height = height

            def walkable_neighbors(self, cell):
                x, z = cell
                for nx, nz in ((x + 1, z), (x - 1, z), (x, z + 1), (x, z - 1)):
                    if 0 <= nx < self.width and 0 <= nz < self.height:
                        yield nx, nz

        maze = _OpenGridMaze(width=11, height=7)
        start_cell = (0, 3)
        goal_cell = (10, 3)
        avoid_cell = (5, 3)

        plain_path = astar_path(maze, start_cell, goal_cell)
        self.assertIn(avoid_cell, plain_path)

        steered_path = astar_path(maze, start_cell, goal_cell, avoid_cell=avoid_cell, avoid_radius=2.0, avoid_penalty=20.0)

        self.assertEqual(steered_path[0], start_cell)
        self.assertEqual(steered_path[-1], goal_cell)
        # With genuine alternate routes available on the open grid, the
        # steered route should detour around the avoided cell rather than
        # cutting straight through it.
        self.assertNotIn(avoid_cell, steered_path)


        try:
            from audio import AudioManager
        except ModuleNotFoundError:
            _install_fake_engine_modules()
            from audio import AudioManager

        with patch("audio.pygame.mixer.init"):
            manager = AudioManager()
        self.assertIsNotNone(manager.endgame_sound)

    def test_monster_footstep_sound_loads_and_overrides_regular_footsteps(self):
        try:
            from audio import AudioManager
        except ModuleNotFoundError:
            _install_fake_engine_modules()
            from audio import AudioManager

        with patch("audio.pygame.mixer.init"):
            manager = AudioManager()
        self.assertIsNotNone(manager.monster_footstep_sound)
        self.assertIs(manager._current_footstep_sound(), manager.footstep_sound)

        manager.set_footstep_monster_mode(True)
        self.assertIs(manager._current_footstep_sound(), manager.monster_footstep_sound)

    def test_level_10_disables_sprint_spider_and_the_regular_monster(self):
        try:
            from main import LiminalVibesGame
        except ModuleNotFoundError:
            _install_fake_engine_modules()
            from main import LiminalVibesGame

        game = LiminalVibesGame(test=True, start_level=10)
        self.assertTrue(game.player.no_sprint)
        self.assertTrue(game.player.use_monster_footstep)
        self.assertEqual(game.spider.spawn_delay_seconds, float("inf"))
        self.assertEqual(game.monster.spawn_delay_seconds, float("inf"))
        self.assertTrue(game.level10_vision_tint.enabled)
        self.assertTrue(game.level10_vein_overlay.enabled)
        self.assertTrue(game.child.spawned)

    def test_level_10_teleport_plays_monster_appearing_sound(self):
        try:
            from main import LiminalVibesGame
        except ModuleNotFoundError:
            _install_fake_engine_modules()
            from main import LiminalVibesGame

        game = LiminalVibesGame(test=True, start_level=10)
        with patch.object(game.audio, "play_monster_appearing", return_value=True) as mock_play:
            game._teleport_player()
            mock_play.assert_called_once()

    def test_level_9_touch_starts_cutscene_before_loading_level_10(self):
        try:
            from main import LiminalVibesGame
            from ursina import time as ursina_time
        except ModuleNotFoundError:
            _install_fake_engine_modules()
            from main import LiminalVibesGame
            from ursina import time as ursina_time

        game = LiminalVibesGame(test=True, start_level=9)
        game.player.position = game.monster.position
        ursina_time.dt = 0.1

        game.update()
        self.assertEqual(game.level, 9)
        self.assertTrue(game._level9_transition_active)
        self.assertTrue(game.ui.level9_transition_active)
        self.assertFalse(game.player.enabled)

        ursina_time.dt = (
            game.ui.level9_transition_black_hold_seconds
            + game.ui.level9_transition_sentence_duration * len(game.ui.level9_transition_messages)
            + 0.1
        )
        game.update()
        self.assertEqual(game.level, 10)
        self.assertTrue(game.ui.level9_transition_level_loaded)
        self.assertFalse(game.player.enabled)

        ursina_time.dt = game.ui.level9_transition_reveal_duration
        game.update()
        self.assertEqual(game.level, 10)
        self.assertFalse(game._level9_transition_active)
        self.assertTrue(game.player.enabled)

    def test_level_10_catch_freezes_and_starts_the_endgame_sequence(self):
        try:
            from main import LiminalVibesGame
            from ursina import time as ursina_time
        except ModuleNotFoundError:
            _install_fake_engine_modules()
            from main import LiminalVibesGame
            from ursina import time as ursina_time

        game = LiminalVibesGame(test=True, start_level=10)
        ursina_time.dt = 0.1

        # Move the child right on top of the player to force a catch.
        game.child.position = game.player.position
        with patch.object(game.audio, "play_endgame", return_value=True) as mock_play_endgame, \
                patch.object(game.audio, "play_monster_scream", return_value=True) as mock_play_scream:
            game.update()
            mock_play_endgame.assert_called_once()
            mock_play_scream.assert_called_once()

        self.assertTrue(game._level10_endgame_triggered)
        self.assertFalse(game.ui.run.running)
        self.assertTrue(game.ui.endgame_active)
        self.assertFalse(game.player.enabled)

    def test_endgame_screen_holds_until_restart_instead_of_auto_quitting(self):
        """The "END GAME" screen should stay up indefinitely once its
        fade/reveal animation completes -- the game must not auto-quit.
        Restart (R) and quit (ESC) remain available via the generic
        input() handling, since `run.running` is False throughout."""
        try:
            from game_state import GameStateUI
            from ursina import time as ursina_time
        except ModuleNotFoundError:
            _install_fake_engine_modules()
            from game_state import GameStateUI
            from ursina import time as ursina_time

        ui = GameStateUI()
        ui.on_endgame_caught()
        ursina_time.dt = ui.endgame_fade_duration + ui.endgame_hold_seconds + 5.0

        # game_state.py no longer imports/calls application.quit() for the
        # endgame sequence -- the screen just holds once finished.
        ui.update()

        self.assertTrue(ui.endgame_finished)
        self.assertTrue(ui.endgame_text.enabled)
        self.assertTrue(ui.endgame_hint.enabled)
        self.assertFalse(ui.run.running)

        # A further update() call should not error or re-trigger anything now
        # that the sequence is finished; the screen just holds.
        ui.update()
        self.assertTrue(ui.endgame_active)

    def test_restart_key_always_returns_to_level_1(self):
        """Pressing "R" after dying should always restart at level 1, even
        if the run was originally launched at a later --start-level (for
        example via dev/test tooling)."""
        try:
            from main import LiminalVibesGame
        except ModuleNotFoundError:
            _install_fake_engine_modules()
            from main import LiminalVibesGame

        game = LiminalVibesGame(test=True, start_level=5)
        self.assertEqual(game.level, 5)

        game.ui.run.running = False
        game.input("r")

        self.assertEqual(game.level, 1)
        self.assertEqual(game.start_level, 5)
        self.assertTrue(game.ui.run.running)


if __name__ == "__main__":
    unittest.main()
