import unittest
from pathlib import Path

ROOT = Path('/home/runner/work/12sgi-king/12sgi-king')


class TestV2ContractFiles(unittest.TestCase):
    def test_openapi_contains_required_routes(self):
        text = (ROOT / 'docs/api/v2-openapi.yaml').read_text()
        required = [
            '/api/v2/auth/session',
            '/api/v2/cases',
            '/api/v2/documents/generate',
            '/api/v2/storage/objects',
            '/api/v2/ai/assist',
        ]
        for route in required:
            self.assertIn(route, text)

    def test_error_schema_exists(self):
        text = (ROOT / 'docs/api/v2-openapi.yaml').read_text()
        self.assertIn('ErrorResponse', text)
        self.assertIn('code', text)
        self.assertIn('message', text)

    def test_health_service_uses_v2_readiness_path(self):
        text = (ROOT / 'services/health/app/checks.py').read_text()
        self.assertIn("SURFACES_HEALTH_PATH", text)
        self.assertIn("/api/v2/ready", text)


if __name__ == '__main__':
    unittest.main()
