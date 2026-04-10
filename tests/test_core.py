import math
import random

from three_dgs_dataset_builder.core.models import DatasetSettingsSnapshot, PointRecord, WarningRecord
from three_dgs_dataset_builder.core.point_sampling import (
    PlainImageData,
    PlainMaterialData,
    PlainTriangleData,
    PointSamplingTaskData,
    sample_points,
)
from three_dgs_dataset_builder.core.sampling import CLOSE_UP_BAND_FRACTION, generate_camera_samples
from three_dgs_dataset_builder.core.serialization import (
    append_warning_once,
    build_materials_metadata,
    build_dummy_test_payload,
    build_frame_path,
    build_metadata_payload,
    serialize_ply_ascii,
)
from three_dgs_dataset_builder.core.transforms import (
    convert_point,
    convert_transform_rows,
)
from three_dgs_dataset_builder.core.validation import validate_settings


def test_convert_transform_rows_preserves_matrix_for_brush():
    matrix = [
        [1.0, 2.0, 3.0, 4.0],
        [5.0, 6.0, 7.0, 8.0],
        [9.0, 10.0, 11.0, 12.0],
        [13.0, 14.0, 15.0, 16.0],
    ]

    assert convert_transform_rows(matrix) == matrix


def test_convert_point_preserves_coordinates_for_brush():
    assert convert_point((1.0, 2.0, 3.0)) == (1.0, 2.0, 3.0)


def test_generate_camera_samples_respects_upper_hemisphere():
    samples = generate_camera_samples(
        total_frames=200,
        min_radius=1.0,
        max_radius=3.0,
        close_up_ratio=0.0,
        view_distribution="UPPER_HEMISPHERE",
        rng=random.Random(7),
    )

    assert all(sample.position[2] >= 0.0 for sample in samples)


def test_generate_camera_samples_biases_close_up_frames():
    min_radius = 2.0
    max_radius = 10.0
    samples = generate_camera_samples(
        total_frames=100,
        min_radius=min_radius,
        max_radius=max_radius,
        close_up_ratio=0.25,
        view_distribution="FULL_SPHERE",
        rng=random.Random(9),
    )

    threshold = min_radius + (max_radius - min_radius) * CLOSE_UP_BAND_FRACTION
    close_up_like = sum(
        1
        for sample in samples
        if math.dist(sample.position, (0.0, 0.0, 0.0)) <= threshold + 1e-9
    )

    assert close_up_like >= 25


def test_build_frame_path_can_omit_extension():
    assert build_frame_path(12, include_extension=True) == "images/00012.png"
    assert build_frame_path(12, include_extension=False) == "images/00012"


def test_build_dummy_test_payload_has_minimal_structure():
    payload = build_dummy_test_payload(
        {"camera_angle_x": 0.5, "w": 512, "h": 512},
        ply_file_path="points3d.ply",
    )
    assert payload == {
        "camera_angle_x": 0.5,
        "w": 512,
        "h": 512,
        "ply_file_path": "points3d.ply",
        "frames": [],
    }


def test_append_warning_once_deduplicates_by_key():
    warnings = []
    seen_keys = set()

    appended_first = append_warning_once(
        warnings,
        seen_keys,
        key="material_base_color_fallback:Mat_A",
        code="material_base_color_fallback",
        message="Material 'Mat_A' does not use a supported image texture chain; using base color fallback.",
    )
    appended_second = append_warning_once(
        warnings,
        seen_keys,
        key="material_base_color_fallback:Mat_A",
        code="material_base_color_fallback",
        message="Material 'Mat_A' does not use a supported image texture chain; using base color fallback.",
    )

    assert appended_first is True
    assert appended_second is False
    assert warnings == [
        WarningRecord(
            code="material_base_color_fallback",
            message="Material 'Mat_A' does not use a supported image texture chain; using base color fallback.",
        )
    ]


def test_build_materials_metadata_summarizes_triangle_usage():
    materials = build_materials_metadata(
        fallback_triangle_count=184,
        fallback_material_triangle_counts={
            "Mat_B": 64,
            "Mat_A": 120,
        },
    )

    assert materials == {
        "fallback_material_count": 2,
        "fallback_triangle_count": 184,
        "fallback_materials": [
            {"name": "Mat_A", "triangle_count": 120},
            {"name": "Mat_B", "triangle_count": 64},
        ],
    }


