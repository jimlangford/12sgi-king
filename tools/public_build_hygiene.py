"""Remove implementation/backup artifacts from PUBLIC output, never its sources."""

import os
from pathlib import Path

IMPLEMENTATION_SUFFIXES = {".py", ".pyc", ".pyo", ".bak"}
BUILD_MARKERS = {"sage/no-reopen"}


def is_build_artifact(relative):
    return (
        Path(relative).suffix.lower() in IMPLEMENTATION_SUFFIXES
        or Path(relative).as_posix() in BUILD_MARKERS
    )


def purge_build_artifacts(site):
    site = Path(site)
    removed = []
    for root, _, names in os.walk(site, followlinks=False):
        for name in names:
            path = Path(root) / name
            relative = path.relative_to(site).as_posix()
            if is_build_artifact(relative):
                path.unlink()
                removed.append(relative)
    return sorted(removed)
