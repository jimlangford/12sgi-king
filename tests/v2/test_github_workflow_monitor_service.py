import unittest
from types import SimpleNamespace
from unittest import mock

from services import github_workflow_monitor_service as service_module


class WorkflowMonitorServiceTests(unittest.TestCase):
    def test_starts_when_optional_repair_executor_is_unavailable(self):
        monitor = SimpleNamespace(executor=None)

        with mock.patch.object(service_module, "GitHubWorkflowMonitor", return_value=monitor):
            service = service_module.WorkflowMonitorService(dry_run=True)

        self.assertIs(service.monitor, monitor)
        self.assertTrue(service.dry_run)

    def test_forwards_dry_run_when_repair_executor_is_available(self):
        executor = SimpleNamespace(dry_run=False)
        monitor = SimpleNamespace(executor=executor)

        with mock.patch.object(service_module, "GitHubWorkflowMonitor", return_value=monitor):
            service_module.WorkflowMonitorService(dry_run=True)

        self.assertTrue(executor.dry_run)


if __name__ == "__main__":
    unittest.main()
