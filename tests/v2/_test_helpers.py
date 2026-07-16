"""Shared test-loading helper for tests/v2/*.py.

Extracted 2026-07-16 (code-review follow-up on commit 4f35f13) after the same ~10-line
module-cache-clearing block was duplicated verbatim across three test files -- one of which
(test_v2_client_migration.py) had NO clearing logic at all, which is exactly how the
"sqlite3.OperationalError: unable to open database file" CI failure happened in the first
place: a future test file (or a newly-added auth submodule with the same module-level-
constant-from-env-var pattern) only needs updating in this one place now, not three.

Named with a leading underscore so pytest's default test-discovery pattern (test_*.py /
*_test.py) does not try to collect it as a test module.
"""
import importlib.util
import os
import sys

# Service submodules that any of the tested main.py files import via a plain
# `from services.X import Y` statement -- which Python serves from sys.modules on every
# call after the first, even though main.py itself gets a fresh exec_module() each time.
#
# CONFIRMED causes of the CI failure (traced via the actual traceback):
#   services.auth.app.passkeys, services.auth.app.magiclinks -- both compute DB_PATH as
#   a module-level `os.environ.get("AUTH_DB_PATH", ...)` constant at first import, so
#   every test after the first silently reused the FIRST test's (by-then-deleted) tempdir
#   instead of its own env override.
# Added defensively (same pattern -- a module-level constant read from an env var at
# import time -- but not individually proven to fail a test today):
#   services.authz (GOVOS_ALLOWED_WILDCARD_SCOPES), services.event_bus (PLATFORM_EVENTS_DB).
# Already present before this fix, kept for parity:
#   services.service_metadata.
CACHED_SERVICE_SUBMODULES = (
    "services.service_metadata",
    "services.authz",
    "services.event_bus",
    "services.auth.app.passkeys",
    "services.auth.app.magiclinks",
)


def load_module(path, name, env_overrides=None, env_clear_keys=None):
    """Load a service's main.py fresh under a controlled environment, so import-time
    guards (fail-closed secret checks, schema migrations, DB_PATH resolution) run exactly
    as they would on process boot. Restores the real environment afterward regardless of
    outcome. See CACHED_SERVICE_SUBMODULES above for why the module-cache clear matters."""
    saved = dict(os.environ)
    try:
        if env_clear_keys:
            for key in env_clear_keys:
                os.environ.pop(key, None)
        if env_overrides:
            os.environ.update(env_overrides)
        for mod in CACHED_SERVICE_SUBMODULES:
            sys.modules.pop(mod, None)
            attr = mod.rsplit(".", 1)[-1]
            parent = sys.modules.get(mod.rsplit(".", 1)[0]) if "." in mod else None
            if parent is not None and hasattr(parent, attr):
                delattr(parent, attr)
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        os.environ.clear()
        os.environ.update(saved)
