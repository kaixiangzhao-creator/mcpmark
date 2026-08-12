from __future__ import annotations

import subprocess
from pathlib import Path

from .base import SnapshotDriver


class ReflinkSnapshotDriver(SnapshotDriver):
    """Use GNU cp reflinks when supported and fail instead of silently full-copying."""

    def clone_directory(self, source: Path, destination: Path) -> None:
        destination.mkdir(parents=True, exist_ok=False)
        result = subprocess.run(
            ["cp", "-a", "--reflink=always", f"{source}/.", str(destination)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if result.returncode:
            raise RuntimeError(
                f"reflink clone failed for {source}: {result.stderr.strip()}"
            )
