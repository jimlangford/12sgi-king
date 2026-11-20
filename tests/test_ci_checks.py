"""Offline regression coverage for shared CI policy and fail-closed execution."""

import argparse
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import ci_checks


class CICheckTests(unittest.TestCase):
    def setUp(self):
        work = tempfile.TemporaryDirectory(prefix=".ci-checks-test-", dir=Path.cwd())
        self.addCleanup(work.cleanup)
        self.root = Path(work.name)
        self.root_patch = mock.patch.object(ci_checks, "ROOT", self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)
        self.environment = mock.patch.dict(os.environ, {}, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.args = argparse.Namespace(base=None, head=None, output_dir=None)
        self.temporary_directory = tempfile.TemporaryDirectory
        self.external_parent = self.root.parent / ".ci-checks-external-test"
        self.temp_parent_patch = mock.patch.object(
            ci_checks.tempfile, "gettempdir", return_value=str(self.external_parent),
        )
        self.temp_parent_patch.start()
        self.addCleanup(self.temp_parent_patch.stop)

    def private_scratch(self, *, prefix, dir):
        self.assertEqual(dir, self.external_parent)
        # Keep test execution isolated in this fixture; production uses external scratch.
        return self.temporary_directory(prefix=prefix, dir=self.root)

    def scanner_sources(self):
        self.write("tests/test_secret_scanner.py", "scanner regression fixture")
        self.write(".gitleaks.toml", "scanner config")

    def write(self, name, content=""):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def run_main(self, stage, *args):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return ci_checks.main(["--stage", stage, *args])

    def test_module_tools_use_current_python(self):
        with mock.patch.object(ci_checks.importlib.util, "find_spec", return_value=object()):
            self.assertEqual(ci_checks.tool_command("ruff", module=True),
                             [sys.executable, "-m", "ruff"])

    def test_binary_fallback_including_windows_executable(self):
        with (
            mock.patch.object(ci_checks.importlib.util, "find_spec", return_value=None),
            mock.patch.object(ci_checks.shutil, "which", return_value="C:/tools/shellcheck.exe"),
        ):
            self.assertEqual(ci_checks.tool_command("shellcheck"),
                             ["C:/tools/shellcheck.exe"])
            self.assertEqual(ci_checks.tool_command("ruff", module=True),
                             ["C:/tools/shellcheck.exe"])

    def test_missing_tools_fail_named_without_installation(self):
        for stage, name in [
            ("lint-python", "ruff"), ("lint-yaml", "yamllint"),
            ("lint-shell", "shellcheck"), ("secrets", "gitleaks"),
        ]:
            with (
                self.subTest(stage=stage),
                mock.patch.object(ci_checks.importlib.util, "find_spec", return_value=None),
                mock.patch.object(ci_checks.shutil, "which", return_value=None),
                mock.patch.object(ci_checks.subprocess, "run") as run,
                contextlib.redirect_stderr(io.StringIO()) as errors,
            ):
                self.assertEqual(ci_checks.main(["--stage", stage]), 1)
                self.assertIn(f"Missing required tool: {name}", errors.getvalue())
                run.assert_not_called()

    def test_commands_use_repo_cwd_without_shell(self):
        with mock.patch.object(ci_checks.subprocess, "run") as run:
            ci_checks.execute(["example", "path with spaces"])
        self.assertEqual(run.call_args.kwargs["cwd"], self.root)
        self.assertIs(run.call_args.kwargs["shell"], False)

    def test_git_failure_is_not_an_empty_success(self):
        with mock.patch.object(
            ci_checks.subprocess, "run",
            return_value=subprocess.CompletedProcess([], 128, stdout=b"", stderr=b"bad ref"),
        ):
            with self.assertRaisesRegex(ci_checks.CheckError, "git diff failed"):
                ci_checks.git("diff", "missing")

    def test_missing_executable_is_actionable(self):
        with mock.patch.object(
            ci_checks.subprocess, "run", side_effect=FileNotFoundError(2, "not found"),
        ):
            with self.assertRaisesRegex(ci_checks.CheckError, "Cannot run ruff"):
                ci_checks.execute(["ruff"])

    def test_local_scope_includes_staged_unstaged_untracked_and_rename(self):
        names = [
            "staged.py", "unstaged.py", "new file.py", "renamed.py",
            "line\nbreak.py", "unicode-aloha-ā.py",
        ]
        for name in names:
            self.write(name)
        self.write("legacy.py")
        status = (
            "M  staged.py\0 M unstaged.py\0?? new file.py\0"
            "R  renamed.py\0old.py\0?? line\nbreak.py\0?? unicode-aloha-ā.py\0"
            " D deleted.py\0"
        )
        with mock.patch.object(
            ci_checks, "git",
            side_effect=["refs/remotes/origin/main\n", "ok", "ok", "", status],
        ) as git:
            self.assertEqual(ci_checks.changed_python(), set(names))
        diff = git.call_args_list[3].args
        self.assertIn("refs/remotes/origin/main...HEAD", diff)
        self.assertNotIn("HEAD^", " ".join(diff))
        self.assertIn("--porcelain=v1", git.call_args_list[4].args)

    def test_clean_committed_python_remains_in_default_strict_scope(self):
        self.write("committed.py")
        with mock.patch.object(
            ci_checks, "git",
            side_effect=["refs/remotes/origin/main\n", "ok", "ok", "committed.py\0", ""],
        ) as git:
            self.assertEqual(ci_checks.changed_python(), {"committed.py"})
        self.assertIn("refs/remotes/origin/main...HEAD", git.call_args_list[3].args)

    def test_default_base_prefers_existing_origin_head(self):
        with mock.patch.object(
            ci_checks, "git",
            return_value="refs/remotes/origin/HEAD\nrefs/remotes/origin/main\n",
        ):
            self.assertEqual(ci_checks.default_base(), "refs/remotes/origin/HEAD")

    def test_missing_offline_default_base_fails_with_actionable_explicit_range(self):
        with mock.patch.object(ci_checks, "git", return_value="") as git:
            with self.assertRaisesRegex(ci_checks.CheckError, "specify --base and --head"):
                ci_checks.changed_python()
        git.assert_called_once()

    def test_default_base_command_failure_does_not_fall_back(self):
        with mock.patch.object(
            ci_checks, "git", side_effect=ci_checks.CheckError("git for-each-ref failed"),
        ):
            with self.assertRaisesRegex(ci_checks.CheckError, "for-each-ref failed"):
                ci_checks.changed_python()

    def test_ci_range_uses_only_explicit_commit_diff(self):
        self.write("changed.py")
        with (
            mock.patch.dict(os.environ, {"DIFF_BASE": "base", "DIFF_HEAD": "head"}),
            mock.patch.object(ci_checks, "git", side_effect=["ok", "ok", "changed.py\0"]) as git,
        ):
            self.assertEqual(ci_checks.changed_python(), {"changed.py"})
        self.assertIn("base...head", git.call_args_list[2].args)
        self.assertEqual(git.call_count, 3)

    def test_local_explicit_refs_still_include_working_changes(self):
        self.write("commit.py")
        self.write("working.py")
        with mock.patch.object(
            ci_checks, "git", side_effect=["ok", "ok", "commit.py\0", "?? working.py\0"],
        ) as git:
            self.assertEqual(ci_checks.changed_python("base", "head"), {"commit.py", "working.py"})
        self.assertIn("base...head", git.call_args_list[2].args)

    def test_initial_ci_push_uses_root_diff_not_workingtree(self):
        with (
            mock.patch.dict(os.environ, {"DIFF_BASE": "0" * 40, "DIFF_HEAD": "head"}),
            mock.patch.object(ci_checks, "git", side_effect=["ok", ""]) as git,
        ):
            self.assertEqual(ci_checks.changed_python(), set())
        self.assertIn("diff-tree", git.call_args_list[1].args)
        self.assertIn("--root", git.call_args_list[1].args)

    def test_incomplete_ci_environment_does_not_fall_back_to_local(self):
        for environment in [{"DIFF_BASE": "bad"}, {"DIFF_HEAD": ""}]:
            with (
                self.subTest(environment=environment),
                mock.patch.dict(os.environ, environment),
                mock.patch.object(ci_checks, "git") as git,
            ):
                with self.assertRaisesRegex(ci_checks.CheckError, "DIFF_HEAD is required"):
                    ci_checks.changed_python()
                git.assert_not_called()

    def test_invalid_base_and_head_fail_closed(self):
        for base, head in [("bad", "HEAD"), ("HEAD", "bad"), ("", "HEAD")]:
            with self.subTest(base=base, head=head):
                def git(*args):
                    if args[-1] in {"bad^{commit}", "^{commit}"}:
                        raise ci_checks.CheckError("git rev-parse failed")
                    return ""
                with mock.patch.object(ci_checks, "git", side_effect=git):
                    with self.assertRaises(ci_checks.CheckError):
                        ci_checks.changed_python(base, head)

    def test_python_scope_excludes_generated_protected_and_scratch(self):
        accepted = ["tools/new.py", "tests/new.pyi"]
        excluded = ["site/generated.py", "tmp/a.py", ".venv/a.py", "tests/.secret-scan-x/a.py"]
        for name in accepted + excluded:
            self.write(name)
        candidates = [*accepted, *excluded, ".github/agents/never.py", "../outside.py"]
        with mock.patch.object(
            ci_checks, "git", side_effect=[
                "refs/remotes/origin/main\n", "ok", "ok", "",
                "".join(f"?? {n}\0" for n in candidates),
            ],
        ):
            self.assertEqual(ci_checks.changed_python(), set(accepted))

    def test_protected_paths_are_rejected_without_stat(self):
        with mock.patch.object(Path, "is_symlink", side_effect=AssertionError("protected read")):
            self.assertFalse(ci_checks.permitted_path(".github/agents/never.py"))
            self.assertFalse(ci_checks.permitted_path(".git/config"))

    def test_baseline_preserves_exact_nine_diagnostics(self):
        self.assertEqual(sum(ci_checks.CORRECTNESS_BASELINE.values()), 9)
        findings = []
        for (path, code, message), count in ci_checks.CORRECTNESS_BASELINE.items():
            findings.extend([{
                "filename": str(self.root / path), "code": code,
                "message": message, "location": {"row": 1},
            }] * count)
        self.write("tracked.py")
        with (
            mock.patch.object(ci_checks, "tool_command", return_value=["ruff"]),
            mock.patch.object(ci_checks, "tracked", return_value=["tracked.py"]),
            mock.patch.object(ci_checks, "changed_python", return_value={"_fix_failing.py"}),
            mock.patch.object(ci_checks, "execute", side_effect=[
                subprocess.CompletedProcess([], 1, stdout=json.dumps(findings)),
                subprocess.CompletedProcess([], 0),
            ]) as run,
        ):
            self.assertEqual(self.run_main("lint-python"), 0)
        self.assertIn("_fix_failing.py", run.call_args_list[1].args[0])
        self.assertNotIn("--select", run.call_args_list[1].args[0])

    def test_duplicate_or_new_correctness_diagnostics_fail(self):
        for path, code, message, count in [
            ("services/studio_assets/app/main.py", "F821", "Undefined name `_sys`", 6),
            ("new.py", "F821", "Undefined name `bad`", 1),
        ]:
            findings = [{
                "filename": str(self.root / path), "code": code,
                "message": message, "location": {"row": 1},
            }] * count
            with (
                self.subTest(path=path),
                mock.patch.object(ci_checks, "tool_command", return_value=["ruff"]),
                mock.patch.object(ci_checks, "tracked", return_value=["tracked.py"]),
                mock.patch.object(ci_checks, "permitted_path", return_value=True),
                mock.patch.object(ci_checks, "changed_python", return_value=set()),
                mock.patch.object(ci_checks, "execute", side_effect=[
                    subprocess.CompletedProcess([], 1, stdout=json.dumps(findings)),
                    subprocess.CompletedProcess([], 0),
                ]),
            ):
                self.assertEqual(self.run_main("lint-python"), 1)

    def test_ruff_tool_error_and_strict_failure_fail(self):
        for results in [
            [subprocess.CompletedProcess([], 2)],
            [subprocess.CompletedProcess([], 0, stdout="[]"),
             subprocess.CompletedProcess([], 1)],
        ]:
            with (
                self.subTest(results=results),
                mock.patch.object(ci_checks, "tool_command", return_value=["ruff"]),
                mock.patch.object(ci_checks, "tracked", return_value=["tracked.py"]),
                mock.patch.object(ci_checks, "permitted_path", return_value=True),
                mock.patch.object(ci_checks, "changed_python", return_value=set()),
                mock.patch.object(ci_checks, "execute", side_effect=results),
            ):
                self.assertEqual(self.run_main("lint-python"), 1)

    def test_yaml_keeps_policy_and_includes_dependabot(self):
        files = [".github/workflows/ci.yml", ".github/dependabot.yml", "docker-compose.yml"]
        for name in files:
            self.write(name)
        with (
            mock.patch.object(ci_checks, "tool_command", return_value=["yamllint"]),
            mock.patch.object(ci_checks, "tracked", return_value=files) as tracked,
            mock.patch.object(
                ci_checks, "execute", return_value=subprocess.CompletedProcess([], 0),
            ) as run,
        ):
            self.assertEqual(self.run_main("lint-yaml"), 0)
        self.assertIn(".github/dependabot.yml", tracked.call_args.args)
        command = run.call_args.args[0]
        self.assertIn("--strict", command)
        self.assertIn("extends: relaxed", command[3])
        self.assertIn("deploy/studio-assets/docker-compose.studio-assets.yml", command[3])
        self.assertEqual(command[-3:], files)

    def test_shell_exception_only_applies_to_check_surfaces(self):
        files = ["scripts/maintained.sh", "scripts/check_surfaces.sh"]
        for name in files:
            self.write(name)
        with (
            mock.patch.object(ci_checks, "tool_command", return_value=["shellcheck"]),
            mock.patch.object(ci_checks, "tracked", return_value=files),
            mock.patch.object(
                ci_checks, "execute", return_value=subprocess.CompletedProcess([], 0),
            ) as run,
        ):
            self.assertEqual(self.run_main("lint-shell"), 0)
        self.assertEqual(run.call_args_list[0].args[0],
                         ["shellcheck", "--external-sources", files[0]])
        self.assertEqual(run.call_args_list[1].args[0],
                         ["shellcheck", "--external-sources", "--exclude=SC1091", files[1]])

    def test_empty_yaml_and_shell_scope_fail(self):
        for stage in ["lint-yaml", "lint-shell"]:
            with (
                self.subTest(stage=stage),
                mock.patch.object(ci_checks, "tool_command", return_value=["tool"]),
                mock.patch.object(ci_checks, "tracked", return_value=[]),
                mock.patch.object(ci_checks, "execute") as run,
            ):
                self.assertEqual(self.run_main(stage), 1)
                run.assert_not_called()

    def test_secret_version_mismatch_and_shallow_history_fail_before_tests(self):
        for version, shallow in [("8.0.0", "false"), ("8.24.3", "true")]:
            with (
                self.subTest(version=version, shallow=shallow),
                mock.patch.object(ci_checks, "tool_command", return_value=["gitleaks"]),
                mock.patch.object(ci_checks, "git", return_value=shallow),
                mock.patch.object(ci_checks, "execute", return_value=
                                  subprocess.CompletedProcess([], 0, stdout=version)) as run,
                contextlib.redirect_stderr(io.StringIO()) as errors,
            ):
                self.assertEqual(ci_checks.main(["--stage", "secrets"]), 1)
                run.assert_called_once()
                expected = "fetch manually" if shallow == "true" else "8.24.3 required"
                self.assertIn(expected, errors.getvalue())

    def test_scanner_regressions_cannot_skip_missing_or_failed_tool(self):
        self.scanner_sources()
        with (
            mock.patch.object(ci_checks, "tool_command", return_value=["gitleaks"]),
            mock.patch.object(ci_checks, "git", return_value="false"),
            mock.patch.object(ci_checks.tempfile, "TemporaryDirectory", side_effect=self.private_scratch),
            mock.patch.object(ci_checks, "execute", side_effect=[
                subprocess.CompletedProcess([], 0, stdout="8.24.3"),
                subprocess.CompletedProcess([], 1, stdout="sensitive"),
            ]) as run,
        ):
            self.assertEqual(self.run_main("secrets"), 1)
        command = run.call_args.args[0]
        self.assertIn("test_secret_scanner.py", command)
        self.assertEqual(run.call_args.kwargs["env"]["GITLEAKS"], "gitleaks")

    def test_current_secret_snapshot_includes_uncommitted_and_untracked_files(self):
        self.scanner_sources()
        files = ["tracked.txt", "untracked new.txt", "site/generated.txt"]
        for name in files:
            self.write(name, f"current {name}")
        self.write("tests/.secret-scan-history/tracked.txt", "tracked prefix stays scanned")
        files.append("tests/.secret-scan-history/tracked.txt")
        names = "\0".join([*files, "deleted.txt", ".github/agents/never.txt"]) + "\0"
        scans = []

        def execute(command, **kwargs):
            if command[-1] == "version":
                return subprocess.CompletedProcess(command, 0, stdout="8.24.3")
            if "unittest" in command:
                self.assertEqual(kwargs["env"]["GITLEAKS"], "gitleaks")
                work = kwargs["cwd"]
                self.assertEqual((work / ".gitleaks.toml").read_text(), "scanner config")
                self.assertEqual((work / "tests" / "test_secret_scanner.py").read_text(),
                                 "scanner regression fixture")
                return subprocess.CompletedProcess(command, 0)
            self.assertTrue(kwargs["capture"])
            self.assertIn("--redact", command)
            self.assertIn("--ignore-gitleaks-allow", command)
            ignore = Path(command[command.index("--gitleaks-ignore-path") + 1])
            self.assertFalse(ignore.exists())
            scans.append(command)
            if command[1] == "dir":
                tree = Path(command[2])
                self.assertEqual(sorted(p.relative_to(tree).as_posix()
                                        for p in tree.rglob("*") if p.is_file()), sorted(files))
                for name in files:
                    self.assertEqual((tree / name).read_text(), (self.root / name).read_text())
            return subprocess.CompletedProcess(command, 0)

        with (
            mock.patch.object(ci_checks, "tool_command", return_value=["gitleaks"]),
            mock.patch.object(ci_checks, "git", side_effect=["false", names]) as git,
            mock.patch.object(ci_checks, "execute", side_effect=execute),
            mock.patch.object(ci_checks.tempfile, "TemporaryDirectory", side_effect=self.private_scratch),
        ):
            self.assertEqual(self.run_main("secrets"), 0)
        self.assertEqual([command[1] for command in scans], ["dir", "git"])
        self.assertIn("--log-opts=--all --full-history", scans[1])
        self.assertIn("--others", git.call_args.args)
        self.assertIn("--exclude-standard", git.call_args.args)
        self.assertFalse(Path(scans[0][2]).exists())

    def test_both_secret_scans_run_and_never_echo_scanner_output(self):
        self.scanner_sources()
        with (
            mock.patch.object(ci_checks, "tool_command", return_value=["gitleaks"]),
            mock.patch.object(ci_checks, "git", side_effect=["false", ""]),
            mock.patch.object(ci_checks.tempfile, "TemporaryDirectory", side_effect=self.private_scratch),
            mock.patch.object(ci_checks, "execute", side_effect=[
                subprocess.CompletedProcess([], 0, stdout="8.24.3"),
                subprocess.CompletedProcess([], 0),
                subprocess.CompletedProcess([], 1, stdout="DO_NOT_PRINT", stderr="DO_NOT_PRINT"),
                subprocess.CompletedProcess([], 1, stdout="DO_NOT_PRINT", stderr="DO_NOT_PRINT"),
            ]) as run,
            contextlib.redirect_stdout(io.StringIO()) as stdout,
            contextlib.redirect_stderr(io.StringIO()) as stderr,
        ):
            self.assertEqual(ci_checks.main(["--stage", "secrets"]), 1)
        self.assertEqual(run.call_count, 4)
        self.assertNotIn("DO_NOT_PRINT", stdout.getvalue() + stderr.getvalue())
        self.assertEqual(sorted(path.name for path in self.root.iterdir()),
                         [".gitleaks.toml", "tests"])

    def test_secret_snapshot_does_not_follow_symlinks(self):
        target = self.write("target.txt", "private")
        try:
            (self.root / "link.txt").symlink_to(target)
            (self.root / "linked-dir").symlink_to(target.parent, target_is_directory=True)
        except OSError:
            self.skipTest("Symlinks require additional privileges on this platform")
        self.assertFalse(ci_checks.permitted_path("link.txt"))
        self.assertFalse(ci_checks.permitted_path("linked-dir/target.txt"))

    def test_output_directory_must_be_external_and_not_an_ancestor(self):
        for directory in [self.root, self.root.parent, self.root / ".git" / "scratch",
                          self.root / ".github" / "agents" / "scratch"]:
            with (
                self.subTest(directory=directory),
                mock.patch.object(ci_checks, "tool_command", return_value=["gitleaks"]),
                mock.patch.object(ci_checks, "git", return_value="false"),
                mock.patch.object(ci_checks, "execute", side_effect=[
                    subprocess.CompletedProcess([], 0, stdout="8.24.3"),
                    subprocess.CompletedProcess([], 0),
                ]),
            ):
                self.assertEqual(self.run_main("secrets", "--output-dir", str(directory)), 1)
        self.assertEqual(list(self.root.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
