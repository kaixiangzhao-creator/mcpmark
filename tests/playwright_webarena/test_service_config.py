from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from src.mcp_services.playwright_webarena.playwright_state_manager import (
    PlaywrightStateManager,
)
from src.mcp_services.playwright_webarena.state.aenv_backend import (
    AEnvServiceBackend,
    PreparedAEnvService,
)
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

    def test_aenv_provider_injects_url_and_releases_service(self) -> None:
        manager = PlaywrightStateManager(
            state_backend="aenv",
            aenv_pvc_name_template="mcpmark-{category}-{run_id}",
        )
        backend = Mock()
        backend.prepare.return_value = PreparedAEnvService(
            run_id="run-1",
            category="shopping_admin",
            service_id="svc-1",
            service_url="https://runtime.example",
            pvc_name="mcpmark-shopping-admin-run-1",
            metadata={"aenv_name": "shopping-admin-final-0719@2.0.0"},
        )
        manager.aenv_backend = backend
        task = SimpleNamespace(name="aenv-test", category_id="shopping_admin")

        state = manager._create_aenv_initial_state(task)
        self.assertEqual(state.state_url, "https://runtime.example/admin")
        manager._store_initial_state_info(task, state)
        self.assertEqual(
            manager.get_service_config_for_agent()["base_url"],
            "https://runtime.example/admin",
        )
        resource = manager.tracked_resources[0]
        self.assertTrue(manager._cleanup_single_resource(resource))
        backend.cleanup.assert_called_once_with("svc-1")
        manager.skip_cleanup = True


if __name__ == "__main__":
    unittest.main()
