"""Run the shared local/GitHub test gate without deploying or starting Docker."""

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--junitxml", type=Path, help="Optional persistent test report")
    parser.add_argument("--coverage-xml", type=Path, help="Optional persistent service coverage report")
    args = parser.parse_args(argv)
    if sys.version_info < (3, 11):
        parser.error("Python 3.11 or newer is required")
    command = [
        sys.executable, "-m", "pytest",
        "tests/v2", "tests/test_studio_assets_crosswalk.py", "tests/test_local_ci.py",
        "tests/test_local_validation.py",
        "tests/test_ci_checks.py",
        "--cov=services", "--cov-report=term",
    ]
    if args.junitxml:
        command.append(f"--junitxml={args.junitxml.resolve()}")
    if args.coverage_xml:
        command.append(f"--cov-report=xml:{args.coverage_xml.resolve()}")
    with tempfile.TemporaryDirectory(prefix="12sgi-ci-") as directory:
        env = {
            **os.environ,
            "PYTHONHASHSEED": "0",
            "PYTHONUTF8": "1",
            "NO_PROXY": "localhost,127.0.0.1",
            "COVERAGE_FILE": str(Path(directory) / ".coverage"),
        }
        return subprocess.run(command, cwd=ROOT, env=env, check=False).returncode


if __name__ == "__main__":
    sys.exit(main())
