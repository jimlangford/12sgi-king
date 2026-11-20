import unittest
from pathlib import Path

import yaml


class TestV2Contract(unittest.TestCase):
    """Smoke tests for the V2 API contract specification."""

    @classmethod
    def setUpClass(cls):
        """Load and validate the API contract YAML once for all tests."""
        contract_path = Path(__file__).resolve().parents[2] / "docs" / "api" / "v2-api-contract.yaml"
        with contract_path.open(encoding="utf-8") as handle:
            cls.contract = yaml.safe_load(handle)
        if not isinstance(cls.contract, dict):
            raise AssertionError("V2 API contract must be a non-empty mapping")

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

    def test_contract_has_servers(self):
        """Contract must declare at least one usable server URL."""
        servers = self.contract.get("servers", [])
        self.assertGreater(len(servers), 0)
        for server in servers:
            self.assertIsInstance(server.get("url"), str)
            self.assertTrue(server["url"].strip())

    def test_required_service_endpoints_exist(self):
        """Readiness and authentication endpoints must be explicitly documented."""
        paths = self.contract.get("paths", {})
        for path, method in (
            ("/api/v2/live", "get"),
            ("/api/v2/ready", "get"),
            ("/api/v2/health", "get"),
            ("/api/v2/auth/session", "post"),
        ):
            with self.subTest(path=path):
                self.assertIn(method, paths[path])
                self.assertIn("200", paths[path][method]["responses"])

    def test_contract_syntax_is_valid_yaml(self):
        """Contract YAML must be valid and parseable (already loaded in setUpClass)."""
        self.assertIsNotNone(self.contract)

    def test_session_requires_service_token(self):
        """Session creation must document the mandatory service-trust header."""
        operation = self.contract["paths"]["/api/v2/auth/session"]["post"]
        headers = {
            parameter["name"]: parameter
            for parameter in operation["parameters"]
            if parameter["in"] == "header"
        }
        self.assertIs(headers["X-Service-Token"]["required"], True)
        self.assertIn("403", operation["responses"])

    def test_local_references_resolve(self):
        """Broken schema references must fail CI rather than ship a partial contract."""
        def check(value):
            if isinstance(value, dict):
                if "$ref" in value:
                    reference = value["$ref"]
                    self.assertTrue(reference.startswith("#/"), reference)
                    target = self.contract
                    for part in reference[2:].split("/"):
                        target = target[part.replace("~1", "/").replace("~0", "~")]
                    self.assertIsInstance(target, dict)
                for child in value.values():
                    check(child)
            elif isinstance(value, list):
                for child in value:
                    check(child)

        check(self.contract)


if __name__ == "__main__":
    # Ensure tests run with proper error reporting
    unittest.main(exit=True, verbosity=2)
