from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class SnapshotDriver(ABC):
    @abstractmethod
    def clone_directory(self, source: Path, destination: Path) -> None:
        """Create an independent writable clone at destination."""
