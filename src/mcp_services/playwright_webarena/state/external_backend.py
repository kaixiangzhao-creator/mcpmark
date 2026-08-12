from __future__ import annotations

import json
import re
import shutil
import time
import uuid
from pathlib import Path

from .models import MountSpec, PreparedState
from .profiles import get_profile
from .snapshot import CopySnapshotDriver, ReflinkSnapshotDriver

_SAFE_RUN_ID = re.compile(r"[^a-zA-Z0-9_.-]+")


class ExternalStateBackend:
    """Prepare an isolated writable state slot from a read-only golden baseline."""

    def __init__(
        self,
        state_root: str | Path,
        snapshot_driver: str = "reflink",
        media_mode: str = "readonly",
        runtime_registry: str = "",
    ) -> None:
        self.state_root = Path(state_root).expanduser().resolve()
        self.media_mode = media_mode
        self.runtime_registry = runtime_registry
        if snapshot_driver == "reflink":
            self.driver = ReflinkSnapshotDriver()
        elif snapshot_driver == "copy":
            self.driver = CopySnapshotDriver()
        else:
            raise ValueError(f"unsupported snapshot driver: {snapshot_driver}")
        if media_mode not in {"readonly", "cow"}:
            raise ValueError(f"unsupported media mode: {media_mode}")

    def prepare(self, category: str, run_id: str | None = None) -> PreparedState:
        profile = get_profile(category, self.runtime_registry)
        safe_id = _SAFE_RUN_ID.sub("-", run_id or uuid.uuid4().hex).strip("-.")
        if not safe_id:
            raise ValueError("run_id must contain at least one safe character")

        baseline = self.state_root / "baselines" / profile.baseline_directory
        if not baseline.is_dir():
            raise FileNotFoundError(f"baseline does not exist: {baseline}")
        required = (*profile.mutable_directories, profile.media_directory)
        missing = [name for name in required if not (baseline / name).is_dir()]
        if missing:
            raise FileNotFoundError(
                f"baseline {baseline} is missing: {', '.join(missing)}"
            )

        runs_root = self.state_root / "runs" / category
        runs_root.mkdir(parents=True, exist_ok=True)
        final = runs_root / safe_id
        temporary = runs_root / f".{safe_id}.{uuid.uuid4().hex}.tmp"
        if final.exists():
            raise FileExistsError(f"run state already exists: {final}")

        cleanup_token = uuid.uuid4().hex
        try:
            temporary.mkdir()
            for name in profile.mutable_directories:
                self.driver.clone_directory(baseline / name, temporary / name)

            media_source = baseline / profile.media_directory
            if self.media_mode == "cow":
                self.driver.clone_directory(media_source, temporary / profile.media_directory)
            else:
                (temporary / profile.media_directory).mkdir()

            state_record = {
                "format": 1,
                "managed_by": "mcpmark",
                "cleanup_token": cleanup_token,
                "run_id": safe_id,
                "profile": category,
                "baseline": str(baseline),
                "media_mode": self.media_mode,
                "created_at": time.time(),
            }
            (temporary / "state.json").write_text(
                json.dumps(state_record, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            temporary.rename(final)
        except Exception:
            shutil.rmtree(temporary, ignore_errors=True)
            raise

        mounts = [MountSpec(final, "/aenv-data")]
        if self.media_mode == "readonly":
            mounts.append(
                MountSpec(
                    baseline / profile.media_directory,
                    f"/aenv-data/{profile.media_directory}",
                    readonly=True,
                )
            )
        return PreparedState(
            run_id=safe_id,
            profile=category,
            mounts=tuple(mounts),
            environment={"AENV_DATA_ROOT": "/aenv-data"},
            cleanup_token=cleanup_token,
            state_directory=final,
            metadata={
                "runtime_image": profile.runtime_image,
                "aenv_name": profile.aenv_name,
                "aenv_version": profile.aenv_version,
                "media_mode": self.media_mode,
            },
        )

    def cleanup(self, cleanup_token: str, state_directory: str | Path) -> None:
        state = Path(state_directory).expanduser().resolve()
        runs = (self.state_root / "runs").resolve()
        if runs not in state.parents:
            raise ValueError(f"refusing to clean unmanaged path: {state}")
        if not state.exists():
            return
        record_path = state / "state.json"
        try:
            record = json.loads(record_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"refusing to clean state without valid manifest: {state}") from exc
        if record.get("managed_by") != "mcpmark" or record.get("cleanup_token") != cleanup_token:
            raise ValueError(f"cleanup token does not own state: {state}")
        shutil.rmtree(state)

    def inspect(self, state_directory: str | Path) -> dict[str, object]:
        state = Path(state_directory).expanduser().resolve()
        return json.loads((state / "state.json").read_text(encoding="utf-8"))
