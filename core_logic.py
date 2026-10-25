from __future__ import annotations


def format_mmss(seconds: float) -> str:
    total = max(0, int(seconds))
    minutes = total // 60
    secs = total % 60
    return f"{minutes:02d}:{secs:02d}"


def phased_speed(elapsed_since_spawn: float, phases: list[tuple[float, float]], max_speed: float) -> float:
    speed = phases[0][1] if phases else 0.0
    for start_time, phase_speed in phases:
        if elapsed_since_spawn >= start_time:
            speed = phase_speed
        else:
            break
    return min(speed, max_speed)


def clamp_fov(value: float, min_fov: float = 55.0, max_fov: float = 110.0) -> float:
    return max(min_fov, min(max_fov, float(value)))


def adjust_fov(current_fov: float, axis: float, delta_time: float, speed: float = 34.0, min_fov: float = 55.0, max_fov: float = 110.0) -> float:
    next_fov = current_fov + axis * speed * max(0.0, delta_time)
    return clamp_fov(next_fov, min_fov=min_fov, max_fov=max_fov)


def touches_exit_portal(
    player_x: float,
    player_z: float,
    exit_x: float,
    exit_z: float,
    exit_direction: tuple[int, int],
    cell_size: float,
    collider_radius: float = 0.45,
    portal_width_ratio: float = 0.5,
    contact_margin: float = 0.18,
) -> bool:
    dir_x, dir_z = exit_direction
    if (dir_x, dir_z) not in {(-1, 0), (1, 0), (0, -1), (0, 1)}:
        return False

    local_x = player_x - exit_x
    local_z = player_z - exit_z
    forward_offset = local_x * dir_x + local_z * dir_z
    lateral_offset = abs(local_x * (-dir_z) + local_z * dir_x)

    portal_half_width = cell_size * max(0.05, min(0.95, portal_width_ratio)) * 0.5
    touch_threshold = (cell_size * 0.5) - max(0.0, collider_radius) - max(0.0, contact_margin)

    return forward_offset >= touch_threshold and lateral_offset <= portal_half_width


def monster_arm_reach_factor(distance_to_player: float, reach_start_distance: float = 2.6, full_reach_distance: float = 1.0) -> float:
    if reach_start_distance <= full_reach_distance:
        return 1.0 if distance_to_player <= full_reach_distance else 0.0
    if distance_to_player >= reach_start_distance:
        return 0.0
    if distance_to_player <= full_reach_distance:
        return 1.0

    normalized = (reach_start_distance - distance_to_player) / (reach_start_distance - full_reach_distance)
    return normalized * normalized * (3.0 - 2.0 * normalized)



POWERUP_EXCLUDED_LEVELS = (1, 5, 7, 9, 10)


def level_has_powerups(level: int) -> bool:
    return level not in POWERUP_EXCLUDED_LEVELS


def find_dead_ends(walkable: set, exclude: tuple = ()) -> list:
    """Walkable cells with exactly one walkable 4-neighbour, sorted for determinism."""
    result = []
    for x, z in walkable:
        count = sum(1 for n in ((x + 1, z), (x - 1, z), (x, z + 1), (x, z - 1)) if n in walkable)
        if count == 1 and (x, z) not in exclude:
            result.append((x, z))
    return sorted(result)


def ray_hits_sphere(origin, direction, center, radius: float, max_distance: float = 1e9):
    """Distance along a normalized ray to a sphere, or None on a miss."""
    ox, oy, oz = origin
    dx, dy, dz = direction
    lx, ly, lz = center[0] - ox, center[1] - oy, center[2] - oz
    t_closest = lx * dx + ly * dy + lz * dz
    if t_closest < 0:
        return None
    dist_sq = lx * lx + ly * ly + lz * lz - t_closest * t_closest
    if dist_sq > radius * radius:
        return None
    t = t_closest - (radius * radius - dist_sq) ** 0.5
    t = max(0.0, t)
    return t if t <= max_distance else None
