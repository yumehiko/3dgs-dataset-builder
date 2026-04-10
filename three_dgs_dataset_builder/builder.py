from __future__ import annotations

import json
import math
import os
import pickle
import random
import shutil
import subprocess
import sys
import tempfile
from bisect import bisect_left
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

from . import bl_info
from .core.models import CameraSample, DatasetSettingsSnapshot, PointRecord, WarningRecord
from .core.point_sampling import (
    PlainImageData,
    PlainMaterialData,
    PlainTriangleData,
    PointSamplingTaskData,
    sample_points,
)
from .core.sampling import generate_camera_samples
from .core.serialization import (
    append_warning_once,
    build_metadata_payload,
    build_dummy_test_payload,
    build_frame_path,
    build_render_stem,
    build_transforms_payload,
    serialize_ply_ascii,
)
from .core.transforms import convert_point, convert_transform_rows


class DatasetBuildError(RuntimeError):
    pass


@dataclass(frozen=True)
class BuildResult:
    output_dir: Path
    frame_count: int
    point_count: int
    warnings: tuple[WarningRecord, ...]
    fallback_material_count: int
    fallback_triangle_count: int


@dataclass(frozen=True)
class RenderState:
    scene_camera: object
    filepath: str
    use_file_extension: bool
    file_format: str
    color_mode: str
    film_transparent: bool
    use_lock_interface: bool


@dataclass(frozen=True)
class MaterialInfo:
    image: object | None
    base_color: tuple[int, int, int]
    material_name: str | None
    fallback_code: str | None


@dataclass(frozen=True)
class TriangleRecord:
    vertices: tuple[
        tuple[float, float, float],
        tuple[float, float, float],
        tuple[float, float, float],
    ]
    uvs: tuple[tuple[float, float], tuple[float, float], tuple[float, float]] | None
    material_index: int
    cumulative_area: float


@dataclass
class PointSamplingWorkerState:
    process: object | None
    temp_dir: Path
    task_path: Path
    progress_path: Path
    result_path: Path
    error_path: Path
    stderr_path: Path


@dataclass
class PointSamplingState:
    triangle_records: list[TriangleRecord]
    cumulative_areas: list[float]
    total_area: float
    sample_count: int
    materials: list[PlainMaterialData]
    images: list[PlainImageData]
    random_seed: int
    fallback_triangle_count: int = 0
    fallback_material_triangle_counts: dict[str, int] = field(default_factory=dict)
    points: list[PointRecord] = field(default_factory=list)
    sampled_count: int = 0
    worker_state: PointSamplingWorkerState | None = None


@dataclass
class BuildSession:
    scene: object
    target_collection: object
    snapshot: DatasetSettingsSnapshot
    output_dir: Path
    images_dir: Path
    render_state: RenderState
    temp_camera_obj: object
    focus_point: Vector
    camera_info: dict
    samples: list[CameraSample]
    frames: list[dict] = field(default_factory=list)
    warnings: list[WarningRecord] = field(default_factory=list)
    warning_keys: set[str] = field(default_factory=set)
    point_state: PointSamplingState | None = None


def build_dataset(context, settings, snapshot: DatasetSettingsSnapshot, output_dir: Path) -> BuildResult:
    session = begin_dataset_build(context, settings, snapshot, output_dir)
    try:
        while has_remaining_frames(session):
            render_next_frame(session)
        prepare_point_sampling(context, session)
        run_point_sampling_sync(session)
        return write_outputs(session)
    finally:
        cleanup_dataset_build(session)


def begin_dataset_build(context, settings, snapshot: DatasetSettingsSnapshot, output_dir: Path) -> BuildSession:
    target_collection = settings.target_collection
    if target_collection is None:
        raise DatasetBuildError("Target Collection is required.")

    mesh_objects = [obj for obj in target_collection.all_objects if obj.type == "MESH"]
    if not mesh_objects:
        raise DatasetBuildError("Target collection does not contain any mesh objects.")

    output_dir.mkdir(parents=True, exist_ok=True)
    images_dir = output_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    scene = context.scene
    render_state = _capture_render_state(scene)
    temp_camera_obj = _create_temp_camera(scene)

    try:
        _configure_render(scene)
        scene.camera = temp_camera_obj
        session = BuildSession(
            scene=scene,
            target_collection=target_collection,
            snapshot=snapshot,
            output_dir=output_dir,
            images_dir=images_dir,
            render_state=render_state,
            temp_camera_obj=temp_camera_obj,
            focus_point=_resolve_focus_point(settings.focus_object),
            camera_info=_build_camera_info(scene, temp_camera_obj),
            samples=generate_camera_samples(
                total_frames=snapshot.total_frames,
                min_radius=snapshot.min_radius,
                max_radius=snapshot.max_radius,
                close_up_ratio=snapshot.close_up_ratio,
                view_distribution=snapshot.view_distribution,
                rng=random.Random(),
            ),
        )
    except Exception:
        _restore_render_state(scene, render_state)
        _cleanup_temp_camera(temp_camera_obj)
        raise

    return session


