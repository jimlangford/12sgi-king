import json
import os
import shutil
import subprocess
import sys
import unittest
import uuid
from pathlib import Path
from unittest import mock

from tools import local_validation as validation


class LocalValidationTests(unittest.TestCase):
    def setUp(self):
        self.workspace = Path.cwd() / f".local-validation-test-{uuid.uuid4().hex}"
        self.workspace.mkdir()
        self.root = self.workspace / "checkout"
        self.root.mkdir()
        self.run = self.workspace / "output" / "run"
        self.run.mkdir(parents=True)
        self.root_patch = mock.patch.object(validation, "ROOT", self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)
        self.addCleanup(shutil.rmtree, self.workspace)

    def metadata(self):
        return mock.patch.object(
            validation, "git_metadata", return_value={"commit": "a" * 40, "dirty": True, "errors": []}
        )

    def test_artifacts_cannot_be_in_or_above_checkout_or_symlink_into_it(self):
        for path in (self.root, self.root / "site", self.workspace):
            with self.subTest(path=path), self.assertRaises(ValueError):
                validation.output_directory(path)
        if os.name == "posix":
            link = self.workspace / "link"
            link.symlink_to(self.root, target_is_directory=True)
            with self.assertRaises(ValueError):
                validation.output_directory(link)
        first = validation.output_directory(self.workspace / "reports")
        second = validation.output_directory(self.workspace / "reports")
        self.assertNotEqual(first, second)
        if os.name == "posix":
            self.assertEqual(first.stat().st_mode & 0o777, 0o700)
            parent = self.workspace / "reports"
            parent.chmod(0o755)
            validation.output_directory(parent)
            self.assertEqual(parent.stat().st_mode & 0o777, 0o755)

    def test_build_environment_isolates_every_profile_and_owner_override(self):
        inherited = {
            "PATH": os.defpath, "KA_SITE": "/owner/site", "PRIVATE_TOKEN": "do-not-record",
            "PYTHONPATH": "/owner/python", "KA_PROJECT": "/owner/project",
            **dict.fromkeys(validation.PROFILE_VARS, "/owner/home"),
        }
        with mock.patch.dict(os.environ, inherited, clear=True):
            env = validation.build_environment(self.run)
        for name in validation.PROFILE_VARS:
            self.assertEqual(env[name], str(self.run / "empty-home"))
        self.assertEqual(env["PATH"], os.defpath)
        self.assertEqual(env["KA_SITE"], str(self.run / "a11y/site"))
        self.assertNotIn("PRIVATE_TOKEN", env)
        self.assertNotIn("PYTHONPATH", env)
        self.assertNotIn("KA_PROJECT", env)
        self.assertEqual(list((self.run / "empty-home").iterdir()), [])

    def test_accessibility_filters_and_proposals_cannot_bypass_gate(self):
        inherited = {
            "A11Y_PAGES": "one.html", "A11Y_PROPOSE": "1", "A11Y_SHARD": "1/99",
            "A11Y_WORK_DIR": "/owner/output", "A11Y_DEADLINE_MS": "1",
        }
        with mock.patch.dict(os.environ, inherited):
            env = validation.accessibility_environment(self.run, None)
            explicit = validation.accessibility_environment(self.run, "2/4")
        for key in ("A11Y_PAGES", "A11Y_PROPOSE", "A11Y_SHARD", "A11Y_DEADLINE_MS"):
            self.assertNotIn(key, env)
        self.assertEqual(explicit["A11Y_SHARD"], "2/4")
        self.assertEqual(env["A11Y_WORK_DIR"], str(self.run / "a11y"))
        self.assertEqual(env["npm_config_offline"], "true")
        for key in ("npm_config_update_notifier", "npm_config_audit", "npm_config_fund"):
            self.assertEqual(env[key], "false")

    def test_missing_tool_timeout_and_failed_command_are_named_failures(self):
        for failure, expected in (
            (FileNotFoundError("sensitive exception"), "Missing required tool: missing-tool"),
            (subprocess.TimeoutExpired("sensitive command", 7), "Command exceeded 7s timeout"),
        ):
            with mock.patch.object(validation.subprocess, "Popen", side_effect=failure):
                result = validation.execute(
                    ["missing-tool"], self.root, {}, self.run / "private.log", 7,
                )
            self.assertNotEqual(result["exit_code"], 0)
            self.assertEqual(result["error"], expected)
            self.assertNotIn("sensitive", json.dumps(result))
        with mock.patch.object(validation.subprocess, "Popen") as process:
            process.return_value.wait.return_value = 8
            result = validation.execute(["tool"], self.root, {}, self.run / "private.log", 7)
        self.assertEqual(result["exit_code"], 8)
        if os.name == "posix":
            self.assertEqual((self.run / "private.log").stat().st_mode & 0o777, 0o600)

    def test_subprocess_uses_logs_not_receipt_for_secret_output(self):
        secret = "synthetic-private-output"

        def fake_run(command, **kwargs):
            kwargs["stdout"].write(secret)
            process = mock.Mock()
            process.wait.return_value = 1
            return process

        with mock.patch.object(validation.subprocess, "Popen", side_effect=fake_run):
            result = validation.execute(["tool"], self.root, {"SECRET": secret}, self.run / "tool.log", 7)
        self.assertNotIn(secret, json.dumps(result))
        self.assertEqual((self.run / "tool.log").read_text(), secret)

    def test_selected_stages_run_once_in_dependency_order_and_continue_after_failure(self):
        names = []

        def fake_stage(name, run, shard, built, **kwargs):
            names.append((name, built))
            return {"stage": name, "exit_code": int(name == "test")}

        with self.metadata(), mock.patch.object(validation, "stage", side_effect=fake_stage):
            code = validation.main([
                "--output-dir", str(self.workspace / "reports"),
                "--stage", "accessibility", "--stage", "test", "--stage", "test",
            ])
        self.assertEqual(code, 1)
        self.assertEqual(names, [("test", False), ("build", False), ("accessibility", True)])
        receipt = json.loads(next((self.workspace / "reports").glob("run-*/receipt.json")).read_text())
        self.assertEqual(receipt["selected_stages"], ["test", "build", "accessibility"])

    def test_default_runs_all_stages_and_receipt_keeps_status_boundaries(self):
        def fake_stage(name, *args, **kwargs):
            return {"stage": name, "exit_code": 0}

        with self.metadata(), mock.patch.dict(os.environ, {"PRIVATE_TOKEN": "never-in-receipt"}):
            with mock.patch.object(validation, "stage", side_effect=fake_stage):
                self.assertEqual(validation.main(["--output-dir", str(self.workspace / "reports")]), 0)
        receipt_path = next((self.workspace / "reports").glob("run-*/receipt.json"))
        text = receipt_path.read_text()
        receipt = json.loads(text)
        self.assertEqual([item["stage"] for item in receipt["stages"]], list(validation.STAGES))
        self.assertEqual(receipt["local_validation"], "passed")
        self.assertEqual(receipt["github"], {"status": "not checked", "approval": "unknown"})
        self.assertEqual(receipt["deployment"], "not attempted")
        self.assertTrue(receipt["git"]["dirty"])
        self.assertNotIn("never-in-receipt", text)
        if os.name == "posix":
            self.assertEqual(receipt_path.stat().st_mode & 0o777, 0o600)

    def test_git_metadata_failure_fails_local_result(self):
        metadata = {"commit": None, "dirty": None, "errors": ["Missing git"]}
        with mock.patch.object(validation, "git_metadata", return_value=metadata):
            with mock.patch.object(validation, "stage", return_value={"stage": "test", "exit_code": 0}):
                self.assertEqual(validation.main([
                    "--stage", "test", "--output-dir", str(self.workspace / "reports"),
                ]), 1)

    def test_build_failure_blocks_accessibility_without_commands(self):
        with mock.patch.object(validation, "execute") as execute:
            result = validation.stage("accessibility", self.run, None, False)
        self.assertEqual(result["exit_code"], 1)
        self.assertIn("Dependency failed", result["errors"][0])
        execute.assert_not_called()

    def test_helper_delegation_has_no_install_fetch_network_or_deploy_commands(self):
        def execute(command, *args):
            self.assertEqual(command[:2], [sys.executable, "tools/ci_checks.py"])
            self.assertEqual(command[2:], ["--stage", name])
            return {"exit_code": 0, "command": command}

        for name in validation.STAGES[1:5]:
            with mock.patch.object(validation, "execute", side_effect=execute):
                self.assertEqual(validation.stage(name, self.run, None, False)["exit_code"], 0)

    def test_explicit_lint_refs_are_forwarded_without_fetching(self):
        with mock.patch.object(validation, "execute", return_value={"exit_code": 0}) as execute:
            result = validation.stage("lint-python", self.run, None, False, "main", "HEAD")
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(execute.call_args.args[0], [
            sys.executable, "tools/ci_checks.py", "--stage", "lint-python",
            "--base", "main", "--head", "HEAD",
        ])

    def test_missing_accessibility_dependencies_fail_without_installing(self):
        with mock.patch.object(validation, "execute") as execute:
            result = validation.stage("accessibility", self.run, None, True)
        self.assertEqual(result["exit_code"], 1)
        self.assertIn("Missing locked accessibility dependencies", result["errors"][0])
        execute.assert_not_called()

    def test_browser_scratch_failure_is_actionable_without_environment_details(self):
        for name in ("axe-core", "puppeteer-core"):
            (self.root / "tools/a11y/node_modules" / name).mkdir(parents=True)
        with mock.patch.object(validation.shutil, "which", return_value="/tools/npm"):
            with mock.patch.object(
                validation, "browser_scratch_directory", side_effect=ValueError("private path")
            ):
                result = validation.stage("accessibility", self.run, None, True)
        self.assertEqual(result["exit_code"], 1)
        self.assertIn("set RUNNER_TEMP to a short writable external path", result["errors"][0])
        self.assertNotIn("private path", json.dumps(result))

    def test_existing_scanner_runs_only_test_and_scan_with_isolated_env(self):
        for name in ("axe-core", "puppeteer-core"):
            (self.root / "tools/a11y/node_modules" / name).mkdir(parents=True)
        calls = []

        def execute(command, cwd, env, *args):
            calls.append((command, env))
            if command[-1] == "scan":
                output = self.run / "a11y"
                output.mkdir()
                (output / "report.json").write_text(json.dumps({"pages": [{}], "errors": []}))
            return {"exit_code": 0, "command": command}

        with mock.patch.object(validation, "execute", side_effect=execute):
            with mock.patch.object(validation.shutil, "which", return_value="/tools/npm"):
                with mock.patch.object(validation, "browser_scratch_directory") as scratch:
                    scratch.return_value = self.workspace / "browser"
                    scratch.return_value.mkdir()
                    result = validation.stage("accessibility", self.run, "1/4", True)
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual([call[0] for call in calls], [
            ["/tools/npm", "test"], ["/tools/npm", "run", "scan"],
        ])
        self.assertTrue(all(call[1]["A11Y_SHARD"] == "1/4" for call in calls))
        self.assertTrue(all(call[1]["TMPDIR"] == str(self.workspace / "browser") for call in calls))
        self.assertFalse((self.workspace / "browser").exists())

    def test_build_metadata_checks_lane_failures_and_private_paths(self):
        site = self.run / "site"
        site.mkdir()
        (site / "index.html").write_text("<html></html>")
        info = {"lanes": [{"lane": f"lane-{n}", "ok": True} for n in range(29)], "lanes_failed": []}
        metadata = site / "buildinfo.json"
        metadata.write_text(json.dumps(info))
        self.assertEqual(validation.check_build(site)["lanes"], 29)
        for name in validation.FORBIDDEN:
            private = site / name
            private.parent.mkdir(parents=True, exist_ok=True)
            private.touch()
            with self.assertRaises(ValueError):
                validation.check_build(site)
            private.unlink()
        info["lanes"][0]["ok"] = False
        metadata.write_text(json.dumps(info))
        with self.assertRaises(ValueError):
            validation.check_build(site)
        info["lanes"] = []
        metadata.write_text(json.dumps(info))
        with self.assertRaises(ValueError):
            validation.check_build(site)
        info["lanes"] = [{"lane": "future-lane", "ok": True}]
        metadata.write_text(json.dumps(info))
        self.assertEqual(validation.check_build(site)["lanes"], 1)

    def test_failed_accessibility_gate_still_records_scan_coverage(self):
        for name in ("axe-core", "puppeteer-core"):
            (self.root / "tools/a11y/node_modules" / name).mkdir(parents=True)
        scratch = self.workspace / "browser"
        scratch.mkdir()

        def execute(command, *args):
            if command[-1] == "scan":
                output = self.run / "a11y"
                output.mkdir()
                (output / "report.json").write_text(json.dumps({
                    "pages": [{}], "errors": [], "regressions": [{}], "resolved": 2,
                }))
                return {"exit_code": 1, "error": "Regression gate failed"}
            return {"exit_code": 0}

        with mock.patch.object(validation, "execute", side_effect=execute):
            with mock.patch.object(validation.shutil, "which", return_value="/tools/npm"):
                with mock.patch.object(validation, "browser_scratch_directory", return_value=scratch):
                    result = validation.stage("accessibility", self.run, None, True)
        self.assertEqual(result["exit_code"], 1)
        self.assertEqual(result["coverage"], {
            "pages_scanned": 1, "shard": "all", "scan_errors": 0,
            "regressions": 1, "resolved_baseline_entries": 2,
        })

    def test_invalid_shards_are_usage_errors(self):
        for shard in ("0/4", "5/4", "a", "1/0"):
            with self.subTest(shard=shard), self.assertRaises(SystemExit) as result:
                validation.main(["--stage", "accessibility", "--shard", shard])
            self.assertEqual(result.exception.code, 2)
        with self.assertRaises(SystemExit):
            validation.main(["--stage", "test", "--shard", "1/4"])

    def test_shared_test_runner_requests_private_junit_and_coverage(self):
        def execute(command, *args):
            self.assertIn(f"--junitxml={self.run / 'test-results.xml'}", command)
            self.assertIn(f"--coverage-xml={self.run / 'coverage.xml'}", command)
            (self.run / "coverage.xml").write_text('<coverage line-rate="0.46"/>')
            return {"exit_code": 0, "command": command}

        with mock.patch.object(validation.importlib.util, "find_spec", return_value=object()):
            with mock.patch.object(validation, "execute", side_effect=execute):
                result = validation.stage("test", self.run, None, False)
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["coverage"]["line_rate"], 0.46)

    def test_failed_tests_still_report_available_coverage(self):
        def execute(command, *args):
            (self.run / "coverage.xml").write_text('<coverage line-rate="0.12"/>')
            return {"exit_code": 1, "command": command, "error": "Test failure"}

        with mock.patch.object(validation.importlib.util, "find_spec", return_value=object()):
            with mock.patch.object(validation, "execute", side_effect=execute):
                result = validation.stage("test", self.run, None, False)
        self.assertEqual(result["exit_code"], 1)
        self.assertEqual(result["coverage"]["line_rate"], 0.12)

    def test_missing_python_test_tools_are_named_failures(self):
        with mock.patch.object(validation.importlib.util, "find_spec", return_value=None):
            with mock.patch.object(validation, "execute") as execute:
                result = validation.stage("test", self.run, None, False)
        self.assertEqual(result["exit_code"], 1)
        self.assertIn("pytest, pytest_cov", result["errors"][0])
        execute.assert_not_called()

    @unittest.skipUnless(os.name == "posix", "POSIX permissions")
    def test_artifacts_copied_with_public_modes_are_sealed(self):
        directory = self.run / "copied-site"
        directory.mkdir(mode=0o755)
        page = directory / "index.html"
        page.write_text("public content in private scratch")
        page.chmod(0o644)
        validation.seal_artifacts(self.run)
        self.assertEqual(directory.stat().st_mode & 0o777, 0o700)
        self.assertEqual(page.stat().st_mode & 0o777, 0o600)

    @unittest.skipUnless(os.name == "posix", "POSIX process groups")
    def test_timeout_terminates_launched_process_group(self):
        with mock.patch.object(validation.subprocess, "Popen") as process:
            process.return_value.pid = 12345
            process.return_value.wait.side_effect = [subprocess.TimeoutExpired("tool", 1), 0]
            with mock.patch.object(validation.os, "killpg") as kill:
                result = validation.execute(["tool"], self.root, {}, self.run / "tool.log", 1)
        self.assertEqual(result["exit_code"], 1)
        self.assertEqual(result["descendant_cleanup"], "process group terminated")
        kill.assert_called_once_with(12345, validation.signal.SIGKILL)

    def test_windows_cleanup_uses_specific_pid_and_reaps_process(self):
        process = mock.Mock(pid=12345)
        with mock.patch.object(validation.os, "name", "nt"):
            # Keep concrete Paths native while exercising the Windows cleanup policy.
            with mock.patch.object(validation, "Path", return_value=self.run):
                with mock.patch.object(
                    validation.subprocess, "run",
                    return_value=subprocess.CompletedProcess([], 0),
                ) as run:
                    result = validation.terminate_tree(process)
        self.assertEqual(run.call_args.args[0][-4:], ["/PID", "12345", "/T", "/F"])
        self.assertEqual(result["descendant_cleanup"], "process tree terminated")
        process.wait.assert_called_once_with(timeout=10)

    @unittest.skipUnless(os.name == "posix", "POSIX process groups")
    def test_interruption_cleans_group_and_records_interrupted_command(self):
        with mock.patch.object(validation.subprocess, "Popen") as process:
            process.return_value.pid = 12345
            process.return_value.wait.side_effect = [KeyboardInterrupt, 0]
            with mock.patch.object(validation.os, "killpg") as kill:
                result = validation.execute(["tool"], self.root, {}, self.run / "tool.log", 1)
        self.assertEqual(result["exit_code"], 130)
        self.assertTrue(result["interrupted"])
        kill.assert_called_once_with(12345, validation.signal.SIGKILL)


if __name__ == "__main__":
    unittest.main()
