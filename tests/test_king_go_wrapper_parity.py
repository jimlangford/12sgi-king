import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GO_DIR = ROOT / "go"


class TestKingGoWrapperParity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp_site = tempfile.mkdtemp(prefix="king-go-wrapper-site-")
        env = os.environ.copy()
        env["KA_SITE"] = cls._tmp_site
        subprocess.run(
            [sys.executable, "build_site.py"],
            cwd=ROOT,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls._tmp_site, ignore_errors=True)

    def test_king_go_index_wrapper_exists(self):
        wrapper = Path(self._tmp_site) / "king" / "go" / "index.html"
        self.assertTrue(wrapper.exists(), "Missing built /king/go/index.html wrapper.")
        text = wrapper.read_text(encoding="utf-8")
        self.assertIn("/king/go.html", text)

    def test_each_go_html_route_has_extensionless_wrappers(self):
        go_html_pages = sorted(
            p.stem for p in GO_DIR.glob("*.html") if p.stem != "index"
        )
        self.assertTrue(go_html_pages, "No /go/*.html routes found to validate.")
        for route in go_html_pages:
            for root in ("go", "king/go"):
                wrapper = Path(self._tmp_site) / root / route / "index.html"
                self.assertTrue(
                    wrapper.exists(),
                    f"Missing built /{root}/{route}/index.html wrapper for /go/{route}.html",
                )
                text = wrapper.read_text(encoding="utf-8")
                self.assertIn(
                    f"/go/{route}.html",
                    text,
                    f"/{root}/{route}/index.html should redirect to /go/{route}.html",
                )


if __name__ == "__main__":
    unittest.main()
