"""PUBLIC links resolve both at domain root and a GitHub Pages project mount."""

import sys
from pathlib import Path
from urllib.parse import urljoin

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import fix_link_prefixes as links  # noqa: E402


def test_root_relative_public_links_are_mount_independent(tmp_path):
    (tmp_path / "nested").mkdir()
    (tmp_path / "assets").mkdir()
    (tmp_path / "maui.html").write_text("<main>Maui</main>")
    (tmp_path / "assets/a.css").write_text("body {}")
    (tmp_path / "nested/index.html").write_text(
        '<a href="/maui.html?record=1#test">Maui</a><link href="/assets/a.css">'
        '<a href="//external.example/path">External</a><a href="/api/jobs">API</a>'
        '<a href="/missing.html">Missing</a><a href="/">Home</a>'
    )
    links.fix_site(tmp_path)
    text = (tmp_path / "nested/index.html").read_text()
    assert 'href="../maui.html?record=1#test"' in text
    assert 'href="../assets/a.css"' in text
    assert 'href="//external.example/path"' in text
    assert 'href="/api/jobs"' in text
    assert 'href="/missing.html"' in text
    assert 'href="../"' in text
    for mount in ("/", "/12sgi-king/"):
        assert urljoin(
            "https://example.com" + mount + "nested/index.html", "../maui.html?record=1#test",
        ) == "https://example.com" + mount + "maui.html?record=1#test"
    assert links.fix_site(tmp_path) == (0, 0)


def test_root_conversion_retains_queries_and_ignores_traversal(tmp_path):
    (tmp_path / "target.html").write_text("public")
    text = '<a href="/target.html?x=1#id"></a><a href="/../outside.html"></a>'
    fixed, count = links._fix_root_relative(text, tmp_path, 0)
    assert count
    assert 'href="target.html?x=1#id"' in fixed
    assert 'href="/../outside.html"' in fixed