def has_remaining_frames(session: BuildSession) -> bool:
    return len(session.frames) < len(session.samples)


def render_next_frame(session: BuildSession) -> int:
    frame_index = prepare_next_frame_render(session)
    bpy.ops.render.render(write_still=True)
    return finalize_rendered_frame(session, frame_index)


def prepare_next_frame_render(session: BuildSession) -> int:
    frame_index = len(session.frames)
    if frame_index >= len(session.samples):
        raise DatasetBuildError("No remaining frames to render.")
    sample = session.samples[frame_index]
    _place_camera(session.temp_camera_obj, sample.position, session.focus_point)
    render_stem = session.images_dir / build_render_stem(frame_index)
    session.scene.render.filepath = str(render_stem)
    return frame_index


def finalize_rendered_frame(session: BuildSession, frame_index: int) -> int:
    if frame_index != len(session.frames):
        raise DatasetBuildError("Rendered frame index is out of sequence.")
    if frame_index >= len(session.samples):
        raise DatasetBuildError("Rendered frame index exceeds planned samples.")
    session.frames.append(
        {
            "file_path": build_frame_path(frame_index, session.snapshot.include_extension),
            "transform_matrix": convert_transform_rows(_matrix_to_rows(session.temp_camera_obj.matrix_world)),
        }
    )
    return len(session.frames)


def prepare_point_sampling(context, session: BuildSession) -> PointSamplingState:
    if session.point_state is not None:
        return session.point_state

    point_state = _prepare_point_sampling_state(
        context=context,
        collection=session.target_collection,
        warnings=session.warnings,
        warning_keys=session.warning_keys,
        sample_count=session.snapshot.point_sample_count,
    )
    session.point_state = point_state
    return point_state


def sample_point_chunk(session: BuildSession, chunk_size: int = 1000) -> bool:
    if session.point_state is None:
        raise DatasetBuildError("Point sampling has not been prepared.")
    run_point_sampling_sync(session)
    return True


def run_point_sampling_sync(session: BuildSession) -> int:
    if session.point_state is None:
        raise DatasetBuildError("Point sampling has not been prepared.")

    point_state = session.point_state
    if point_state.points:
        return len(point_state.points)

    point_state.points = sample_points(_build_point_sampling_task_data(point_state))
    point_state.sampled_count = len(point_state.points)
    return point_state.sampled_count


def start_point_sampling_worker(session: BuildSession) -> None:
    if session.point_state is None:
        raise DatasetBuildError("Point sampling has not been prepared.")

    point_state = session.point_state
    if point_state.worker_state is not None:
        return

    temp_dir = Path(tempfile.mkdtemp(prefix="three_dgs_point_sampling_"))
    task_path = temp_dir / "task.pkl"
    progress_path = temp_dir / "progress.json"
    result_path = temp_dir / "result.pkl"
    error_path = temp_dir / "error.txt"
    stderr_path = temp_dir / "stderr.txt"
    task_path.write_bytes(pickle.dumps(_build_point_sampling_task_data(point_state)))

    python_executable = _resolve_python_executable()
    worker_script = Path(__file__).resolve().parent / "core" / "point_sampling_worker.py"
    worker_env = os.environ.copy()
    addon_parent = str(Path(__file__).resolve().parent.parent)
    existing_pythonpath = worker_env.get("PYTHONPATH", "")
    worker_env["PYTHONPATH"] = (
        addon_parent if not existing_pythonpath else os.pathsep.join((addon_parent, existing_pythonpath))
    )

    stderr_handle = stderr_path.open("w", encoding="utf-8")
    try:
        process = subprocess.Popen(
            [
                python_executable,
                str(worker_script),
                str(task_path),
                str(progress_path),
                str(result_path),
                str(error_path),
            ],
            stdout=subprocess.DEVNULL,
            stderr=stderr_handle,
            env=worker_env,
        )
    except Exception:
        stderr_handle.close()
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise
    else:
        stderr_handle.close()

    point_state.worker_state = PointSamplingWorkerState(
        process=process,
        temp_dir=temp_dir,
        task_path=task_path,
        progress_path=progress_path,
        result_path=result_path,
        error_path=error_path,
        stderr_path=stderr_path,
    )


