"""
Regression test: owner_jobs.html must never appear in the public site build.

owner_jobs.html is a private owner-administration surface (job tracking + approval UI)
served exclusively via king-bridge / Tailscale. Exposing it on the public GitHub Pages
artifact is a privacy violation even when the API fails closed, because the owner
administration interface structure itself should not be public.

This test runs a full site build and asserts the file is absent from the output.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PRIVATE_FILES = [
    "owner_jobs.html",  # owner job tracking + approval UI — private king-bridge route
]


class TestOwnerJobsNotPublic(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp_site = tempfile.mkdtemp(prefix="king-owner-jobs-check-")
        env = os.environ.copy()
        env["KA_SITE"] = cls._tmp_site
        result = subprocess.run(
            [sys.executable, "build_site.py"],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
        )
        cls._build_stdout = result.stdout
        cls._build_returncode = result.returncode

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls._tmp_site, ignore_errors=True)

    def test_build_succeeds(self):
        self.assertEqual(
            self._build_returncode, 0,
            "build_site.py exited non-zero:\n" + self._build_stdout,
        )

    def test_owner_jobs_not_in_public_site(self):
        """owner_jobs.html must not appear anywhere in the public site tree."""
        site = Path(self._tmp_site)
        hits = list(site.rglob("owner_jobs.html"))
        self.assertEqual(
            hits, [],
            "Privacy violation: owner_jobs.html found in public site build at: "
            + ", ".join(str(h) for h in hits),
        )

    def test_private_source_file_preserved(self):
        """The private source file must still exist in element_lotus_public/ (not deleted)."""
        private_src = ROOT / "element_lotus_public" / "owner_jobs.html"
        self.assertTrue(
            private_src.exists(),
            "element_lotus_public/owner_jobs.html source was unexpectedly removed.",
        )

    def test_no_owner_admin_files_in_site_root(self):
        """Spot-check: none of the known private admin files appear at the site root."""
        site = Path(self._tmp_site)
        for name in PRIVATE_FILES:
            path = site / name
            self.assertFalse(
                path.exists(),
                f"Private admin file '{name}' must not be published to the public site root.",
            )


if __name__ == "__main__":
    unittest.main()
