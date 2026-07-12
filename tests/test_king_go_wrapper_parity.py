import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GO_DIR = ROOT / "go"
KING_GO_DIR = ROOT / "king_public_src" / "go"


class TestKingGoWrapperParity(unittest.TestCase):
    def test_king_go_index_wrapper_exists(self):
        wrapper = KING_GO_DIR / "index.html"
        self.assertTrue(wrapper.exists(), "Missing /king/go/index.html wrapper.")
        text = wrapper.read_text(encoding="utf-8")
        self.assertIn("/king/go.html", text)

    def test_each_go_html_route_has_king_extensionless_wrapper(self):
        go_html_pages = sorted(
            p.stem for p in GO_DIR.glob("*.html") if p.stem != "index"
        )
        self.assertTrue(go_html_pages, "No /go/*.html routes found to validate.")
        for route in go_html_pages:
            wrapper = KING_GO_DIR / route / "index.html"
            self.assertTrue(
                wrapper.exists(),
                f"Missing /king/go/{route}/index.html wrapper for /go/{route}.html",
            )
            text = wrapper.read_text(encoding="utf-8")
            self.assertIn(
                f"/go/{route}.html",
                text,
                f"/king/go/{route}/index.html should redirect to /go/{route}.html",
            )


if __name__ == "__main__":
    unittest.main()