def poll_point_sampling_worker(session: BuildSession) -> bool:
    if session.point_state is None:
        raise DatasetBuildError("Point sampling has not been prepared.")

    point_state = session.point_state
    worker_state = point_state.worker_state
    if worker_state is None:
        raise DatasetBuildError("Point sampling worker has not been started.")

    if worker_state.progress_path.exists():
        try:
            progress_payload = json.loads(worker_state.progress_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            progress_payload = None
        if isinstance(progress_payload, dict):
            point_state.sampled_count = max(
                point_state.sampled_count,
                int(progress_payload.get("sampled_count", point_state.sampled_count)),
            )

    if worker_state.error_path.exists():
        message = worker_state.error_path.read_text(encoding="utf-8").strip() or "Point sampling worker failed."
        raise DatasetBuildError(message)

    if worker_state.result_path.exists():
        result_payload = pickle.loads(worker_state.result_path.read_bytes())
        point_state.points = list(result_payload["points"])
        point_state.sampled_count = int(result_payload.get("sampled_count", len(point_state.points)))
        _wait_for_worker_process(worker_state.process)
        return True

    if worker_state.process is not None:
        return_code = worker_state.process.poll()
        if return_code is not None and return_code != 0:
            stderr_text = ""
            if worker_state.stderr_path.exists():
                stderr_text = worker_state.stderr_path.read_text(encoding="utf-8").strip()
            message = stderr_text or "Point sampling worker exited before producing a result."
            raise DatasetBuildError(message)

    return False


def cancel_point_sampling_worker(session: BuildSession) -> None:
    point_state = session.point_state
    if point_state is None or point_state.worker_state is None:
        return
    worker_state = point_state.worker_state
    process = worker_state.process
    if process is not None and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2.0)
    point_state.worker_state = None
    shutil.rmtree(worker_state.temp_dir, ignore_errors=True)


def write_outputs(session: BuildSession) -> BuildResult:
    if session.point_state is None:
        raise DatasetBuildError("Point sampling has not been prepared.")

    transforms_train = build_transforms_payload(
        camera_info=session.camera_info,
        frames=session.frames,
        ply_file_path="points3d.ply",
    )
    transforms_test = build_dummy_test_payload(
        camera_info=session.camera_info,
        ply_file_path="points3d.ply",
    )
    (session.output_dir / "transforms_train.json").write_text(
        json.dumps(transforms_train, indent=2),
        encoding="utf-8",
    )
    (session.output_dir / "transforms_test.json").write_text(
        json.dumps(transforms_test, indent=2),
        encoding="utf-8",
    )
    (session.output_dir / "points3d.ply").write_text(
        serialize_ply_ascii(session.point_state.points),
        encoding="utf-8",
    )
    (session.output_dir / "metadata.json").write_text(
        json.dumps(
            build_metadata_payload(
                addon_version=_addon_version_string(),
                export_timestamp=_export_timestamp_utc(),
                dataset_name=session.snapshot.dataset_name,
                target_collection=session.target_collection.name,
                frame_count=len(session.frames),
                point_sample_count=len(session.point_state.points),
                image_width=int(session.camera_info["w"]),
                image_height=int(session.camera_info["h"]),
                render_engine=session.scene.render.engine,
                warnings=session.warnings,
                fallback_triangle_count=session.point_state.fallback_triangle_count,
                fallback_material_triangle_counts=session.point_state.fallback_material_triangle_counts,
            ),
            indent=2,
        ),
        encoding="utf-8",
    )

    return BuildResult(
        output_dir=session.output_dir,
        frame_count=len(session.frames),
        point_count=len(session.point_state.points),
        warnings=tuple(session.warnings),
        fallback_material_count=len(session.point_state.fallback_material_triangle_counts),
        fallback_triangle_count=session.point_state.fallback_triangle_count,
    )


def cleanup_dataset_build(session: BuildSession) -> None:
    cancel_point_sampling_worker(session)
    _restore_render_state(session.scene, session.render_state)
    _cleanup_temp_camera(session.temp_camera_obj)


