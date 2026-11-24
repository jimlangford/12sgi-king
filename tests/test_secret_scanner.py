"""Exercise the actual pinned scanner, including removed history and narrow exceptions."""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(
    shutil.which(os.environ.get("GITLEAKS", "gitleaks")),
    "Optional Gitleaks binary is unavailable; secret-scan CI installs and verifies it",
)
class SecretScannerTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix=".secret-scan-", dir=ROOT / "tests")
        self.addCleanup(directory.cleanup)
        self.work = Path(directory.name)
        self.scanner = os.environ.get("GITLEAKS", "gitleaks")

    def scan(self, mode="dir"):
        return subprocess.run(
            [
                self.scanner, mode, str(self.work),
                "--config", str(ROOT / ".gitleaks.toml"),
                "--ignore-gitleaks-allow",
                "--gitleaks-ignore-path", str(self.work / "absent"),
                "--redact", "--no-banner", "--log-level", "error",
            ] + (["--log-opts=--all --full-history"] if mode == "git" else []),
            capture_output=True,
        ).returncode

    def write(self, name, content):
        path = self.work / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    def test_clean_and_exact_exception(self):
        self.write("game_sage/js/sage_ui.js",
                   "var VICTORY_ACK_KEY = '" + "sage_victory_ack_v1" + "';\n")
        self.assertEqual(self.scan(), 0)

    def test_exception_cannot_hide_other_paths_or_values(self):
        self.write("other.js", "var VICTORY_ACK_KEY = '" + "sage_victory_ack_v1" + "';\n")
        self.assertEqual(self.scan(), 1)
        (self.work / "other.js").unlink()
        self.write("game_sage/js/sage_ui.js",
                   "api_key = '" + "AKIA" + "Q7Z2X9V4N6M8C3B5" + "'\n")
        self.assertEqual(self.scan(), 1)

    def test_documentation_exceptions_are_exact_and_path_scoped(self):
        examples = [
            ("POINTS_3_5_QUICK_REFERENCE.md", "Authorization: Bearer " + "JETPACK_TOKEN"),
            ("SETUP_FINAL_INTEGRATION.md", "Authorization: Bearer " + "JETPACK_TOKEN"),
            ("GORDON_INTEGRATION_LOCAL_AI.md", "X-API-Key: " + "dev_key_12345"),
            ("TEST_AUTONOMOUS_REPAIRS.md", "X-Service-Token: " + "dev-internal-token"),
        ]
        for path, header in examples:
            with self.subTest(path=path):
                example = 'curl http://localhost:8504/test -H "' + header + '"\n'
                self.write(path, example)
                self.assertEqual(self.scan(), 0)
                (self.work / path).rename(self.work / "other.md")
                self.assertEqual(self.scan(), 1)
                (self.work / "other.md").unlink()
                self.write(path, 'curl http://localhost:8504/test -H "X-API-Key: '
                           + "random-live-looking-value-7Qp9" + '"\n')
                self.assertEqual(self.scan(), 1)
                (self.work / path).unlink()

    def test_configuration_identifier_exception_is_path_scoped(self):
        self.write("init-services.js", "key: '" + "NEO4J_CONV_TTL_DAYS" + "'\n")
        self.assertEqual(self.scan(), 0)
        (self.work / "init-services.js").rename(self.work / "other.js")
        self.assertEqual(self.scan(), 1)

    def test_removed_secret_still_fails_history(self):
        def git(*args):
            subprocess.run(
                ["git", "-C", str(self.work), *args],
                check=True, capture_output=True,
                env={**os.environ, "GIT_AUTHOR_NAME": "Scanner Test",
                     "GIT_AUTHOR_EMAIL": "scanner@example.invalid",
                     "GIT_COMMITTER_NAME": "Scanner Test",
                     "GIT_COMMITTER_EMAIL": "scanner@example.invalid"},
            )

        git("init", "--quiet")
        self.write("clean.txt", "No credentials here.\n")
        git("add", ".")
        git("-c", "commit.gpgsign=false", "commit", "--quiet", "-m", "clean fixture")
        self.assertEqual(self.scan("git"), 0)
        # Synthetic, nonfunctional value, constructed to avoid self-detection.
        self.write("removed.txt", "aws_access_key_id = " + "AKIA" + "Q7Z2X9V4N6M8C3B5\n")
        git("add", ".")
        git("-c", "commit.gpgsign=false", "commit", "--quiet", "-m", "synthetic fixture")
        git("rm", "--quiet", "removed.txt")
        git("-c", "commit.gpgsign=false", "commit", "--quiet", "-m", "remove fixture")
        self.assertEqual(self.scan(), 0)
        self.assertEqual(self.scan("git"), 1)
