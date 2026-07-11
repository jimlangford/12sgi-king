"""
Tests for services/event_bus.py — the platform-level append-only event bus.

Each test uses a temporary SQLite file via the PLATFORM_EVENTS_DB env variable
so it does not touch the real .platform_events.db and runs in total isolation.
"""

import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


class TestEventBus(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._db_path = Path(self._tmp.name) / "test_events.db"
        # Redirect event bus to temp DB before importing the module
        os.environ["PLATFORM_EVENTS_DB"] = str(self._db_path)
        # Force re-import so _DB_PATH picks up the env change
        import importlib
        import services.event_bus as eb_module
        importlib.reload(eb_module)
        self.eb = eb_module

    def tearDown(self):
        del os.environ["PLATFORM_EVENTS_DB"]
        self._tmp.cleanup()

    # ── publish_event ─────────────────────────────────────────────────────────

    def test_publish_returns_event_id(self):
        eid = self.eb.publish_event("test.event.fired", "test-producer", payload={"x": 1})
        self.assertIsNotNone(eid)
        self.assertIsInstance(eid, str)
        self.assertEqual(len(eid), 36)  # UUID length with dashes

    def test_published_event_is_retrievable(self):
        self.eb.publish_event("test.case.created", "test-service", payload={"case_id": "abc"}, entity_id="abc")
        events = self.eb.get_recent_events()
        self.assertEqual(len(events), 1)
        e = events[0]
        self.assertEqual(e["event_type"], "test.case.created")
        self.assertEqual(e["producer"], "test-service")
        self.assertEqual(e["entity_id"], "abc")
        self.assertEqual(e["payload"]["case_id"], "abc")

    def test_schema_version_present(self):
        self.eb.publish_event("test.schema.check", "svc")
        events = self.eb.get_recent_events()
        self.assertEqual(events[0]["schema_version"], "1.0")

    def test_publish_no_payload_defaults_empty_dict(self):
        self.eb.publish_event("test.no.payload", "svc")
        events = self.eb.get_recent_events()
        self.assertIsInstance(events[0]["payload"], dict)

    def test_idempotency_key_prevents_duplicate(self):
        self.eb.publish_event("test.idempotent", "svc", idempotency_key="key-1")
        result = self.eb.publish_event("test.idempotent", "svc", idempotency_key="key-1")
        self.assertIsNone(result)  # second call returns None
        events = self.eb.get_recent_events()
        self.assertEqual(len(events), 1)

    def test_different_producers_same_key_both_stored(self):
        self.eb.publish_event("test.event", "producer-a", idempotency_key="shared-key")
        self.eb.publish_event("test.event", "producer-b", idempotency_key="shared-key")
        events = self.eb.get_recent_events()
        self.assertEqual(len(events), 2)

    def test_publish_never_raises_on_bad_payload(self):
        # Non-serialisable value — should not raise
        result = self.eb.publish_event("test.bad", "svc", payload={"fn": object()})
        # Result is None (swallowed) but no exception
        self.assertIsNone(result)

    # ── get_recent_events ─────────────────────────────────────────────────────

    def test_filter_by_event_type(self):
        self.eb.publish_event("workboard.job.created", "v2_workboard")
        self.eb.publish_event("auth.login.success", "auth-service")
        events = self.eb.get_recent_events(event_type="workboard.job.created")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_type"], "workboard.job.created")

    def test_filter_by_producer(self):
        self.eb.publish_event("a.b.c", "svc-x")
        self.eb.publish_event("a.b.c", "svc-y")
        events = self.eb.get_recent_events(producer="svc-x")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["producer"], "svc-x")

    def test_limit_is_respected(self):
        for i in range(10):
            self.eb.publish_event("test.bulk", "svc", payload={"i": i})
        events = self.eb.get_recent_events(limit=3)
        self.assertEqual(len(events), 3)

    def test_events_returned_newest_first(self):
        self.eb.publish_event("test.order", "svc", payload={"seq": 1})
        self.eb.publish_event("test.order", "svc", payload={"seq": 2})
        events = self.eb.get_recent_events(event_type="test.order")
        self.assertGreaterEqual(events[0]["payload"]["seq"], events[1]["payload"]["seq"])

    def test_get_returns_empty_list_when_no_events(self):
        events = self.eb.get_recent_events()
        self.assertEqual(events, [])

    # ── dead-letter ───────────────────────────────────────────────────────────

    def test_oversized_payload_goes_to_dead_letter(self):
        big_payload = {"data": "x" * (self.eb.MAX_PAYLOAD_BYTES + 1)}
        result = self.eb.publish_event("test.oversized", "svc", payload=big_payload)
        self.assertIsNone(result)
        # Not in regular events
        events = self.eb.get_recent_events()
        self.assertEqual(len(events), 0)
        # Is in dead letters
        dead = self.eb.get_dead_letters()
        self.assertEqual(len(dead), 1)
        self.assertEqual(dead[0]["event_type"], "test.oversized")
        self.assertEqual(dead[0]["reason"], "payload_too_large")

    def test_get_dead_letters_empty_initially(self):
        dead = self.eb.get_dead_letters()
        self.assertEqual(dead, [])

    # ── correlation_id passthrough ────────────────────────────────────────────

    def test_correlation_id_stored_and_returned(self):
        self.eb.publish_event(
            "test.corr", "svc",
            correlation_id="req-abc-123",
        )
        events = self.eb.get_recent_events()
        self.assertEqual(events[0]["correlation_id"], "req-abc-123")


