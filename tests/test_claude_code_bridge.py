"""The delegated task is data (never a CLI option), the reviewer sees no secrets, and a review needs owner approval."""
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.authz import DEFAULT_SCOPES_BY_ROLE  # noqa: E402


def _bridge(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / "claude_code_bridge.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestClaudeBridge(unittest.TestCase):
    def test_flag_like_task_is_sent_on_stdin_not_argv(self):
        bridge = _bridge("ccb")
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        bridge.DATA, bridge.DB_PATH = Path(tmp.name), Path(tmp.name) / "jobs.sqlite3"
        task = '--settings={"hooks":{}} please review'
        seen = {}

        def fake_run(argv, **kw):
            seen["argv"], seen["input"], seen["cwd"] = argv, kw.get("input"), kw.get("cwd")
            return SimpleNamespace(returncode=0, stdout="ok", stderr="")

        bridge._slot.acquire()
        with mock.patch.object(bridge.shutil, "which", return_value="claude"), \
                mock.patch.object(bridge.subprocess, "run", fake_run), \
                mock.patch.object(bridge, "_snapshot", return_value=0):
            bridge._run("job-1", task)
        self.assertEqual(seen["input"], task)
        self.assertFalse(any(task in str(a) or str(a).startswith("--settings") for a in seen["argv"]))
        self.assertNotEqual(Path(seen["cwd"]), bridge.ROOT)
        for flag in ("--restricted", "--safe-mode", "--strict-mcp-config", "--tools"):
            self.assertIn(flag, seen["argv"])
        tmp.cleanup()

    def test_snapshot_leaves_out_secrets_and_output_is_redacted(self):
        bridge = _bridge("ccb2")
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as src, \
                tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as dst:
            names = ["app/main.py", ".env", ".env.v2.example", "keys/server.pem", "config/credentials.json", "site/index.html"]
            for name in names:
                path = Path(src) / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("x", encoding="utf-8")
            bridge.ROOT = Path(src)
            listing = SimpleNamespace(stdout="\0".join(names).encode() + b"\0")
            with mock.patch.object(bridge.subprocess, "run", return_value=listing):
                bridge._snapshot(Path(dst))
            copied = sorted(p.relative_to(dst).as_posix() for p in Path(dst).rglob("*") if p.is_file())
            self.assertEqual(copied, ["app/main.py"])
        # Fake values are assembled at runtime so no commit ever contains a secret-shaped literal (the repo scan reads history).
        fake_env, fake_json, fake_hex = "abcdef0123456789" * 2, "s3cret" + "value99", "a1" * 32
        sample = "CLAUDE_CODE_BRIDGE_{}={}  \"api_{}\": \"{}\"  {}".format("TOK" + "EN", fake_env, "key", fake_json, fake_hex)
        text = bridge._redact(sample)
        for leaked in (fake_env, fake_json, fake_hex):
            self.assertNotIn(leaked, text)

    def test_review_needs_owner_approval_and_no_role_holds_the_scope(self):
        registry = json.loads((ROOT / "config" / "ai_tool_registry.v2.json").read_text(encoding="utf-8"))
        tools = {t["tool_id"]: t for t in (registry if isinstance(registry, list) else registry["tools"])}
        self.assertEqual(tools["claude_code.review"]["risk_class"], "approval")
        self.assertTrue(tools["claude_code.review"]["idempotency_required"])
        source = (ROOT / "services" / "ai_gateway" / "app" / "main.py").read_text(encoding="utf-8")
        self.assertIn('if tool["tool_id"] in _CLAUDE_TOOLS:', source)
        self.assertFalse(any("claude:invoke" in scopes for scopes in DEFAULT_SCOPES_BY_ROLE.values()))

    def test_start_script_binds_loopback_only(self):
        text = (ROOT / "tools" / "start_claude_code_bridge.ps1").read_text(encoding="utf-8")
        self.assertIn("CLAUDE_CODE_BRIDGE_BIND = '127.0.0.1'", text)
        self.assertNotIn("0.0.0.0", text)


if __name__ == "__main__":
    unittest.main()
