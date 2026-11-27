"""The delegated task is data, never a command-line option; the CLI is locked to read-only tools with customizations off."""
import importlib.util
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]


class TestClaudeBridge(unittest.TestCase):
    def test_flag_like_task_is_sent_on_stdin_not_argv(self):
        spec = importlib.util.spec_from_file_location("ccb", ROOT / "tools" / "claude_code_bridge.py")
        bridge = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bridge)
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        bridge.DATA, bridge.DB_PATH = Path(tmp.name), Path(tmp.name) / "jobs.sqlite3"
        task = '--settings={"hooks":{}} please review'
        seen = {}

        def fake_run(argv, **kw):
            seen["argv"], seen["input"] = argv, kw.get("input")
            return SimpleNamespace(returncode=0, stdout="ok", stderr="")

        bridge._slot.acquire()
        with mock.patch.object(bridge.shutil, "which", return_value="claude"), mock.patch.object(bridge.subprocess, "run", fake_run):
            bridge._run("job-1", task)
        self.assertEqual(seen["input"], task)
        self.assertFalse(any(task in str(a) or str(a).startswith("--settings") for a in seen["argv"]))
        for flag in ("--safe-mode", "--strict-mcp-config", "--tools"):
            self.assertIn(flag, seen["argv"])
        tmp.cleanup()

    def test_start_script_binds_loopback_only(self):
        text = (ROOT / "tools" / "start_claude_code_bridge.ps1").read_text(encoding="utf-8")
        self.assertIn("CLAUDE_CODE_BRIDGE_BIND = '127.0.0.1'", text)
        self.assertNotIn("0.0.0.0", text)


if __name__ == "__main__":
    unittest.main()