def _capture_render_state(scene) -> RenderState:
    return RenderState(
        scene_camera=scene.camera,
        filepath=scene.render.filepath,
        use_file_extension=scene.render.use_file_extension,
        file_format=scene.render.image_settings.file_format,
        color_mode=scene.render.image_settings.color_mode,
        film_transparent=scene.render.film_transparent,
        use_lock_interface=scene.render.use_lock_interface,
    )


def _configure_render(scene) -> None:
    scene.render.use_file_extension = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = True
    scene.render.use_lock_interface = False


def _restore_render_state(scene, state: RenderState) -> None:
    scene.camera = state.scene_camera
    scene.render.filepath = state.filepath
    scene.render.use_file_extension = state.use_file_extension
    scene.render.image_settings.file_format = state.file_format
    scene.render.image_settings.color_mode = state.color_mode
    scene.render.film_transparent = state.film_transparent
    scene.render.use_lock_interface = state.use_lock_interface


def _create_temp_camera(scene):
    camera_data = bpy.data.cameras.new("ThreeDGSDatasetCamera")
    camera_data.type = "PERSP"

    if scene.camera and scene.camera.type == "CAMERA":
        source = scene.camera.data
        if source.type == "PERSP":
            camera_data.lens = source.lens
            camera_data.sensor_fit = source.sensor_fit
            camera_data.sensor_width = source.sensor_width
            camera_data.sensor_height = source.sensor_height
            camera_data.shift_x = source.shift_x
            camera_data.shift_y = source.shift_y
            camera_data.clip_start = source.clip_start
            camera_data.clip_end = source.clip_end

    camera_object = bpy.data.objects.new("ThreeDGSDatasetCamera", camera_data)
    scene.collection.objects.link(camera_object)
    return camera_object


def _cleanup_temp_camera(camera_object) -> None:
    camera_data = camera_object.data
    if camera_object.users_collection:
        for collection in list(camera_object.users_collection):
            collection.objects.unlink(camera_object)
    bpy.data.objects.remove(camera_object)
    if camera_data.users == 0:
        bpy.data.cameras.remove(camera_data)


def _resolve_focus_point(focus_object) -> Vector:
    if focus_object is None:
        return Vector((0.0, 0.0, 0.0))
    return focus_object.matrix_world.translation.copy()


def _place_camera(camera_object, position, target: Vector) -> None:
    position_vec = Vector(position)
    direction = target - position_vec
    if direction.length == 0.0:
        raise DatasetBuildError("Camera sample coincides with focus point.")

    camera_object.location = position_vec
    camera_object.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def _build_camera_info(scene, camera_object) -> dict:
    camera = camera_object.data
    if camera.type != "PERSP":
        raise DatasetBuildError("3DGS export requires a perspective camera.")

    width = int(scene.render.resolution_x * scene.render.resolution_percentage / 100)
    height = int(scene.render.resolution_y * scene.render.resolution_percentage / 100)
    pixel_aspect = scene.render.pixel_aspect_x / scene.render.pixel_aspect_y
    sensor_fit = camera.sensor_fit
    if sensor_fit == "AUTO":
        sensor_fit = "HORIZONTAL" if width * pixel_aspect >= height else "VERTICAL"

    if sensor_fit == "VERTICAL":
        fl_x = camera.lens / camera.sensor_height * height * pixel_aspect
        fl_y = camera.lens / camera.sensor_height * height
    else:
        fl_x = camera.lens / camera.sensor_width * width
        fl_y = camera.lens / camera.sensor_width * width / pixel_aspect

    camera_angle_x = 2.0 * math.atan(width / (2.0 * fl_x))
    camera_angle_y = 2.0 * math.atan(height / (2.0 * fl_y))

    return {
        "camera_angle_x": camera_angle_x,
        "camera_angle_y": camera_angle_y,
        "fl_x": fl_x,
        "fl_y": fl_y,
        "cx": width / 2.0 - (camera.shift_x * width),
        "cy": height / 2.0 + (camera.shift_y * height),
        "w": width,
        "h": height,
    }


def _matrix_to_rows(matrix: Matrix) -> list[list[float]]:
    return [[float(value) for value in row] for row in matrix]