def test_build_metadata_payload_contains_warning_and_material_sections():
    payload = build_metadata_payload(
        addon_version="0.3.0",
        export_timestamp="2026-04-10T12:34:56Z",
        dataset_name="example",
        target_collection="Collection",
        frame_count=100,
        point_sample_count=50000,
        image_width=1024,
        image_height=1024,
        render_engine="CYCLES",
        diagnostics_log_file="three_dgs_dataset_builder.log",
        warnings=[
            WarningRecord(
                code="material_base_color_fallback",
                message="Material 'Mat_A' does not use a supported image texture chain; using base color fallback.",
            ),
            WarningRecord(
                code="no_material",
                message="Encountered mesh faces without an assigned material; using white fallback color.",
            ),
        ],
        fallback_triangle_count=184,
        fallback_material_triangle_counts={"Mat_A": 120, "Mat_B": 64},
    )

    assert payload == {
        "addon_version": "0.3.0",
        "export_timestamp": "2026-04-10T12:34:56Z",
        "dataset_name": "example",
        "target_collection": "Collection",
        "frame_count": 100,
        "point_sample_count": 50000,
        "image_resolution": {"width": 1024, "height": 1024},
        "render_engine": "CYCLES",
        "diagnostics": {"log_file": "three_dgs_dataset_builder.log"},
        "warnings": [
            {
                "code": "material_base_color_fallback",
                "message": (
                    "Material 'Mat_A' does not use a supported image texture chain; "
                    "using base color fallback."
                ),
            },
            {
                "code": "no_material",
                "message": "Encountered mesh faces without an assigned material; using white fallback color.",
            },
        ],
        "materials": {
            "fallback_material_count": 2,
            "fallback_triangle_count": 184,
            "fallback_materials": [
                {"name": "Mat_A", "triangle_count": 120},
                {"name": "Mat_B", "triangle_count": 64},
            ],
        },
    }


def test_serialize_ply_ascii_contains_header_and_rows():
    text = serialize_ply_ascii(
        [
            PointRecord(x=1.0, y=2.0, z=3.0, color=(4, 5, 6)),
            PointRecord(x=-1.5, y=0.0, z=8.25, color=(255, 0, 127)),
        ]
    )

    assert "element vertex 2" in text
    assert "1.00000000 2.00000000 3.00000000 4 5 6" in text
    assert "-1.50000000 0.00000000 8.25000000 255 0 127" in text


def test_sample_points_generates_requested_count_from_plain_triangle_data():
    task_data = PointSamplingTaskData(
        triangles=(
            PlainTriangleData(
                vertices=((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
                uvs=None,
                material_index=0,
            ),
        ),
        cumulative_areas=(0.5,),
        total_area=0.5,
        sample_count=8,
        random_seed=7,
        materials=(PlainMaterialData(base_color=(12, 34, 56), image_index=None),),
        images=(),
    )

    points = sample_points(task_data)

    assert len(points) == 8
    assert all(point.color == (12, 34, 56) for point in points)
    assert all(point.z == 0.0 for point in points)


def test_sample_points_uses_image_pixels_when_uvs_are_available():
    image_pixels = (
        1.0, 0.0, 0.0, 1.0,
        0.0, 1.0, 0.0, 1.0,
        0.0, 0.0, 1.0, 1.0,
        1.0, 1.0, 0.0, 1.0,
    )
    task_data = PointSamplingTaskData(
        triangles=(
            PlainTriangleData(
                vertices=((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
                uvs=((0.99, 0.99), (0.99, 0.99), (0.99, 0.99)),
                material_index=0,
            ),
        ),
        cumulative_areas=(0.5,),
        total_area=0.5,
        sample_count=1,
        random_seed=3,
        materials=(PlainMaterialData(base_color=(0, 0, 0), image_index=0),),
        images=(PlainImageData(width=2, height=2, pixels=image_pixels),),
    )

    points = sample_points(task_data)

    assert len(points) == 1
    assert points[0].color == (255, 255, 0)
    assert points[0].z == 0.0


def test_validate_settings_reports_common_errors():
    settings = DatasetSettingsSnapshot(
        save_path="",
        dataset_name="",
        include_extension=False,
        total_frames=0,
        min_radius=3.0,
        max_radius=2.0,
        close_up_ratio=1.5,
        view_distribution="SIDEWAYS",
        point_sample_count=0,
    )

    errors = validate_settings(settings)

    assert "Save Path is required." in errors
    assert "Dataset Name is required." in errors
    assert "Brush compatibility requires Include Extension to be enabled." in errors
    assert "Total Frames must be greater than zero." in errors
    assert "Min Radius must be smaller than Max Radius." in errors
    assert "Close-up Ratio must be between 0.0 and 1.0." in errors
    assert "Unsupported view distribution: SIDEWAYS" in errors
    assert "Sample Count must be greater than zero." in errors
