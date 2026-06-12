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
