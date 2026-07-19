import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "deploy-v2-king-server.yml"


class PrivateDeployWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def test_deploy_uses_canonical_private_environment(self):
        self.assertIn("V2_ENV_FILE:", self.text)
        self.assertIn("Validate private compose environment", self.text)
        self.assertIn('GOVOS_ALLOW_DEV_SECRETS must be 0', self.text)
        self.assertGreaterEqual(
            self.text.count('docker compose --env-file "$env:V2_ENV_FILE"'),
            3,
        )

    def test_deploy_waits_for_dependency_readiness(self):
        self.assertIn("Wait for V2 services to become ready", self.text)
        self.assertIn("AddSeconds(120)", self.text)
        self.assertIn("All V2 readiness endpoints returned HTTP 200", self.text)


if __name__ == "__main__":
    unittest.main()
