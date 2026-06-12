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


def monster_arm_reach_factor(distance_to_player: float, reach_start_distance: float = 2.6, full_reach_distance: float = 1.0) -> float:
    if reach_start_distance <= full_reach_distance:
        return 1.0 if distance_to_player <= full_reach_distance else 0.0
    if distance_to_player >= reach_start_distance:
        return 0.0
    if distance_to_player <= full_reach_distance:
        return 1.0

    normalized = (reach_start_distance - distance_to_player) / (reach_start_distance - full_reach_distance)
    return normalized * normalized * (3.0 - 2.0 * normalized)

