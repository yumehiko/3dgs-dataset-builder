from __future__ import annotations

def convert_transform_rows(matrix_rows: list[list[float]]) -> list[list[float]]:
    return [[float(value) for value in row] for row in matrix_rows]


def convert_point(point: tuple[float, float, float]) -> tuple[float, float, float]:
    return (float(point[0]), float(point[1]), float(point[2]))
