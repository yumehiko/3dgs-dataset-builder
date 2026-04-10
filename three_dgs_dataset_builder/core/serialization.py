from __future__ import annotations

from collections.abc import Mapping, Sequence

from .models import MaterialFallbackRecord, PointRecord, WarningRecord


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


def append_warning_once(
    warnings: list[WarningRecord],
    seen_keys: set[str],
    *,
    key: str,
    code: str,
    message: str,
) -> bool:
    if key in seen_keys:
        return False
    warnings.append(WarningRecord(code=code, message=message))
    seen_keys.add(key)
    return True


def build_materials_metadata(
    fallback_triangle_count: int,
    fallback_material_triangle_counts: Mapping[str, int],
) -> dict:
    fallback_materials = [
        MaterialFallbackRecord(name=name, triangle_count=triangle_count)
        for name, triangle_count in sorted(
            fallback_material_triangle_counts.items(),
            key=lambda item: (-item[1], item[0]),
        )
    ]
    return {
        "fallback_material_count": len(fallback_materials),
        "fallback_triangle_count": fallback_triangle_count,
        "fallback_materials": [
            {
                "name": record.name,
                "triangle_count": record.triangle_count,
            }
            for record in fallback_materials
        ],
    }


def build_metadata_payload(
    *,
    addon_version: str,
    export_timestamp: str,
    dataset_name: str,
    target_collection: str,
    frame_count: int,
    point_sample_count: int,
    image_width: int,
    image_height: int,
    render_engine: str,
    diagnostics_log_file: str | None,
    warnings: Sequence[WarningRecord],
    fallback_triangle_count: int,
    fallback_material_triangle_counts: Mapping[str, int],
) -> dict:
    payload = {
        "addon_version": addon_version,
        "export_timestamp": export_timestamp,
        "dataset_name": dataset_name,
        "target_collection": target_collection,
        "frame_count": frame_count,
        "point_sample_count": point_sample_count,
        "image_resolution": {
            "width": image_width,
            "height": image_height,
        },
        "render_engine": render_engine,
        "warnings": [
            {
                "code": warning.code,
                "message": warning.message,
            }
            for warning in warnings
        ],
        "materials": build_materials_metadata(
            fallback_triangle_count=fallback_triangle_count,
            fallback_material_triangle_counts=fallback_material_triangle_counts,
        ),
    }
    if diagnostics_log_file:
        payload["diagnostics"] = {"log_file": diagnostics_log_file}
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
