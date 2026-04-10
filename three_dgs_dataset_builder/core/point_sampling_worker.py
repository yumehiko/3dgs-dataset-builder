from __future__ import annotations

import sys
from pathlib import Path


if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from three_dgs_dataset_builder.core.point_sampling import run_worker


def main(argv: list[str]) -> int:
    if len(argv) != 5:
        return 2
    task_path = Path(argv[1])
    progress_path = Path(argv[2])
    result_path = Path(argv[3])
    error_path = Path(argv[4])
    return run_worker(task_path, progress_path, result_path, error_path)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
