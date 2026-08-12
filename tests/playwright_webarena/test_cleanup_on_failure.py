from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

try:
    from src.evaluator import MCPEvaluator
except ModuleNotFoundError:
    MCPEvaluator = None


class CleanupOnFailureTest(unittest.TestCase):
    @unittest.skipIf(MCPEvaluator is None, "project runtime dependencies not installed")
    def test_agent_exception_still_cleans_prepared_state(self) -> None:
        evaluator = MCPEvaluator.__new__(MCPEvaluator)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        evaluator.base_experiment_dir = Path(temporary.name)
        evaluator.state_manager = Mock()
        evaluator.state_manager.set_up.return_value = True
        evaluator.task_manager = Mock()
        evaluator.task_manager.get_task_instruction.return_value = "do the task"
        evaluator.agent = Mock()
        evaluator.agent.execute_sync.side_effect = RuntimeError("agent failed")
        evaluator.results_reporter = Mock()

        task = SimpleNamespace(
            name="cleanup-test", category_id="shopping_admin", task_id="1"
        )
        with self.assertRaisesRegex(RuntimeError, "agent failed"):
            evaluator._run_single_task(task)

        evaluator.state_manager.clean_up.assert_called_once_with(task)


if __name__ == "__main__":
    unittest.main()
