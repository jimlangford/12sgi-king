import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

from tools import local_ci


class LocalCITests(unittest.TestCase):
    def test_runs_shared_suite_with_isolated_artifacts(self):
        observed = {}

        def run(command, **kwargs):
            observed.update(command=command, **kwargs)
            self.assertTrue(Path(kwargs["env"]["COVERAGE_FILE"]).parent.is_dir())
            return subprocess.CompletedProcess(command, 0)

        with mock.patch.object(local_ci.subprocess, "run", side_effect=run):
            self.assertEqual(local_ci.main([]), 0)
        self.assertEqual(observed["command"][:3], [sys.executable, "-m", "pytest"])
        self.assertIn("tests/v2", observed["command"])
        self.assertIn("tests/test_studio_assets_crosswalk.py", observed["command"])
        self.assertEqual(observed["cwd"], local_ci.ROOT)
        self.assertEqual(observed["env"]["PYTHONHASHSEED"], "0")
        self.assertFalse(Path(observed["env"]["COVERAGE_FILE"]).parent.exists())

    def test_preserves_pytest_failure_and_report_destination(self):
        with mock.patch.object(
            local_ci.subprocess, "run", return_value=subprocess.CompletedProcess([], 5)
        ) as run:
            self.assertEqual(local_ci.main(["--junitxml", "results.xml"]), 5)
        self.assertIn(f"--junitxml={Path('results.xml').resolve()}", run.call_args.args[0])

    def test_does_not_mutate_parent_environment(self):
        before = dict(os.environ)
        with mock.patch.object(
            local_ci.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)
        ):
            local_ci.main([])
        self.assertEqual(dict(os.environ), before)
