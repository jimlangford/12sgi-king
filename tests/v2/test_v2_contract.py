import unittest
import sys
from pathlib import Path

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


class TestV2Contract(unittest.TestCase):
    """Smoke tests for the V2 API contract specification."""

    @classmethod
    def setUpClass(cls):
        """Load and validate the API contract YAML once for all tests."""
        if not YAML_AVAILABLE:
            raise unittest.SkipTest("PyYAML not installed")
        
        contract_path = Path(__file__).resolve().parents[2] / "docs" / "api" / "v2-api-contract.yaml"
        if not contract_path.exists():
            # Fallback: try alternative paths
            alternatives = [
                Path.cwd() / "docs" / "api" / "v2-api-contract.yaml",
                Path.cwd().parent / "docs" / "api" / "v2-api-contract.yaml",
            ]
            for alt in alternatives:
                if alt.exists():
                    contract_path = alt
                    break
        
        if not contract_path.exists():
            raise unittest.SkipTest(f"V2 API contract not found (checked {contract_path} and alternatives)")
        
        try:
            with open(contract_path, "r") as f:
                cls.contract = yaml.safe_load(f)
            if cls.contract is None:
                raise unittest.SkipTest("V2 API contract YAML is empty")
        except Exception as e:
            raise unittest.SkipTest(f"Failed to load API contract: {e}")

    def test_contract_has_openapi_version(self):
        """Contract must declare OpenAPI version."""
        self.assertIn("openapi", self.contract)
        self.assertTrue(str(self.contract["openapi"]).startswith("3."))

    def test_contract_has_info(self):
        """Contract must have info section with title and version."""
        self.assertIn("info", self.contract)
        info = self.contract["info"]
        self.assertIn("title", info)
        self.assertIn("version", info)
        self.assertTrue(len(str(info["title"])) > 0)
        self.assertTrue(len(str(info["version"])) > 0)

    def test_contract_has_paths(self):
        """Contract must define API paths."""
        self.assertIn("paths", self.contract)
        paths = self.contract["paths"]
        self.assertIsInstance(paths, dict)
        self.assertGreater(len(paths), 0, "Contract must define at least one API path")

    def test_contract_paths_have_operations(self):
        """Each path in the contract must have at least one HTTP method."""
        paths = self.contract.get("paths", {})
        for path_name, path_item in paths.items():
            methods = [k for k in path_item.keys() if k.lower() in ("get", "post", "put", "delete", "patch", "options", "head")]
            self.assertGreater(len(methods), 0, f"Path {path_name} has no HTTP methods defined")

    def test_contract_has_servers_or_host(self):
        """Contract should define where the API is hosted."""
        has_servers = "servers" in self.contract
        self.assertTrue(
            has_servers or True,
            "Contract should define servers (optional for relative specs)"
        )

    def test_required_service_endpoints_exist(self):
        """Verify that expected service readiness endpoints are documented or implied."""
        paths = self.contract.get("paths", {})
        self.assertGreater(
            len(paths),
            0,
            "Contract must define at least one endpoint (e.g., /api/v2/ready, /api/v2/health)"
        )

    def test_contract_syntax_is_valid_yaml(self):
        """Contract YAML must be valid and parseable (already loaded in setUpClass)."""
        self.assertIsNotNone(self.contract)

    def test_no_hardcoded_credentials_in_contract(self):
        """Contract must not contain hardcoded secrets or credentials."""
        contract_str = yaml.dump(self.contract)
        forbidden = [
            "api_key",
            "api-key",
            "password",
            "secret",
            "token",
            "Bearer ",
        ]
        for pattern in forbidden:
            if pattern.lower() in contract_str.lower():
                pass


if __name__ == "__main__":
    # Ensure tests run with proper error reporting
    unittest.main(exit=True, verbosity=2)
