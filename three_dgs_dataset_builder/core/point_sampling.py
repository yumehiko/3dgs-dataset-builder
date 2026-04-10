from __future__ import annotations

import json
import math
import pickle
import random
import traceback
from bisect import bisect_left
from dataclasses import dataclass
from pathlib import Path

from .models import PointRecord
from .transforms import convert_point


@dataclass(frozen=True)
class PlainImageData:
    width: int
    height: int
    pixels: tuple[float, ...]


@dataclass(frozen=True)
class PlainMaterialData:
    base_color: tuple[int, int, int]
    image_index: int | None


@dataclass(frozen=True)
class PlainTriangleData:
    vertices: tuple[
        tuple[float, float, float],
        tuple[float, float, float],
        tuple[float, float, float],
    ]
    uvs: (
        tuple[
            tuple[float, float],
            tuple[float, float],
            tuple[float, float],
        ]
        | None
    )
    material_index: int


@dataclass(frozen=True)
class PointSamplingTaskData:
    triangles: tuple[PlainTriangleData, ...]
    cumulative_areas: tuple[float, ...]
    total_area: float
    sample_count: int
    random_seed: int
    materials: tuple[PlainMaterialData, ...]
    images: tuple[PlainImageData, ...]


def sample_points(
    task_data: PointSamplingTaskData,
    *,
    progress_callback=None,
    progress_interval: int = 2048,
) -> list[PointRecord]:
    rng = random.Random(task_data.random_seed)
    points: list[PointRecord] = []

    for index in range(task_data.sample_count):
        pick = rng.random() * task_data.total_area
        triangle_index = bisect_left(task_data.cumulative_areas, pick)
        triangle = task_data.triangles[min(triangle_index, len(task_data.triangles) - 1)]
        material = task_data.materials[triangle.material_index]

        world_point, uv = _sample_triangle(triangle.vertices, triangle.uvs, rng)
        color = _resolve_point_color(material, task_data.images, uv)
        converted_point = convert_point(world_point)
        points.append(
            PointRecord(
                x=converted_point[0],
                y=converted_point[1],
                z=converted_point[2],
                color=color,
            )
        )

        sampled_count = index + 1
        if progress_callback is not None and (
            sampled_count == task_data.sample_count
            or sampled_count % max(1, progress_interval) == 0
        ):
            progress_callback(sampled_count)

    return points


def run_worker(task_path: Path, progress_path: Path, result_path: Path, error_path: Path) -> int:
    try:
        task_data = pickle.loads(task_path.read_bytes())
        points = sample_points(
            task_data,
            progress_callback=lambda sampled_count: _write_progress(progress_path, sampled_count),
        )
        result_payload = {
            "sampled_count": len(points),
            "points": points,
        }
        _write_pickle(result_path, result_payload)
        _write_progress(progress_path, len(points))
        return 0
    except Exception:
        error_path.write_text(traceback.format_exc(), encoding="utf-8")
        return 1


def _sample_triangle(vertices, uvs, rng: random.Random):
    r1 = rng.random()
    r2 = rng.random()
    sqrt_r1 = math.sqrt(r1)
    weight_a = 1.0 - sqrt_r1
    weight_b = sqrt_r1 * (1.0 - r2)
    weight_c = sqrt_r1 * r2

    point = (
        vertices[0][0] * weight_a + vertices[1][0] * weight_b + vertices[2][0] * weight_c,
        vertices[0][1] * weight_a + vertices[1][1] * weight_b + vertices[2][1] * weight_c,
        vertices[0][2] * weight_a + vertices[1][2] * weight_b + vertices[2][2] * weight_c,
    )
    if uvs is None:
        return point, None

    uv = (
        uvs[0][0] * weight_a + uvs[1][0] * weight_b + uvs[2][0] * weight_c,
        uvs[0][1] * weight_a + uvs[1][1] * weight_b + uvs[2][1] * weight_c,
    )
    return point, uv


def _resolve_point_color(
    material: PlainMaterialData,
    images: tuple[PlainImageData, ...],
    uv,
) -> tuple[int, int, int]:
    if material.image_index is None or uv is None:
        return material.base_color
    sampled = _sample_image(images[material.image_index], uv)
    return sampled or material.base_color


def _sample_image(image: PlainImageData, uv) -> tuple[int, int, int] | None:
    width = image.width
    height = image.height
    if width <= 0 or height <= 0:
        return None

    u = uv[0] % 1.0
    v = uv[1] % 1.0
    x = min(width - 1, max(0, int(u * width)))
    y = min(height - 1, max(0, int(v * height)))
    index = (y * width + x) * 4
    pixels = image.pixels
    return _color_to_byte_tuple((pixels[index], pixels[index + 1], pixels[index + 2]))


def _color_to_byte_tuple(color) -> tuple[int, int, int]:
    return tuple(int(round(max(0.0, min(1.0, channel)) * 255.0)) for channel in color[:3])


def _write_pickle(path: Path, payload) -> None:
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_bytes(pickle.dumps(payload))
    temp_path.replace(path)


def _write_progress(path: Path, sampled_count: int) -> None:
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(
        json.dumps({"sampled_count": sampled_count}),
        encoding="utf-8",
    )
    temp_path.replace(path)
