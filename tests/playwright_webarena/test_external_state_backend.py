from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.mcp_services.playwright_webarena.state.external_backend import (
    ExternalStateBackend,
)


class ExternalStateBackendTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        baseline = self.root / "baselines" / "shopping-admin-v1-pristine"
        for name in ("mysql", "elasticsearch", "media"):
            (baseline / name).mkdir(parents=True)
            (baseline / name / "golden.txt").write_text(name, encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_prepare_uses_unique_owned_state_and_readonly_media(self) -> None:
        backend = ExternalStateBackend(
            self.root, snapshot_driver="copy", media_mode="readonly"
        )
        prepared = backend.prepare("shopping_admin", "task-001")

        self.assertEqual(prepared.run_id, "task-001")
        self.assertEqual(len(prepared.mounts), 2)
        self.assertFalse(prepared.mounts[0].readonly)
        self.assertTrue(prepared.mounts[1].readonly)
        self.assertEqual(prepared.mounts[1].target, "/aenv-data/media")
        self.assertNotIn("rw", prepared.mounts[0].docker_argument())
        self.assertTrue(prepared.mounts[1].docker_argument().endswith(",readonly"))
        self.assertEqual(
            (prepared.state_directory / "mysql" / "golden.txt").read_text(),
            "mysql",
        )

        (prepared.state_directory / "mysql" / "golden.txt").write_text("changed")
        baseline_file = (
            self.root
            / "baselines"
            / "shopping-admin-v1-pristine"
            / "mysql"
            / "golden.txt"
        )
        self.assertEqual(baseline_file.read_text(), "mysql")

        manifest = json.loads(
            (prepared.state_directory / "state.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["managed_by"], "mcpmark")
        backend.cleanup(prepared.cleanup_token, prepared.state_directory)
        self.assertFalse(prepared.state_directory.exists())
        backend.cleanup(prepared.cleanup_token, prepared.state_directory)

    def test_cleanup_rejects_wrong_token(self) -> None:
        backend = ExternalStateBackend(self.root, snapshot_driver="copy")
        prepared = backend.prepare("shopping_admin", "task-002")
        with self.assertRaisesRegex(ValueError, "does not own"):
            backend.cleanup("wrong", prepared.state_directory)
        self.assertTrue(prepared.state_directory.exists())

    def test_duplicate_run_id_does_not_overwrite(self) -> None:
        backend = ExternalStateBackend(self.root, snapshot_driver="copy")
        backend.prepare("shopping_admin", "same")
        with self.assertRaises(FileExistsError):
            backend.prepare("shopping_admin", "same")

    def test_parallel_slots_are_independent(self) -> None:
        backend = ExternalStateBackend(self.root, snapshot_driver="copy")
        first = backend.prepare("shopping_admin", "parallel-a")
        second = backend.prepare("shopping_admin", "parallel-b")
        (first.state_directory / "mysql" / "only-a.txt").write_text("a")
        self.assertFalse(
            (second.state_directory / "mysql" / "only-a.txt").exists()
        )
        backend.cleanup(first.cleanup_token, first.state_directory)
        self.assertTrue(second.state_directory.exists())


if __name__ == "__main__":
    unittest.main()
