from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class MountSpec:
    source: Path
    target: str
    readonly: bool = False

    def docker_argument(self) -> str:
        argument = f"type=bind,src={self.source},dst={self.target}"
        return f"{argument},readonly" if self.readonly else argument


@dataclass(frozen=True)
class PreparedState:
    run_id: str
    profile: str
    mounts: tuple[MountSpec, ...]
    environment: dict[str, str]
    cleanup_token: str
    state_directory: Path
    metadata: dict[str, object] = field(default_factory=dict)
