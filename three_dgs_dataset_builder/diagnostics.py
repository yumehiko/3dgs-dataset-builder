from __future__ import annotations

import faulthandler
import platform
import resource
import sys
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TextIO


@dataclass
class DiagnosticsSession:
    log_path: Path
    handle: TextIO
    faulthandler_owned: bool

    def info(self, message: str) -> None:
        self._write("INFO", message)

    def warning(self, message: str) -> None:
        self._write("WARN", message)

    def error(self, message: str) -> None:
        self._write("ERROR", message)

    def exception(self, message: str) -> None:
        self._write("ERROR", f"{message}\n{traceback.format_exc().rstrip()}")

    def close(self) -> None:
        try:
            self.info("Diagnostics session closed.")
        finally:
            if self.faulthandler_owned and faulthandler.is_enabled():
                try:
                    faulthandler.disable()
                except Exception:
                    pass
            self.handle.close()

    def _write(self, level: str, message: str) -> None:
        timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        self.handle.write(f"{timestamp} [{level}] {message.rstrip()}\n")
        self.handle.flush()


def start_diagnostics(output_dir: Path, *, dataset_name: str) -> DiagnosticsSession:
    output_dir.mkdir(parents=True, exist_ok=True)
    log_path = output_dir / "three_dgs_dataset_builder.log"
    handle = log_path.open("a", encoding="utf-8", buffering=1)
    faulthandler_owned = False

    if not faulthandler.is_enabled():
        try:
            faulthandler.enable(handle, all_threads=True)
            faulthandler_owned = True
        except Exception:
            faulthandler_owned = False

    session = DiagnosticsSession(
        log_path=log_path,
        handle=handle,
        faulthandler_owned=faulthandler_owned,
    )
    session.info(
        "Diagnostics session started "
        f"(dataset={dataset_name!r}, python={sys.version.split()[0]}, platform={platform.platform()})."
    )
    if faulthandler_owned:
        session.info("Python faulthandler enabled for fatal signal traces.")
    else:
        session.warning("Python faulthandler could not be enabled; hard native crashes may not emit Python traces.")
    return session


def format_peak_rss_mb() -> str:
    try:
        usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    except Exception:
        return "unknown"

    if sys.platform == "darwin":
        rss_mb = usage / (1024 * 1024)
    else:
        rss_mb = usage / 1024
    return f"{rss_mb:.1f} MB"
