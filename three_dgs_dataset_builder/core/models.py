from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DatasetSettingsSnapshot:
    save_path: str
    dataset_name: str
    include_extension: bool
    total_frames: int
    min_radius: float
    max_radius: float
    close_up_ratio: float
    view_distribution: str
    point_sample_count: int


@dataclass(frozen=True)
class CameraSample:
    position: tuple[float, float, float]
    is_close_up: bool


@dataclass(frozen=True)
class PointRecord:
    x: float
    y: float
    z: float
    color: tuple[int, int, int]


@dataclass(frozen=True)
class WarningRecord:
    code: str
    message: str


@dataclass(frozen=True)
class MaterialFallbackRecord:
    name: str
    triangle_count: int
