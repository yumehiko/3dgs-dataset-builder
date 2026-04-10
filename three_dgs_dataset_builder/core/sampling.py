from __future__ import annotations

import math
import random

from .models import CameraSample

CLOSE_UP_BAND_FRACTION = 0.15


def generate_camera_samples(
    total_frames: int,
    min_radius: float,
    max_radius: float,
    close_up_ratio: float,
    view_distribution: str,
    rng: random.Random | None = None,
) -> list[CameraSample]:
    rng = rng or random.Random()
    close_up_count = int(round(total_frames * close_up_ratio))
    samples: list[CameraSample] = []

    for index in range(total_frames):
        is_close_up = index < close_up_count
        radius = _sample_radius(
            min_radius=min_radius,
            max_radius=max_radius,
            is_close_up=is_close_up,
            rng=rng,
        )
        position = _sample_direction(radius=radius, view_distribution=view_distribution, rng=rng)
        samples.append(CameraSample(position=position, is_close_up=is_close_up))

    rng.shuffle(samples)
    return samples


def _sample_radius(min_radius: float, max_radius: float, is_close_up: bool, rng: random.Random) -> float:
    if not is_close_up:
        return rng.uniform(min_radius, max_radius)

    span = max_radius - min_radius
    close_up_max = min_radius + span * CLOSE_UP_BAND_FRACTION
    return rng.uniform(min_radius, min(close_up_max, max_radius))


def _sample_direction(radius: float, view_distribution: str, rng: random.Random) -> tuple[float, float, float]:
    phi = rng.uniform(0.0, 2.0 * math.pi)
    if view_distribution == "UPPER_HEMISPHERE":
        z = rng.uniform(0.0, 1.0)
    else:
        z = rng.uniform(-1.0, 1.0)

    horizontal = math.sqrt(max(0.0, 1.0 - z * z))
    return (
        radius * horizontal * math.cos(phi),
        radius * horizontal * math.sin(phi),
        radius * z,
    )

