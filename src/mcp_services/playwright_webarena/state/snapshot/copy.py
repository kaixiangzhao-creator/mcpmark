from __future__ import annotations

import shutil
from pathlib import Path

from .base import SnapshotDriver


class CopySnapshotDriver(SnapshotDriver):
    def clone_directory(self, source: Path, destination: Path) -> None:
        shutil.copytree(source, destination, symlinks=True)
