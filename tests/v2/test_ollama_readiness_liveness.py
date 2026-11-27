"""Readiness asks Ollama "are you alive?", not "list every model".

/api/tags walks the model catalog and exceeded the 3 second readiness limit on a busy machine, so gpu-router and
king-bridge reported 503 while Ollama was fine. /api/version is a liveness answer. Model availability stays a
dispatch concern. The functions are run in isolation so the test needs no service dependencies.
"""
import ast
import io
import unittest
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CASES = (
    ("services/gpu_router/app/main.py", "request", {"GPU_RUNTIME_URL": "http://ollama:11434", "REQUEST_TIMEOUT": 3}),
    ("services/king_bridge/app/main.py", "urllib", {"OLLAMA_BASE": "http://ollama:11434"}),
)


class _Answer(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _run(path, module_name, settings, fail=False):
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    func = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_ollama_ready")
    asked = []

    def urlopen(url, timeout=None):
        asked.append((url, timeout))
        if fail:
            raise OSError("down")
        return _Answer(b"{}")

    fake_request = type("R", (), {"urlopen": staticmethod(urlopen)})
    fake = fake_request if module_name == "request" else type("U", (), {"request": fake_request})
    scope = dict(settings, **{module_name: fake})
    exec(compile(ast.Module(body=[func], type_ignores=[]), path, "exec"), scope)
    return scope["_ollama_ready"](), asked


class OllamaReadinessTest(unittest.TestCase):
    def test_readiness_uses_the_liveness_endpoint(self):
        for path, module_name, settings in CASES:
            with self.subTest(path=path):
                ok, asked = _run(path, module_name, settings)
                self.assertTrue(ok)
                self.assertEqual([u for u, _ in asked], ["http://ollama:11434/api/version"])
                self.assertEqual(asked[0][1], 3)

    def test_unreachable_ollama_is_still_not_ready(self):
        for path, module_name, settings in CASES:
            with self.subTest(path=path):
                ok, _ = _run(path, module_name, settings, fail=True)
                self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