def _prepare_point_sampling_state(
    context,
    collection,
    warnings: list[WarningRecord],
    warning_keys: set[str],
    sample_count: int,
) -> PointSamplingState:
    depsgraph = context.evaluated_depsgraph_get()
    triangle_records: list[TriangleRecord] = []
    cumulative_areas: list[float] = []
    cumulative_area = 0.0
    fallback_triangle_count = 0
    fallback_material_triangle_counts: dict[str, int] = {}
    images: list[PlainImageData] = []
    image_lookup: dict[int, int] = {}
    materials: list[PlainMaterialData] = []
    material_lookup: dict[tuple[tuple[int, int, int], int | None], int] = {}

    for obj in collection.all_objects:
        if obj.type != "MESH":
            continue

        evaluated_obj = obj.evaluated_get(depsgraph)
        mesh = evaluated_obj.to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)
        if mesh is None:
            continue

        try:
            mesh.calc_loop_triangles()
            if not mesh.loop_triangles:
                continue

            uv_layer = mesh.uv_layers.active.data if mesh.uv_layers.active else None
            material_infos = [_resolve_material_info(material) for material in mesh.materials]
            material_indices = [
                _intern_plain_material(material_info, materials, material_lookup, images, image_lookup)
                for material_info in material_infos
            ]

            for triangle in mesh.loop_triangles:
                area = float(triangle.area)
                if area <= 0.0:
                    continue

                material_index = triangle.material_index
                material_info = (
                    material_infos[material_index]
                    if 0 <= material_index < len(material_infos)
                    else _fallback_material_info("missing_material")
                )
                plain_material_index = (
                    material_indices[material_index]
                    if 0 <= material_index < len(material_indices)
                    else _intern_plain_material(
                        _fallback_material_info("missing_material"),
                        materials,
                        material_lookup,
                        images,
                        image_lookup,
                    )
                )
                if material_info.fallback_code is not None:
                    fallback_triangle_count += 1
                    if material_info.material_name is not None:
                        fallback_material_triangle_counts[material_info.material_name] = (
                            fallback_material_triangle_counts.get(material_info.material_name, 0) + 1
                        )
                    _append_warning_for_material_info(
                        material_info,
                        warnings,
                        warning_keys,
                    )
                cumulative_area += area
                triangle_records.append(
                    TriangleRecord(
                        vertices=tuple(
                            _vector_to_tuple(evaluated_obj.matrix_world @ mesh.vertices[index].co)
                            for index in triangle.vertices
                        ),
                        uvs=(
                            tuple(tuple(float(v) for v in uv_layer[loop_index].uv) for loop_index in triangle.loops)
                            if uv_layer is not None
                            else None
                        ),
                        material_index=plain_material_index,
                        cumulative_area=cumulative_area,
                    )
                )
                cumulative_areas.append(cumulative_area)
        finally:
            evaluated_obj.to_mesh_clear()

    if not triangle_records:
        raise DatasetBuildError("Target collection does not contain any renderable mesh surface.")

    return PointSamplingState(
        triangle_records=triangle_records,
        cumulative_areas=cumulative_areas,
        total_area=cumulative_areas[-1],
        sample_count=sample_count,
        materials=materials,
        images=images,
        random_seed=random.randrange(0, 2**32),
        fallback_triangle_count=fallback_triangle_count,
        fallback_material_triangle_counts=fallback_material_triangle_counts,
    )


def _resolve_material_info(material) -> MaterialInfo:
    if material is None:
        return _fallback_material_info("no_material")

    image = None
    base_color = material.diffuse_color[:3] if hasattr(material, "diffuse_color") else (1.0, 1.0, 1.0)

    if material.use_nodes and material.node_tree:
        principled = next(
            (node for node in material.node_tree.nodes if node.type == "BSDF_PRINCIPLED"),
            None,
        )
        if principled is not None:
            base_input = principled.inputs.get("Base Color")
            if base_input is not None:
                base_color = tuple(base_input.default_value[:3])
                if base_input.is_linked:
                    image = _find_linked_image(base_input.links[0].from_node, set())

    if image is None:
        fallback_code = "material_base_color_fallback"
    else:
        fallback_code = None

    return MaterialInfo(
        image=image,
        base_color=_color_to_byte_tuple(base_color),
        material_name=material.name,
        fallback_code=fallback_code,
    )


def _fallback_material_info(key: str) -> MaterialInfo:
    return MaterialInfo(image=None, base_color=(255, 255, 255), material_name=None, fallback_code=key)


