from __future__ import annotations

import unittest

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


if __name__ == "__main__":
    unittest.main()
