"""
Tests for services/event_bus.py — the platform-level append-only event bus.

Each test uses a temporary SQLite file via the PLATFORM_EVENTS_DB env variable
so it does not touch the real .platform_events.db and runs in total isolation.
"""

import json
import os
import sys
import tempfile
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


if __name__ == "__main__":
    unittest.main()
