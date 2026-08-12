from __future__ import annotations

import unittest
from unittest.mock import Mock

from src.mcp_services.playwright_webarena.playwright_state_manager import (
    PlaywrightStateManager,
)
from src.mcp_services.playwright_webarena.state.aenv_backend import AEnvServiceBackend
from src.services import SERVICES


class WebArenaServiceConfigTest(unittest.TestCase):
    def test_external_state_settings_are_mapped_to_manager(self) -> None:
        definition = SERVICES["playwright_webarena"]
        schema = definition["config_schema"]
        mapping = definition["config_mapping"]["state_manager"]
        expected = {
            "state_backend",
            "state_root",
            "snapshot_driver",
            "runtime_registry",
            "media_mode",
            "reset_timeout",
            "keep_failed_state",
        }
        self.assertTrue(expected.issubset(schema))
        self.assertTrue(expected.issubset(mapping))
        self.assertEqual(schema["state_backend"]["default"], "legacy-docker")

    def test_external_runtime_maps_web_mcp_and_health_ports(self) -> None:
        manager = PlaywrightStateManager.__new__(PlaywrightStateManager)
        manager._run_cmd = Mock(
            side_effect=[
                Mock(returncode=0, stdout="127.0.0.1:20000\n", stderr=""),
                Mock(returncode=0, stdout="127.0.0.1:20001\n", stderr=""),
                Mock(returncode=0, stdout="127.0.0.1:20002\n", stderr=""),
            ]
        )
        self.assertEqual(manager._mapped_host_port("runtime", 8080), 20000)
        self.assertEqual(manager._mapped_host_port("runtime", 8081), 20001)
        self.assertEqual(manager._mapped_host_port("runtime", 49999), 20002)

    def test_aenv_requires_a_unique_preprovisioned_pvc(self) -> None:
        with self.assertRaisesRegex(ValueError, "must include"):
            AEnvServiceBackend("shared-baseline-pvc")
        backend = AEnvServiceBackend("mcpmark-{category}-{run_id}")
        self.assertIn("{run_id}", backend.pvc_name_template)


if __name__ == "__main__":
    unittest.main()