class TestWorkboardEventEmission(unittest.TestCase):
    """Verify that v2_workboard emits platform events at key transitions."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._db_path = Path(self._tmp.name) / "wb_events.db"
        self._log_path = Path(self._tmp.name) / "dispatch.jsonl"
        os.environ["PLATFORM_EVENTS_DB"] = str(self._db_path)

        import importlib
        import services.event_bus as eb_module
        importlib.reload(eb_module)
        self.eb = eb_module

        import services.v2_workboard as wb_module
        importlib.reload(wb_module)
        self.wb = wb_module

    def tearDown(self):
        del os.environ["PLATFORM_EVENTS_DB"]
        self._tmp.cleanup()

    def test_emit_workboard_job_fires_created_event(self):
        self.wb.emit_workboard_job(
            source="test",
            action="test-action",
            event="test-event",
            lane="engineering",
            log_path=self._log_path,
        )
        events = self.eb.get_recent_events(event_type="workboard.job.created")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["producer"], "v2_workboard")

    def test_approve_workboard_job_fires_approved_event(self):
        entry = self.wb.emit_workboard_job(
            source="test",
            action="approve-me",
            event="evt",
            lane="creative",
            status="pending-approval",
            log_path=self._log_path,
        )
        self.wb.approve_workboard_job(
            entry["job"]["id"],
            approver="owner",
            log_path=self._log_path,
        )
        events = self.eb.get_recent_events(event_type="workboard.job.approved")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["entity_id"], entry["job"]["id"])

    def test_reject_workboard_job_fires_rejected_event(self):
        entry = self.wb.emit_workboard_job(
            source="test",
            action="reject-me",
            event="evt",
            lane="creative",
            log_path=self._log_path,
        )
        self.wb.reject_workboard_job(
            entry["job"]["id"],
            reason="not ready",
            log_path=self._log_path,
        )
        events = self.eb.get_recent_events(event_type="workboard.job.rejected")
        self.assertEqual(len(events), 1)

    def test_selfheal_fires_selfhealed_event_only_when_jobs_healed(self):
        # No jobs → no event
        self.wb.selfheal_engineering_jobs(log_path=self._log_path)
        events = self.eb.get_recent_events(event_type="workboard.engineering.selfhealed")
        self.assertEqual(len(events), 0)

        # Add an engineering job → selfheal should fire event
        self.wb.emit_workboard_job(
            source="test", action="eng-task", event="e",
            lane="engineering", log_path=self._log_path,
        )
        self.wb.selfheal_engineering_jobs(log_path=self._log_path)
        events = self.eb.get_recent_events(event_type="workboard.engineering.selfhealed")
        self.assertEqual(len(events), 1)
        self.assertGreater(events[0]["payload"]["healed_count"], 0)


class TestAuthTenantEventEmission(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._db_path = Path(self._tmp.name) / "platform_events.db"
        self._auth_db = Path(self._tmp.name) / "auth.db"
        self._tenant_db = Path(self._tmp.name) / "tenant.db"
        os.environ["PLATFORM_EVENTS_DB"] = str(self._db_path)
        os.environ["GOVOS_ALLOW_DEV_SECRETS"] = "1"
        os.environ["AUTH_DB_PATH"] = str(self._auth_db)
        os.environ["TENANT_DB_PATH"] = str(self._tenant_db)
        self._install_service_stubs()

        import importlib
        import services.event_bus as eb_module
        importlib.reload(eb_module)
        self.eb = eb_module

        import services.auth.app.main as auth_module
        importlib.reload(auth_module)
        self.auth = auth_module

        import services.tenant.app.main as tenant_module
        importlib.reload(tenant_module)
        self.tenant = tenant_module

    def tearDown(self):
        del os.environ["PLATFORM_EVENTS_DB"]
        del os.environ["GOVOS_ALLOW_DEV_SECRETS"]
        del os.environ["AUTH_DB_PATH"]
        del os.environ["TENANT_DB_PATH"]
        for name in [
            "fastapi",
            "fastapi.middleware",
            "fastapi.middleware.cors",
            "fastapi.responses",
            "pydantic",
        ]:
            sys.modules.pop(name, None)
        self._tmp.cleanup()

    def _install_service_stubs(self):
        if "fastapi" not in sys.modules:
            fastapi = types.ModuleType("fastapi")

            class HTTPException(Exception):
                def __init__(self, status_code=500, detail=None):
                    self.status_code = status_code
                    self.detail = detail

            class FastAPI:
                def __init__(self, *args, **kwargs):
                    pass

                def add_middleware(self, *args, **kwargs):
                    return None

                def _route(self, *args, **kwargs):
                    def dec(fn):
                        return fn
                    return dec

                get = post = patch = _route

            def Header(default=None, alias=None):
                return default

            class Response:
                def __init__(self):
                    self.status_code = 200

            fastapi.FastAPI = FastAPI
            fastapi.Header = Header
            fastapi.HTTPException = HTTPException
            fastapi.Response = Response
            sys.modules["fastapi"] = fastapi

            middleware = types.ModuleType("fastapi.middleware")
            cors = types.ModuleType("fastapi.middleware.cors")
            cors.CORSMiddleware = object
            responses = types.ModuleType("fastapi.responses")
            responses.HTMLResponse = object
            responses.RedirectResponse = object
            sys.modules["fastapi.middleware"] = middleware
            sys.modules["fastapi.middleware.cors"] = cors
            sys.modules["fastapi.responses"] = responses

        if "pydantic" not in sys.modules:
            pydantic = types.ModuleType("pydantic")

            class BaseModel:
                def __init__(self, **kwargs):
                    for key, value in kwargs.items():
                        setattr(self, key, value)

            pydantic.BaseModel = BaseModel
            sys.modules["pydantic"] = pydantic

    def test_auth_session_creation_emits_event(self):
        req = self.auth.AuthSessionRequest(
            provider="magic_link",
            subject="resident:abc",
            tenant_id="tenant-a",
            role="Resident",
            scopes=["tenant:read"],
        )
        self.auth.create_session(req)
        events = self.eb.get_recent_events(event_type="auth.session.created", producer="auth")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["payload"]["provider"], "magic_link")
        self.assertEqual(events[0]["payload"]["role"], "Resident")

    def test_tenant_case_create_and_status_change_emit_events(self):
        self.tenant.require_claims = lambda **kwargs: {
            "sub": "user-1",
            "tenant_id": "tenant-a",
            "role": "Resident",
            "scopes": ["tenant:write", "tenant:read"],
        }
        self.tenant.enforce_tenant_scope = lambda **kwargs: kwargs.get("requested_tenant_id") or "tenant-a"
        self.tenant.enforce_resource_tenant = lambda **kwargs: None

        created = self.tenant.create_case(
            self.tenant.CaseCreateRequest(tenant_id="tenant-a", title="Case A", status="open"),
            authorization="******",
        )
        updated = self.tenant.update_case_status(
            created["id"],
            self.tenant.CaseStatusUpdateRequest(status="closed", notes="resolved"),
            authorization="******",
        )

        self.assertEqual(updated["status"], "closed")
        created_events = self.eb.get_recent_events(event_type="case.created", producer="tenant")
        changed_events = self.eb.get_recent_events(event_type="case.status.changed", producer="tenant")
        self.assertEqual(len(created_events), 1)
        self.assertEqual(len(changed_events), 1)
        self.assertEqual(changed_events[0]["payload"]["previous_status"], "open")
        self.assertEqual(changed_events[0]["payload"]["status"], "closed")


if __name__ == "__main__":
    unittest.main()
