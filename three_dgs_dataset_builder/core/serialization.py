from __future__ import annotations

from .models import PointRecord


def build_render_stem(index: int) -> str:
    return f"{index:05d}"


def build_frame_path(index: int, include_extension: bool) -> str:
    suffix = ".png" if include_extension else ""
    return f"images/{build_render_stem(index)}{suffix}"


def build_transforms_payload(camera_info: dict, frames: list[dict], ply_file_path: str | None = None) -> dict:
    payload = dict(camera_info)
    if ply_file_path is not None:
        payload["ply_file_path"] = ply_file_path
    payload["frames"] = frames
    return payload


def build_dummy_test_payload(camera_info: dict, ply_file_path: str | None = None) -> dict:
    payload = dict(camera_info)
    if ply_file_path is not None:
        payload["ply_file_path"] = ply_file_path
    payload["frames"] = []
    return payload


def serialize_ply_ascii(points: list[PointRecord]) -> str:
    lines = [
        "ply",
        "format ascii 1.0",
        f"element vertex {len(points)}",
        "property float x",
        "property float y",
        "property float z",
        "property uchar red",
        "property uchar green",
        "property uchar blue",
        "end_header",
    ]

    for point in points:
        lines.append(
            f"{point.x:.8f} {point.y:.8f} {point.z:.8f} {point.color[0]} {point.color[1]} {point.color[2]}"
        )

    return "\n".join(lines) + "\n"
