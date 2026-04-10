from __future__ import annotations

from .models import DatasetSettingsSnapshot

VALID_VIEW_DISTRIBUTIONS = {"FULL_SPHERE", "UPPER_HEMISPHERE"}


def validate_settings(settings: DatasetSettingsSnapshot) -> list[str]:
    errors: list[str] = []

    if not settings.save_path:
        errors.append("Save Path is required.")
    if not settings.dataset_name:
        errors.append("Dataset Name is required.")
    if not settings.include_extension:
        errors.append("Brush compatibility requires Include Extension to be enabled.")
    if settings.total_frames <= 0:
        errors.append("Total Frames must be greater than zero.")
    if settings.point_sample_count <= 0:
        errors.append("Sample Count must be greater than zero.")
    if settings.min_radius <= 0.0:
        errors.append("Min Radius must be greater than zero.")
    if settings.max_radius <= 0.0:
        errors.append("Max Radius must be greater than zero.")
    if settings.min_radius >= settings.max_radius:
        errors.append("Min Radius must be smaller than Max Radius.")
    if not 0.0 <= settings.close_up_ratio <= 1.0:
        errors.append("Close-up Ratio must be between 0.0 and 1.0.")
    if settings.view_distribution not in VALID_VIEW_DISTRIBUTIONS:
        errors.append(f"Unsupported view distribution: {settings.view_distribution}")

    return errors