def _append_warning(
    warnings: list[WarningRecord],
    warning_keys: set[str],
    *,
    key: str,
    code: str,
    message: str,
) -> None:
    append_warning_once(
        warnings,
        warning_keys,
        key=key,
        code=code,
        message=message,
    )


def _append_warning_for_material_info(
    material_info: MaterialInfo,
    warnings: list[WarningRecord],
    warning_keys: set[str],
) -> None:
    if material_info.fallback_code == "material_base_color_fallback" and material_info.material_name is not None:
        _append_warning(
            warnings,
            warning_keys,
            key=f"material_base_color_fallback:{material_info.material_name}",
            code="material_base_color_fallback",
            message=(
                f"Material '{material_info.material_name}' does not use a supported image texture chain; "
                "using base color fallback."
            ),
        )
    elif material_info.fallback_code == "no_material":
        _append_warning(
            warnings,
            warning_keys,
            key="no_material",
            code="no_material",
            message="Encountered mesh faces without an assigned material; using white fallback color.",
        )
    elif material_info.fallback_code == "missing_material":
        _append_warning(
            warnings,
            warning_keys,
            key="missing_material",
            code="missing_material",
            message="Encountered mesh faces referencing a missing material slot; using white fallback color.",
        )


def _addon_version_string() -> str:
    return ".".join(str(part) for part in bl_info["version"])


def _export_timestamp_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _find_linked_image(node, visited: set) -> object | None:
    if node is None:
        return None
    node_key = id(node)
    if node_key in visited:
        return None
    visited.add(node_key)

    if node.type == "TEX_IMAGE" and getattr(node, "image", None) is not None:
        return node.image

    for input_socket in getattr(node, "inputs", []):
        if input_socket.is_linked:
            for link in input_socket.links:
                found = _find_linked_image(link.from_node, visited)
                if found is not None:
                    return found
    return None


def _build_point_sampling_task_data(point_state: PointSamplingState) -> PointSamplingTaskData:
    return PointSamplingTaskData(
        triangles=tuple(
            PlainTriangleData(
                vertices=triangle.vertices,
                uvs=triangle.uvs,
                material_index=triangle.material_index,
            )
            for triangle in point_state.triangle_records
        ),
        cumulative_areas=tuple(point_state.cumulative_areas),
        total_area=point_state.total_area,
        sample_count=point_state.sample_count,
        random_seed=point_state.random_seed,
        materials=tuple(point_state.materials),
        images=tuple(point_state.images),
    )


def _intern_plain_material(
    material_info: MaterialInfo,
    materials: list[PlainMaterialData],
    material_lookup: dict[tuple[tuple[int, int, int], int | None], int],
    images: list[PlainImageData],
    image_lookup: dict[int, int],
) -> int:
    image_index = _intern_plain_image(material_info.image, images, image_lookup)
    material_key = (material_info.base_color, image_index)
    cached_index = material_lookup.get(material_key)
    if cached_index is not None:
        return cached_index

    material_index = len(materials)
    materials.append(PlainMaterialData(base_color=material_info.base_color, image_index=image_index))
    material_lookup[material_key] = material_index
    return material_index


def _intern_plain_image(
    image,
    images: list[PlainImageData],
    image_lookup: dict[int, int],
) -> int | None:
    if image is None:
        return None
    image_key = id(image)
    cached_index = image_lookup.get(image_key)
    if cached_index is not None:
        return cached_index

    image_index = len(images)
    width = int(image.size[0])
    height = int(image.size[1])
    images.append(
        PlainImageData(
            width=width,
            height=height,
            pixels=tuple(float(channel) for channel in image.pixels),
        )
    )
    image_lookup[image_key] = image_index
    return image_index


def _resolve_python_executable() -> str:
    blender_python = getattr(bpy.app, "binary_path_python", "")
    if blender_python:
        return blender_python
    if sys.executable:
        return sys.executable
    raise DatasetBuildError("Could not resolve a Python interpreter for point sampling.")


def _wait_for_worker_process(process) -> None:
    if process is None:
        return
    try:
        process.wait(timeout=0.1)
    except subprocess.TimeoutExpired:
        return


def _vector_to_tuple(vector: Vector) -> tuple[float, float, float]:
    return (float(vector.x), float(vector.y), float(vector.z))


def _color_to_byte_tuple(color) -> tuple[int, int, int]:
    return tuple(int(round(max(0.0, min(1.0, channel)) * 255.0)) for channel in color[:3])
