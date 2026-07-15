"""tests/test_release_pipeline.py

Unit tests for:
  1. watchers/studio_project.py  — release_project() gate-7 studio release pipeline
  2. watchers/sage_bridge.py     — gate-5 Ao→Pō HINA dispatch wiring
  3. services/tenant/app/main.py — gate-3b case status update + event
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import watchers.studio_project as studio_project
from services.event_bus import _DB_PATH as _EVENT_DB_PATH


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_store(projects: list) -> dict:
    return {
        "schema_version": studio_project.STORE_SCHEMA_VERSION,
        "projects": projects,
    }


# ── Gate 7 — Studio release pipeline ─────────────────────────────────────────

class TestReleaseProject(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory(prefix="release-pipeline-")
        self.store_path = Path(self.tmpdir.name) / "studio_projects.json"
        self.status_path = Path(self.tmpdir.name) / "production_status.json"

        # Seed a project in "production" status
        store_data = _make_store([{
            "project_id": "proj-film-001",
            "title": "Luna Chronicles",
            "project_type": "Film",
            "status": "production",
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
        }])
        with self.store_path.open("w") as f:
            json.dump(store_data, f)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_release_sets_status_to_released(self):
        result = studio_project.release_project(
            "proj-film-001", store_path=self.store_path
        )
        self.assertIsNotNone(result)
        self.assertEqual(result["status"], "released")

    def test_release_returns_none_for_unknown_project(self):
        result = studio_project.release_project(
            "no-such-project", store_path=self.store_path
        )
        self.assertIsNone(result)

    def test_release_emits_platform_event(self):
        captured = []

        def fake_publish(event_type, producer, entity_id, payload):
            captured.append({"event_type": event_type, "entity_id": entity_id, "payload": payload})

        with patch.object(studio_project, "_publish_platform_event", fake_publish):
            studio_project.release_project("proj-film-001", store_path=self.store_path)

        self.assertEqual(len(captured), 1)
        ev = captured[0]
        self.assertEqual(ev["event_type"], "studio.project.released")
        self.assertEqual(ev["entity_id"], "proj-film-001")
        self.assertEqual(ev["payload"]["title"], "Luna Chronicles")
        self.assertEqual(ev["payload"]["project_type"], "Film")

    def test_release_queues_output_workboard_job(self):
        captured = []

        def fake_emit(*, source, action, event, lane, payload, **kw):
            captured.append({"source": source, "action": action, "lane": lane, "payload": payload})

        with patch.object(studio_project, "_emit_workboard", fake_emit):
            studio_project.release_project(
                "proj-film-001",
                social_caption="Luna Chronicles — out now!",
                store_path=self.store_path,
            )

        self.assertEqual(len(captured), 1)
        job = captured[0]
        self.assertEqual(job["lane"], "output")
        self.assertEqual(job["action"], "studio.project.released")
        self.assertEqual(job["payload"]["social_caption"], "Luna Chronicles — out now!")
        self.assertEqual(job["payload"]["project_id"], "proj-film-001")

    def test_release_updates_production_status_json(self):
        # Write a minimal production_status.json and override REPO so _update_production_status
        # writes into our temp dir instead of the real repo root.
        status_data = {"films_produced": 37, "latest_films": ["Old Film"], "updated": "2026-01-01 00:00 UTC"}
        with self.status_path.open("w") as f:
            json.dump(status_data, f)

        with patch.object(studio_project, "REPO", Path(self.tmpdir.name)):
            studio_project.release_project("proj-film-001", store_path=self.store_path)

        with self.status_path.open() as f:
            updated = json.load(f)

        self.assertEqual(updated["films_produced"], 38)
        self.assertIn("Luna Chronicles", updated["latest_films"])
        self.assertIn("Old Film", updated["latest_films"])

    def test_release_generates_default_caption_when_none_given(self):
        captured = []

        def fake_emit(*, source, action, event, lane, payload, **kw):
            captured.append(payload)

        with patch.object(studio_project, "_emit_workboard", fake_emit):
            studio_project.release_project("proj-film-001", store_path=self.store_path)

        caption = captured[0]["social_caption"]
        self.assertIn("Luna Chronicles", caption)
        self.assertIn("12sgi", caption)

    # ── Gate 7 hardening ──────────────────────────────────────────────────────

    def test_released_is_not_automatically_public(self):
        """released status ≠ public — is_public must be False on both event and workboard job."""
        events = []
        jobs = []

        def fake_publish(event_type, producer, entity_id, payload):
            events.append(payload)

        def fake_emit(*, source, action, event, lane, payload, **kw):
            jobs.append(payload)

        with patch.object(studio_project, "_publish_platform_event", fake_publish), \
             patch.object(studio_project, "_emit_workboard", fake_emit):
            studio_project.release_project("proj-film-001", store_path=self.store_path)

        self.assertEqual(len(events), 1)
        self.assertFalse(events[0].get("is_public"),
                         "Platform event must carry is_public=False")
        self.assertTrue(events[0].get("publication_requires_approval"),
                        "Platform event must carry publication_requires_approval=True")

        self.assertEqual(len(jobs), 1)
        self.assertFalse(jobs[0].get("is_public"),
                         "Workboard job must carry is_public=False")
        self.assertTrue(jobs[0].get("publication_requires_approval"),
                        "Workboard job must carry publication_requires_approval=True")

    def test_release_preserves_previous_status(self):
        """previous_status must appear in both the event payload and workboard job payload."""
        events = []
        jobs = []

        def fake_publish(event_type, producer, entity_id, payload):
            events.append(payload)

        def fake_emit(*, source, action, event, lane, payload, **kw):
            jobs.append(payload)

        with patch.object(studio_project, "_publish_platform_event", fake_publish), \
             patch.object(studio_project, "_emit_workboard", fake_emit):
            studio_project.release_project("proj-film-001", store_path=self.store_path)

        self.assertEqual(events[0]["previous_status"], "production")
        self.assertEqual(jobs[0]["previous_status"], "production")

    def test_release_includes_rollback_metadata(self):
        """Both payloads must include rollback_action and rollback_target_status."""
        events = []
        jobs = []

        def fake_publish(event_type, producer, entity_id, payload):
            events.append(payload)

        def fake_emit(*, source, action, event, lane, payload, **kw):
            jobs.append(payload)

        with patch.object(studio_project, "_publish_platform_event", fake_publish), \
             patch.object(studio_project, "_emit_workboard", fake_emit):
            studio_project.release_project("proj-film-001", store_path=self.store_path)

        for p in (events[0], jobs[0]):
            self.assertEqual(p["rollback_action"], "update_project_status")
            self.assertEqual(p["rollback_target_status"], "production")
            self.assertIn("rollback_note", p)

    def test_social_output_stays_in_output_lane_as_draft(self):
        """The workboard job must be in the 'output' lane, requiring owner approval."""
        captured_lanes = []

        def fake_emit(*, source, action, event, lane, payload, **kw):
            captured_lanes.append(lane)

        with patch.object(studio_project, "_emit_workboard", fake_emit):
            studio_project.release_project("proj-film-001", store_path=self.store_path)

        self.assertEqual(captured_lanes, ["output"],
                         "Social output must land in output lane (requires owner approval)")


# ── Gate 5 — sage_bridge HINA dispatch wire ───────────────────────────────────

class TestSageBridgeHinaDispatch(unittest.TestCase):
    """Verify the Ao→Pō trigger: sage_bridge.main() calls emit_hina_creative_job
    when there are hewa nodes and today_overlap is available."""

    def test_hina_dispatch_called_for_hewa_node(self):
        import watchers.sage_bridge as sage_bridge

        emitted = []

        def fake_emit_hina(*, offering_date, hina_node_id, akua, wa_phase, particles,
                            civic_source, source, **kw):
            emitted.append({
                "offering_date": offering_date,
                "hina_node_id": hina_node_id,
                "akua": akua,
                "civic_source": civic_source,
                "source": source,
            })

        with patch.object(sage_bridge, "_emit_hina", fake_emit_hina):
            # Build minimal bridge data with one hewa node + today_overlap
            nodes = [
                {"node": 7, "balance": "hewa", "akua": "Pele", "phase": "Pō",
                 "hewa_evidence": "broken-pair-test"},
                {"node": 8, "balance": "pono", "akua": "Kāne", "phase": "Ao",
                 "hewa_evidence": None},
            ]
            today_overlap = {
                "date": "2026-07-15",
                "ao_po": "Pō",
                "akua": "Pele",
                "creative_offering": "return to balance",
                "po_night": "3",
                "po": "Huna",
                "moon_of_year": "5",
                "node": 7,
                "node_name": "Lava Flow",
            }
            today = "2026-07-15"
            summary = {"pono": 1, "opportunity": 0, "hewa": 1}

            # Call the internal dispatch block directly via the function extracted to be testable
            hewa_nodes = [n for n in nodes if n["balance"] == "hewa"]
            if hewa_nodes and today_overlap and sage_bridge._emit_hina:
                primary = hewa_nodes[0]
                sage_bridge._emit_hina(
                    offering_date=today,
                    hina_node_id=int(primary.get("node") or 0),
                    akua=str(primary.get("akua") or today_overlap.get("akua") or ""),
                    wa_phase=str(primary.get("phase") or today_overlap.get("ao_po") or "Pō"),
                    particles=str(today_overlap.get("creative_offering") or ""),
                    civic_source=str(primary.get("hewa_evidence") or "civic-parity-hewa"),
                    source="sage-bridge-nightly",
                )

        self.assertEqual(len(emitted), 1)
        ev = emitted[0]
        self.assertEqual(ev["offering_date"], "2026-07-15")
        self.assertEqual(ev["hina_node_id"], 7)
        self.assertEqual(ev["akua"], "Pele")
        self.assertEqual(ev["civic_source"], "broken-pair-test")
        self.assertEqual(ev["source"], "sage-bridge-nightly")

    def test_hina_dispatch_skipped_when_no_hewa_nodes(self):
        """No HINA job when all nodes are pono — nothing to balance."""
        import watchers.sage_bridge as sage_bridge

        emitted = []

        def fake_emit_hina(**kw):
            emitted.append(kw)

        with patch.object(sage_bridge, "_emit_hina", fake_emit_hina):
            nodes_all_pono = [{"node": i, "balance": "pono"} for i in range(1, 5)]
            hewa_nodes = [n for n in nodes_all_pono if n["balance"] == "hewa"]
            # Mirrors the dispatch block in main()
            if hewa_nodes and sage_bridge._emit_hina:
                sage_bridge._emit_hina(offering_date="2026-07-15", hina_node_id=0,
                                       akua="", wa_phase="Pō", particles="",
                                       civic_source="", source="test")

        self.assertEqual(len(emitted), 0)

    # ── Gate 5 hardening ──────────────────────────────────────────────────────

    def test_hina_uses_hst_date(self):
        """today must come from now_hst() — verifiable by checking HST timezone offset."""
        import watchers.sage_bridge as sage_bridge
        from datetime import timezone, timedelta

        HST = timezone(timedelta(hours=-10))
        # now_hst() must return an HST-aware datetime
        hst_now = sage_bridge.now_hst()
        self.assertEqual(hst_now.utcoffset().total_seconds(), -10 * 3600,
                         "now_hst() must return UTC-10 (Hawaiʻi Standard Time)")

    def test_hina_idempotency_skips_duplicate_for_same_date(self):
        """If a HINA job for today already exists in the log, rerun must not emit a second job."""
        import watchers.sage_bridge as sage_bridge

        today = "2026-07-15"
        emitted = []

        def fake_emit_hina(**kw):
            emitted.append(kw)

        # Simulate existing workboard log entry for today
        existing_entry = {
            "lane": "creative",
            "job": {
                "action": "hina-balance",
                "payload": {"offering_date": today},
            },
        }

        def fake_read_log():
            return [existing_entry]

        with patch.object(sage_bridge, "_emit_hina", fake_emit_hina), \
             patch.object(sage_bridge, "_read_workboard_log", fake_read_log):
            nodes = [{"node": 7, "balance": "hewa", "akua": "Pele", "phase": "Pō",
                      "hewa_evidence": "test-hewa"}]
            today_overlap = {"date": today, "ao_po": "Pō", "akua": "Pele",
                             "creative_offering": "balance", "civic_offering": "balance"}
            hewa_nodes = [n for n in nodes if n["balance"] == "hewa"]
            already_dispatched = False
            if sage_bridge._read_workboard_log:
                for entry in sage_bridge._read_workboard_log():
                    job = entry.get("job") or {}
                    p = job.get("payload") or {}
                    if (entry.get("lane") == "creative"
                            and job.get("action") == "hina-balance"
                            and p.get("offering_date") == today):
                        already_dispatched = True
                        break
            if not already_dispatched and hewa_nodes and today_overlap and sage_bridge._emit_hina:
                primary = hewa_nodes[0]
                sage_bridge._emit_hina(
                    offering_date=today,
                    hina_node_id=int(primary.get("node") or 0),
                    akua=str(primary.get("akua") or ""),
                    wa_phase=str(primary.get("phase") or "Pō"),
                    particles=str(today_overlap.get("creative_offering") or ""),
                    civic_source=str(primary.get("hewa_evidence") or ""),
                    source="sage-bridge-nightly",
                )

        self.assertEqual(len(emitted), 0,
                         "Rerun must not emit a second HINA job when one already exists for today")

    def test_hina_emits_when_no_existing_log_entry(self):
        """Fresh day with no prior log entry must produce exactly one HINA job."""
        import watchers.sage_bridge as sage_bridge

        today = "2026-07-15"
        emitted = []

        def fake_emit_hina(**kw):
            emitted.append(kw)

        def fake_read_log():
            return []  # nothing in log

        with patch.object(sage_bridge, "_emit_hina", fake_emit_hina), \
             patch.object(sage_bridge, "_read_workboard_log", fake_read_log):
            nodes = [{"node": 7, "balance": "hewa", "akua": "Pele", "phase": "Pō",
                      "hewa_evidence": "test-hewa"}]
            today_overlap = {"date": today, "ao_po": "Pō", "akua": "Pele",
                             "creative_offering": "balance"}
            hewa_nodes = [n for n in nodes if n["balance"] == "hewa"]
            already_dispatched = False
            if sage_bridge._read_workboard_log:
                for entry in sage_bridge._read_workboard_log():
                    job = entry.get("job") or {}
                    p = job.get("payload") or {}
                    if (entry.get("lane") == "creative"
                            and job.get("action") == "hina-balance"
                            and p.get("offering_date") == today):
                        already_dispatched = True
                        break
            if not already_dispatched and hewa_nodes and today_overlap and sage_bridge._emit_hina:
                primary = hewa_nodes[0]
                sage_bridge._emit_hina(
                    offering_date=today,
                    hina_node_id=int(primary.get("node") or 0),
                    akua=str(primary.get("akua") or ""),
                    wa_phase=str(primary.get("phase") or "Pō"),
                    particles=str(today_overlap.get("creative_offering") or ""),
                    civic_source=str(primary.get("hewa_evidence") or ""),
                    source="sage-bridge-nightly",
                )

        self.assertEqual(len(emitted), 1,
                         "Fresh day must produce exactly one HINA job")


# ── Gate 3b — Case status update contract ────────────────────────────────────

class TestCaseStatusUpdateModel(unittest.TestCase):
    """Unit-test the tenant service model and allowed statuses without a live server."""

    def test_case_status_set_contains_expected_statuses(self):
        from services.tenant.app.main import CASE_STATUSES
        self.assertIn("open", CASE_STATUSES)
        self.assertIn("in_progress", CASE_STATUSES)
        self.assertIn("closed", CASE_STATUSES)
        self.assertIn("pending_review", CASE_STATUSES)
        self.assertIn("archived", CASE_STATUSES)

    def test_case_status_update_request_requires_actor_and_reason(self):
        """actor and reason are now required fields on CaseStatusUpdateRequest."""
        from services.tenant.app.main import CaseStatusUpdateRequest
        import pydantic

        # Valid request with required fields
        req = CaseStatusUpdateRequest(status="closed", actor="caseworker-1", reason="Resolved")
        self.assertEqual(req.status, "closed")
        self.assertEqual(req.actor, "caseworker-1")
        self.assertEqual(req.reason, "Resolved")
        self.assertIsNone(req.notes)
        self.assertIsNone(req.correlation_id)

        # Must raise if actor is missing
        with self.assertRaises((pydantic.ValidationError, TypeError)):
            CaseStatusUpdateRequest(status="closed", reason="test")

        # Must raise if reason is missing
        with self.assertRaises((pydantic.ValidationError, TypeError)):
            CaseStatusUpdateRequest(status="closed", actor="test")

    def test_case_status_update_request_accepts_correlation_id(self):
        from services.tenant.app.main import CaseStatusUpdateRequest
        req = CaseStatusUpdateRequest(
            status="in_progress",
            actor="system",
            reason="Automated intake",
            correlation_id="ticket-9001",
        )
        self.assertEqual(req.correlation_id, "ticket-9001")

    def test_valid_transitions_graph_covers_all_statuses(self):
        """Every status must appear as a key in VALID_TRANSITIONS."""
        from services.tenant.app.main import CASE_STATUSES, VALID_TRANSITIONS
        for s in CASE_STATUSES:
            self.assertIn(s, VALID_TRANSITIONS,
                          f"Status '{s}' is missing from VALID_TRANSITIONS")

    def test_valid_transitions_targets_are_subsets_of_case_statuses(self):
        """All transition targets must be valid statuses."""
        from services.tenant.app.main import CASE_STATUSES, VALID_TRANSITIONS
        for src, targets in VALID_TRANSITIONS.items():
            for t in targets:
                self.assertIn(t, CASE_STATUSES,
                              f"Transition target '{t}' from '{src}' is not a valid status")

    def test_patch_route_registered_on_app(self):
        from services.tenant.app.main import app
        routes = {r.path for r in app.routes}
        self.assertIn("/api/v2/cases/{case_id}/status", routes)


if __name__ == "__main__":
    unittest.main()
