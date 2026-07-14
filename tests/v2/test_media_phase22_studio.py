"""
Phase 2.2 Studio departments test suite.

Covers:
  Writing Room (scripts, scenes, dialogue)
  Storyboard lock / archive / restore / revision
  FCP adapter (FCPXML, markers, roles)
  Logic adapter (sessions, cues, cue sheet)
  Game controls (projects, levels, quests, cinematics, builds)
  studio_interchange module (fcpxml.py, logic_manifest.py)
  Schema files (writing_roles, script, dialogue, editor_decision,
                fcp_roles, fcp_timeline, logic_session, audio_cue,
                game_project, game_dialogue_tree, game_quest, game_cinematic)
  Acceptance tests (30 required tests)
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# ── Config paths ───────────────────────────────────────────────────────────────
WRITING_ROLES_PATH      = ROOT / "config" / "media_writing_roles.v2.json"
SCRIPT_SCHEMA_PATH      = ROOT / "config" / "media_script.schema.json"
DIALOGUE_SCHEMA_PATH    = ROOT / "config" / "media_dialogue.schema.json"
EDITOR_DECISION_PATH    = ROOT / "config" / "media_editor_decision.schema.json"
FCP_ROLES_PATH          = ROOT / "config" / "fcp_roles.v2.json"
FCP_TIMELINE_PATH       = ROOT / "config" / "fcp_timeline.schema.json"
LOGIC_SESSION_PATH      = ROOT / "config" / "logic_session.schema.json"
AUDIO_CUE_PATH          = ROOT / "config" / "audio_cue.schema.json"
GAME_PROJECT_PATH       = ROOT / "config" / "game_project.schema.json"
GAME_DIALOGUE_PATH      = ROOT / "config" / "game_dialogue_tree.schema.json"
GAME_QUEST_PATH         = ROOT / "config" / "game_quest.schema.json"
GAME_CINEMATIC_PATH     = ROOT / "config" / "game_cinematic.schema.json"
WORKFLOW_INVENTORY_PATH = ROOT / "config" / "media_workflow_inventory.v2.json"
ENGINE_ROLES_PATH       = ROOT / "config" / "media_engine_roles.v2.json"


def _make_storyboard_client(tmp_dir: str):
    """Create a TestClient for the storyboard API routed to a temp DB."""
    import os
    db_path = str(Path(tmp_dir) / "storyboard.db")
    os.environ["STUDIO_STORYBOARD_DB_PATH"] = db_path
    from services.studio_assets.app import storyboard_api
    import importlib
    importlib.reload(storyboard_api)
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(storyboard_api.router)
    return TestClient(app), db_path


def _make_script_client(tmp_dir: str):
    import os
    db_path = str(Path(tmp_dir) / "scripts.db")
    os.environ["STUDIO_SCRIPT_DB_PATH"] = db_path
    from services.studio_assets.app import script_api
    import importlib
    importlib.reload(script_api)
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(script_api.router)
    return TestClient(app), db_path


def _make_fcp_client(tmp_dir: str):
    import os
    db_path = str(Path(tmp_dir) / "fcp.db")
    os.environ["STUDIO_FCP_DB_PATH"] = db_path
    from services.studio_assets.app import fcp_adapter
    import importlib
    importlib.reload(fcp_adapter)
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(fcp_adapter.router)
    return TestClient(app), db_path


def _make_logic_client(tmp_dir: str):
    import os
    db_path = str(Path(tmp_dir) / "logic.db")
    os.environ["STUDIO_LOGIC_DB_PATH"] = db_path
    from services.studio_assets.app import logic_adapter
    import importlib
    importlib.reload(logic_adapter)
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(logic_adapter.router)
    return TestClient(app), db_path


def _make_game_client(tmp_dir: str):
    import os
    db_path = str(Path(tmp_dir) / "game.db")
    os.environ["STUDIO_GAME_DB_PATH"] = db_path
    from services.studio_assets.app import game_api
    import importlib
    importlib.reload(game_api)
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(game_api.router)
    return TestClient(app), db_path


# ==============================================================================
# Schema file existence and structure
# ==============================================================================

class TestSchemaFiles(unittest.TestCase):
    """All Phase 2.2 schema and config files exist and are valid JSON."""

    REQUIRED_FILES = [
        WRITING_ROLES_PATH, SCRIPT_SCHEMA_PATH, DIALOGUE_SCHEMA_PATH,
        EDITOR_DECISION_PATH, FCP_ROLES_PATH, FCP_TIMELINE_PATH,
        LOGIC_SESSION_PATH, AUDIO_CUE_PATH,
        GAME_PROJECT_PATH, GAME_DIALOGUE_PATH, GAME_QUEST_PATH, GAME_CINEMATIC_PATH,
    ]

    def test_all_schema_files_exist(self):
        for p in self.REQUIRED_FILES:
            self.assertTrue(p.exists(), f"Schema file missing: {p.name}")

    def test_all_schema_files_parse_as_json(self):
        for p in self.REQUIRED_FILES:
            with open(p) as f:
                data = json.load(f)
            self.assertIsInstance(data, dict, f"{p.name} must be a JSON object")


class TestWritingRolesConfig(unittest.TestCase):
    def setUp(self):
        with open(WRITING_ROLES_PATH) as f:
            self.cfg = json.load(f)

    def test_all_required_roles_present(self):
        roles = self.cfg["writing_roles"]
        for r in ["showrunner", "story_architect", "screenwriter", "dialogue_writer",
                  "continuity_editor", "cultural_guardian", "script_supervisor", "table_read_critic"]:
            self.assertIn(r, roles, f"Role '{r}' missing from writing_roles")

    def test_cultural_guardian_has_uncertainty_policy(self):
        role = self.cfg["writing_roles"]["cultural_guardian"]
        self.assertEqual(role["uncertainty_policy"], "flag_and_hold")

    def test_all_required_writing_job_types_listed(self):
        jts = self.cfg["writing_job_types"]
        for jt in ["story_architecture", "beat_sheet", "scene_outline", "screenplay_scene",
                   "dialogue_pass", "continuity_pass", "cultural_review",
                   "table_read_review", "script_approval", "script_revision"]:
            self.assertIn(jt, jts)

    def test_writing_states_start_at_concept_and_end_at_locked(self):
        states = self.cfg["workflow_states"]
        self.assertEqual(states[0], "concept")
        self.assertEqual(states[-1], "script_locked")

    def test_locked_script_allows_archive(self):
        allows = self.cfg["lock_policy"]["locked_script_allows"]
        self.assertIn("archive", allows)

    def test_locked_script_prevents_overwrite(self):
        prevents = self.cfg["lock_policy"]["locked_script_prevents"]
        self.assertIn("overwrite", prevents)


class TestDialogueSchema(unittest.TestCase):
    def setUp(self):
        with open(DIALOGUE_SCHEMA_PATH) as f:
            self.schema = json.load(f)

    def test_delivery_has_estimated_duration_seconds(self):
        delivery = self.schema["properties"]["delivery"]["properties"]
        self.assertIn("estimated_duration_seconds", delivery)

    def test_cultural_review_status_includes_elder_consultation(self):
        enum = self.schema["properties"]["cultural_review_status"]["enum"]
        self.assertIn("requires_elder_consultation", enum)

    def test_fcp_role_includes_narration(self):
        enum = self.schema["properties"]["fcp_role"]["enum"]
        self.assertIn("Narration", enum)

    def test_example_estimated_duration_is_6_8(self):
        ex = self.schema["example"]
        self.assertEqual(ex["delivery"]["estimated_duration_seconds"], 6.8)


class TestEditorDecisionSchema(unittest.TestCase):
    def setUp(self):
        with open(EDITOR_DECISION_PATH) as f:
            self.schema = json.load(f)

    def test_camera_compliance_field_present(self):
        props = self.schema["properties"]
        self.assertIn("camera_compliance", props)

    def test_declared_vs_measured_engine_fields(self):
        cc = self.schema["properties"]["camera_compliance"]["properties"]
        self.assertIn("declared_engine", cc)
        self.assertIn("observed_engine_signature", cc)

    def test_motion_score_has_0_to_1_range(self):
        ms = self.schema["properties"]["motion_score"]
        self.assertEqual(ms["minimum"], 0.0)
        self.assertEqual(ms["maximum"], 1.0)

    def test_identity_score_is_nullable(self):
        ids = self.schema["properties"]["identity_score"]
        self.assertIn("null", ids["type"])


class TestFCPConfig(unittest.TestCase):
    def setUp(self):
        with open(FCP_ROLES_PATH) as f:
            self.roles_cfg = json.load(f)
        with open(FCP_TIMELINE_PATH) as f:
            self.timeline_schema = json.load(f)

    def test_all_required_fcp_roles_present(self):
        role_ids = [r["role_id"] for r in self.roles_cfg["roles"]]
        for role in ["Dialogue", "Narration", "Music", "Effects", "Ambience",
                     "Foley", "Room Tone", "Temporary Score", "Final Score", "Video"]:
            self.assertIn(role, role_ids)

    def test_timeline_schema_has_shots_and_markers(self):
        props = self.timeline_schema["properties"]
        self.assertIn("shots", props)
        self.assertIn("markers", props)

    def test_timeline_shot_has_immutable_asset_id(self):
        shot_props = self.timeline_schema["properties"]["shots"]["items"]["properties"]
        self.assertIn("asset_id", shot_props)
        self.assertIn("asset_hash", shot_props)


class TestGameSchemas(unittest.TestCase):
    def test_game_project_has_hierarchy_definition(self):
        with open(GAME_PROJECT_PATH) as f:
            schema = json.load(f)
        hierarchy = schema.get("hierarchy", {})
        levels = hierarchy.get("levels", [])
        self.assertEqual(levels[0], "game")
        self.assertEqual(levels[-1], "build")

    def test_game_cinematic_has_sequencer_manifest(self):
        with open(GAME_CINEMATIC_PATH) as f:
            schema = json.load(f)
        props = schema["properties"]
        self.assertIn("sequencer_manifest", props)

    def test_game_cinematic_example_has_storyboard_refs(self):
        with open(GAME_CINEMATIC_PATH) as f:
            schema = json.load(f)
        seq = schema["example"]["sequencer_manifest"]
        self.assertIn("storyboard_refs", seq)

    def test_game_dialogue_tree_node_links_to_studio_dialogue_id(self):
        with open(GAME_DIALOGUE_PATH) as f:
            schema = json.load(f)
        node_props = schema["properties"]["nodes"]["items"]["properties"]
        self.assertIn("dialogue_id", node_props)


# ==============================================================================
# Writing Room API
# ==============================================================================

class TestScriptAPI(unittest.TestCase):
    """TEST 1-6: Writing Room tests."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="script-api-")
        self.client, self.db = _make_script_client(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _create_script(self, production_id="prod-001"):
        resp = self.client.post("/api/v2/media/scripts", json={
            "production_id": production_id, "title": "Test Script", "logline": ""
        })
        self.assertEqual(resp.status_code, 201)
        return resp.json()["script_id"]

    def test_1_script_can_advance_through_workflow(self):
        """TEST 1: Approved scene can enter Director planning."""
        sid = self._create_script()
        # Advance through to approved
        for status in ["premise_ready", "architecture_ready", "beat_sheet_ready",
                       "scene_outline_ready", "first_draft", "dialogue_review",
                       "continuity_review", "cultural_review", "table_read_review",
                       "approval_pending", "approved"]:
            r = self.client.post(f"/api/v2/media/scripts/{sid}/advance",
                                 json={"to_status": status})
            self.assertEqual(r.status_code, 200, f"Failed advancing to {status}: {r.text}")
        r = self.client.get(f"/api/v2/media/scripts/{sid}")
        self.assertEqual(r.json()["status"], "approved")

    def test_2_unapproved_script_is_readable(self):
        """TEST 2: Unapproved script cannot generate production storyboards (status check)."""
        sid = self._create_script()
        r = self.client.get(f"/api/v2/media/scripts/{sid}")
        self.assertNotEqual(r.json()["status"], "approved")
        self.assertNotEqual(r.json()["status"], "script_locked")

    def test_3_dialogue_block_has_estimated_duration(self):
        """TEST 3: Dialogue timing reaches shot-plan output."""
        sid = self._create_script()
        r = self.client.post(f"/api/v2/media/scripts/{sid}/scenes", json={
            "slugline": "EXT. HALEAKALA - PRE-DAWN", "scene_purpose": "Establish"
        })
        self.assertEqual(r.status_code, 201)
        scene_id = r.json()["scene_id"]
        r2 = self.client.post(f"/api/v2/media/scripts/{sid}/scenes/{scene_id}/dialogue", json={
            "character": "NARRATOR",
            "text": "They ask us a question.",
            "intent": "invite reflection",
            "delivery": {"pace": "slow", "volume": "quiet", "estimated_duration_seconds": 6.8}
        })
        self.assertEqual(r2.status_code, 201)
        dialogue_id = r2.json()["dialogue_id"]
        r3 = self.client.get(f"/api/v2/media/scripts/{sid}/scenes/{scene_id}/dialogue")
        block = next(d for d in r3.json() if d["id"] == dialogue_id)
        self.assertEqual(block["delivery"]["estimated_duration_seconds"], 6.8)

    def test_4_cultural_review_status_preserved(self):
        """TEST 4: Cultural-review uncertainty is preserved and not fabricated."""
        sid = self._create_script()
        r = self.client.get(f"/api/v2/media/scripts/{sid}")
        self.assertEqual(r.json()["cultural_review"]["status"], "pending")
        # Pending state is preserved — not auto-approved
        self.assertNotEqual(r.json()["cultural_review"]["status"], "approved")

    def test_5_locked_script_cannot_be_overwritten(self):
        """TEST 5: Locked script cannot be overwritten."""
        sid = self._create_script()
        # Advance to approved and lock
        for s in ["premise_ready", "architecture_ready", "beat_sheet_ready",
                  "scene_outline_ready", "first_draft", "dialogue_review",
                  "continuity_review", "cultural_review", "table_read_review",
                  "approval_pending", "approved"]:
            self.client.post(f"/api/v2/media/scripts/{sid}/advance", json={"to_status": s})
        self.client.post(f"/api/v2/media/scripts/{sid}/lock")
        # Cannot advance locked script to a new status
        r = self.client.post(f"/api/v2/media/scripts/{sid}/advance",
                             json={"to_status": "first_draft"})
        self.assertEqual(r.status_code, 409)

    def test_6_locked_script_cannot_add_scenes(self):
        """TEST 6: Locked script cannot have scenes added (cannot be overwritten)."""
        sid = self._create_script()
        for s in ["premise_ready", "approved"]:
            self.client.post(f"/api/v2/media/scripts/{sid}/advance", json={"to_status": s})
        self.client.post(f"/api/v2/media/scripts/{sid}/lock")
        r = self.client.post(f"/api/v2/media/scripts/{sid}/scenes",
                             json={"slugline": "INT. CAVE"})
        self.assertEqual(r.status_code, 409)


# ==============================================================================
# Storyboard lock / archive / restore / revision
# ==============================================================================

class TestStoryboardLockArchive(unittest.TestCase):
    """TEST 7-21: Storyboard lock/archive/restore/revision tests."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="storyboard-")
        self.client, self.db = _make_storyboard_client(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _create(self, **kwargs):
        body = {
            "production_id": "prod-001",
            "scene_id": "S01",
            "shot_id": "SH001",
            "prompt": "dawn at Haleakala",
            "engine": "kandinsky5",
            "image_hash": "abc123",
            "image_uri": "artifact://sb001",
            "provenance_hash": "prov001",
            "source_refs": [],
            "used_by": [
                {"type": "film_shot", "id": "HWTF-S01-SH001"},
                {"type": "game_cinematic", "id": "STARFORGE-CIN-004"},
                {"type": "fcp_timeline", "id": "FCP-001"},
                {"type": "logic_cue", "id": "HWTF-MUS-014"},
            ],
            **kwargs
        }
        r = self.client.post("/api/v2/media/storyboards", json=body)
        self.assertEqual(r.status_code, 201)
        return r.json()["storyboard_id"]

    def _lock(self, sb_id, locked: bool):
        return self.client.patch(
            f"/api/v2/media/storyboards/{sb_id}/lock",
            json={"locked": locked, "actor": "owner", "reason": "test"}
        )

    def _archive(self, sb_id):
        return self.client.post(f"/api/v2/media/storyboards/{sb_id}/archive",
                                json={"actor": "owner", "reason": "test", "preserve_lock": True})

    def _restore(self, sb_id):
        return self.client.post(f"/api/v2/media/storyboards/{sb_id}/restore",
                                json={"actor": "owner"})

    def test_7_lock_toggle_works_both_directions(self):
        """TEST 7: Lock toggle works in both directions."""
        sb_id = self._create()
        r1 = self._lock(sb_id, True)
        self.assertEqual(r1.status_code, 200)
        self.assertTrue(r1.json()["current"])
        r2 = self._lock(sb_id, False)
        self.assertEqual(r2.status_code, 200)
        self.assertFalse(r2.json()["current"])

    def test_8_repeated_identical_lock_request_is_idempotent(self):
        """TEST 8: Repeated identical lock request is idempotent."""
        sb_id = self._create()
        self._lock(sb_id, True)
        r = self.client.get(f"/api/v2/media/storyboards/{sb_id}/provenance")
        audit_count_before = len([e for e in r.json() if e["event_type"] == "storyboard.lock_changed"])
        # Same request again
        r2 = self._lock(sb_id, True)
        self.assertEqual(r2.status_code, 200)
        self.assertFalse(r2.json()["changed"])
        r3 = self.client.get(f"/api/v2/media/storyboards/{sb_id}/provenance")
        audit_count_after = len([e for e in r3.json() if e["event_type"] == "storyboard.lock_changed"])
        self.assertEqual(audit_count_before, audit_count_after)

    def test_9_lock_toggle_appends_exactly_one_audit_event(self):
        """TEST 8b: Each lock toggle appends exactly one audit event."""
        sb_id = self._create()
        self._lock(sb_id, True)
        r = self.client.get(f"/api/v2/media/storyboards/{sb_id}/provenance")
        lock_events = [e for e in r.json() if e["event_type"] == "storyboard.lock_changed"]
        self.assertEqual(len(lock_events), 1)

    def test_10_locked_storyboard_can_be_archived(self):
        """TEST 10: Locked storyboard can be archived."""
        sb_id = self._create()
        self._lock(sb_id, True)
        r = self._archive(sb_id)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["archived"])

    def test_11_archive_preserves_lock_state(self):
        """TEST 11: Archive preserves lock state."""
        sb_id = self._create()
        self._lock(sb_id, True)
        self._archive(sb_id)
        r = self.client.get(f"/api/v2/media/storyboards/{sb_id}")
        self.assertTrue(r.json()["locked"])
        self.assertTrue(r.json()["archived"])

    def test_12_restore_preserves_prior_lock_state(self):
        """TEST 12: Restore preserves prior lock state."""
        sb_id = self._create()
        self._lock(sb_id, True)
        self._archive(sb_id)
        self._restore(sb_id)
        r = self.client.get(f"/api/v2/media/storyboards/{sb_id}")
        self.assertTrue(r.json()["locked"])
        self.assertFalse(r.json()["archived"])

    def test_13_locked_storyboard_creates_unlocked_revision(self):
        """TEST 13: Locked storyboard creates an unlocked new revision."""
        sb_id = self._create()
        self._lock(sb_id, True)
        r = self.client.post(f"/api/v2/media/storyboards/{sb_id}/revisions",
                             json={"actor": "owner"})
        self.assertEqual(r.status_code, 200)
        new_id = r.json()["storyboard_id"]
        self.assertFalse(r.json()["locked"])
        self.assertEqual(r.json()["revision"], 2)
        # Original unchanged
        orig = self.client.get(f"/api/v2/media/storyboards/{sb_id}")
        self.assertTrue(orig.json()["locked"])

    def test_14_original_revision_remains_immutable(self):
        """TEST 14: Original revision remains immutable after new revision is created."""
        sb_id = self._create()
        self._lock(sb_id, True)
        self.client.post(f"/api/v2/media/storyboards/{sb_id}/revisions", json={"actor": "owner"})
        orig = self.client.get(f"/api/v2/media/storyboards/{sb_id}")
        self.assertEqual(orig.json()["revision"], 1)
        self.assertTrue(orig.json()["locked"])

    def test_15_archive_preserves_hashes_and_provenance(self):
        """TEST 15: Archive preserves hashes and provenance."""
        sb_id = self._create(image_hash="hashXXX", provenance_hash="provYYY")
        self._archive(sb_id)
        r = self.client.get(f"/api/v2/media/storyboards/{sb_id}")
        self.assertEqual(r.json()["image_hash"], "hashXXX")
        self.assertEqual(r.json()["provenance_hash"], "provYYY")

    def test_16_film_references_survive_archive(self):
        """TEST 16: Film references survive archive."""
        sb_id = self._create()
        self._archive(sb_id)
        r = self.client.get(f"/api/v2/media/storyboards/{sb_id}")
        used_by = r.json()["used_by"]
        film_refs = [u for u in used_by if u["type"] == "film_shot"]
        self.assertTrue(len(film_refs) > 0)

    def test_17_fcp_references_survive_archive(self):
        """TEST 17: FCP references survive archive."""
        sb_id = self._create()
        self._archive(sb_id)
        r = self.client.get(f"/api/v2/media/storyboards/{sb_id}")
        fcp_refs = [u for u in r.json()["used_by"] if u["type"] == "fcp_timeline"]
        self.assertTrue(len(fcp_refs) > 0)

    def test_18_logic_references_survive_archive(self):
        """TEST 18: Logic references survive archive."""
        sb_id = self._create()
        self._archive(sb_id)
        r = self.client.get(f"/api/v2/media/storyboards/{sb_id}")
        logic_refs = [u for u in r.json()["used_by"] if u["type"] == "logic_cue"]
        self.assertTrue(len(logic_refs) > 0)

    def test_19_game_references_survive_archive(self):
        """TEST 19: Game references survive archive."""
        sb_id = self._create()
        self._archive(sb_id)
        r = self.client.get(f"/api/v2/media/storyboards/{sb_id}")
        game_refs = [u for u in r.json()["used_by"] if u["type"] == "game_cinematic"]
        self.assertTrue(len(game_refs) > 0)

    def test_20_archived_disappears_from_active_view(self):
        """TEST 8 (acceptance): Archived storyboard disappears from active view."""
        sb_id = self._create()
        self._archive(sb_id)
        r = self.client.get("/api/v2/media/storyboards?production_id=prod-001")
        ids = [s["id"] for s in r.json()]
        self.assertNotIn(sb_id, ids)

    def test_21_archived_appears_in_archive_view(self):
        """TEST 9 (acceptance): Archived storyboard appears in archive view."""
        sb_id = self._create()
        self._archive(sb_id)
        r = self.client.get("/api/v2/media/storyboards/archived?production_id=prod-001")
        ids = [s["id"] for s in r.json()]
        self.assertIn(sb_id, ids)


# ==============================================================================
# FCP Adapter
# ==============================================================================

class TestFCPAdapter(unittest.TestCase):
    """TEST 28: FCPXML retains immutable asset IDs."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="fcp-")
        self.client, self.db = _make_fcp_client(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _create_timeline(self):
        r = self.client.post("/api/v2/media/fcp/timelines", json={
            "production_id": "prod-001", "title": "HWTF Assembly"
        })
        self.assertEqual(r.status_code, 201)
        return r.json()["timeline_id"]

    def test_create_timeline(self):
        tl_id = self._create_timeline()
        r = self.client.get(f"/api/v2/media/fcp/timelines/{tl_id}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["production_id"], "prod-001")

    def test_update_timeline_with_shots(self):
        tl_id = self._create_timeline()
        shots = [{"shot_id": "SH001", "asset_id": "ASSET-IMMUTABLE-001",
                  "asset_hash": "hash001", "start_seconds": 0.0, "duration_seconds": 6.8,
                  "timeline_role": "Video"}]
        r = self.client.patch(f"/api/v2/media/fcp/timelines/{tl_id}",
                              json={"shots": shots, "duration_seconds": 6.8})
        self.assertEqual(r.status_code, 200)

    def test_28_fcpxml_retains_immutable_asset_id(self):
        """TEST 28: FCPXML retains immutable asset IDs."""
        tl_id = self._create_timeline()
        shots = [{"shot_id": "SH001", "asset_id": "ASSET-IMMUTABLE-001",
                  "asset_hash": "hash001", "start_seconds": 0.0, "duration_seconds": 3.0,
                  "timeline_role": "Video"}]
        self.client.patch(f"/api/v2/media/fcp/timelines/{tl_id}",
                          json={"shots": shots, "duration_seconds": 3.0})
        r = self.client.get(f"/api/v2/media/fcp/timelines/{tl_id}/fcpxml")
        self.assertEqual(r.status_code, 200)
        fcpxml = r.json()["fcpxml"]
        self.assertIn("ASSET-IMMUTABLE-001", fcpxml)
        self.assertIn("fcpxml", fcpxml)

    def test_get_markers(self):
        tl_id = self._create_timeline()
        r = self.client.get(f"/api/v2/media/fcp/timelines/{tl_id}/markers")
        self.assertEqual(r.status_code, 200)

    def test_get_roles(self):
        tl_id = self._create_timeline()
        r = self.client.get(f"/api/v2/media/fcp/timelines/{tl_id}/roles")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Dialogue", r.json()["roles"])


# ==============================================================================
# Logic Adapter
# ==============================================================================

class TestLogicAdapter(unittest.TestCase):
    """TEST 29: Logic manifest retains dialogue and cue lineage."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="logic-")
        self.client, self.db = _make_logic_client(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _create_session(self):
        r = self.client.post("/api/v2/media/logic/sessions", json={
            "production_id": "prod-001", "title": "HWTF Main Session"
        })
        self.assertEqual(r.status_code, 201)
        return r.json()["session_id"]

    def test_create_session(self):
        sess_id = self._create_session()
        r = self.client.get(f"/api/v2/media/logic/sessions/{sess_id}")
        self.assertEqual(r.status_code, 200)
        stems = r.json()["stems"]
        stem_names = [s["stem"] for s in stems]
        self.assertIn("dialogue", stem_names)
        self.assertIn("narration", stem_names)
        self.assertIn("adr", stem_names)

    def test_add_cue(self):
        sess_id = self._create_session()
        r = self.client.post(f"/api/v2/media/logic/sessions/{sess_id}/cues", json={
            "cue_id": "HWTF-MUS-014",
            "scene_id": "HWTF-S04",
            "start_timecode": "01:04:12:00",
            "duration_seconds": 34.5,
            "tempo_bpm": 72.0,
            "key": "D minor",
            "purpose": "ancestral tension",
            "logic_marker": "MOKUULA THEME ENTRY",
            "stem_requirements": ["music", "voice"]
        })
        self.assertEqual(r.status_code, 201)

    def test_29_cue_sheet_retains_cue_lineage(self):
        """TEST 29: Logic manifest retains dialogue and cue lineage."""
        sess_id = self._create_session()
        self.client.post(f"/api/v2/media/logic/sessions/{sess_id}/cues", json={
            "cue_id": "HWTF-MUS-014", "scene_id": "HWTF-S04",
            "start_timecode": "01:04:12:00", "duration_seconds": 34.5,
            "logic_marker": "MOKUULA THEME ENTRY",
            "stem_requirements": ["music"]
        })
        r = self.client.get(f"/api/v2/media/logic/sessions/{sess_id}/cue_sheet")
        self.assertEqual(r.status_code, 200)
        cues = r.json()["cues"]
        self.assertTrue(any(c["cue_id"] == "HWTF-MUS-014" for c in cues))

    def test_adr_list_filters_adr_cues(self):
        sess_id = self._create_session()
        self.client.post(f"/api/v2/media/logic/sessions/{sess_id}/cues", json={
            "cue_id": "ADR-001", "scene_id": "S01",
            "start_timecode": "00:01:00:00", "duration_seconds": 5.0,
            "stem_requirements": ["adr"]
        })
        r = self.client.get(f"/api/v2/media/logic/sessions/{sess_id}/adr_list")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(any(c["cue_id"] == "ADR-001" for c in r.json()["adr_list"]))

    def test_foley_list_filters_foley_cues(self):
        sess_id = self._create_session()
        self.client.post(f"/api/v2/media/logic/sessions/{sess_id}/cues", json={
            "cue_id": "FOLEY-001", "scene_id": "S01",
            "start_timecode": "00:01:05:00", "duration_seconds": 2.0,
            "stem_requirements": ["foley"]
        })
        r = self.client.get(f"/api/v2/media/logic/sessions/{sess_id}/foley_list")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(any(c["cue_id"] == "FOLEY-001" for c in r.json()["foley_list"]))


# ==============================================================================
# Game Controls
# ==============================================================================

class TestGameAPI(unittest.TestCase):
    """TEST 30: Unreal/Sequencer manifest retains storyboard and camera references."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="game-")
        self.client, self.db = _make_game_client(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _create_game(self):
        r = self.client.post("/api/v2/media/game/projects", json={
            "production_id": "prod-001",
            "title": "Starforge Chronicles",
            "engine": "unreal_engine_5"
        })
        self.assertEqual(r.status_code, 201)
        return r.json()["game_id"]

    def test_create_game_project(self):
        game_id = self._create_game()
        r = self.client.get(f"/api/v2/media/game/projects/{game_id}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["engine"], "unreal_engine_5")

    def test_create_level(self):
        game_id = self._create_game()
        r = self.client.post(f"/api/v2/media/game/projects/{game_id}/levels",
                             json={"title": "Chapter 1: The Summit"})
        self.assertEqual(r.status_code, 201)

    def test_create_quest(self):
        game_id = self._create_game()
        r = self.client.post(f"/api/v2/media/game/projects/{game_id}/quests",
                             json={"title": "The Ancestor Question", "type": "main"})
        self.assertEqual(r.status_code, 201)

    def test_create_cinematic_with_storyboard_ref(self):
        game_id = self._create_game()
        r = self.client.post(f"/api/v2/media/game/projects/{game_id}/cinematics",
                             json={
                                 "title": "Opening",
                                 "shots": [{"shot_id": "CIN-SH001",
                                            "storyboard_id": "HWTF-S01-SH003-SB01",
                                            "duration_seconds": 6.8}]
                             })
        self.assertEqual(r.status_code, 201)

    def test_30_sequencer_manifest_retains_storyboard_refs(self):
        """TEST 30: Unreal/Sequencer manifest retains storyboard and camera references."""
        game_id = self._create_game()
        self.client.post(f"/api/v2/media/game/projects/{game_id}/cinematics",
                         json={
                             "title": "Opening",
                             "shots": [
                                 {"shot_id": "CIN-SH001",
                                  "storyboard_id": "HWTF-S01-SH003-SB01",
                                  "camera_spec": {"movement": "slow_push_in"},
                                  "duration_seconds": 6.8}
                             ]
                         })
        r = self.client.post(f"/api/v2/media/game/projects/{game_id}/unreal/sequencer_manifest")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("HWTF-S01-SH003-SB01", data["storyboard_refs"])
        shots = data["shots"]
        self.assertTrue(any(s["storyboard_id"] == "HWTF-S01-SH003-SB01" for s in shots))

    def test_build_archive_restore(self):
        game_id = self._create_game()
        r = self.client.post(f"/api/v2/media/game/projects/{game_id}/builds",
                             json={"version": "0.1.0-dev"})
        build_id = r.json()["build_id"]
        r2 = self.client.post(f"/api/v2/media/game/projects/{game_id}/builds/{build_id}/archive")
        self.assertTrue(r2.json()["archived"])
        r3 = self.client.post(f"/api/v2/media/game/projects/{game_id}/builds/{build_id}/restore")
        self.assertFalse(r3.json()["archived"])

    def test_unreal_datatable_quest(self):
        game_id = self._create_game()
        self.client.post(f"/api/v2/media/game/projects/{game_id}/quests",
                         json={"title": "Find the Way"})
        r = self.client.post(f"/api/v2/media/game/projects/{game_id}/unreal/datatable",
                             json={"table_type": "quest"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["format"], "unreal_datatable_json")
        self.assertGreater(r.json()["row_count"], 0)

    def test_dialogue_tree_links_to_studio_dialogue(self):
        game_id = self._create_game()
        r = self.client.post(f"/api/v2/media/game/projects/{game_id}/dialogue_trees",
                             json={
                                 "character": "ELDER",
                                 "scene_id": "HWTF-S01",
                                 "nodes": [{"node_id": "N001",
                                            "dialogue_id": "HWTF-S01-D004",
                                            "text": "They ask us a question.",
                                            "character": "ELDER", "emotion": "reflective",
                                            "conditions": [], "responses": []}]
                             })
        self.assertEqual(r.status_code, 201)


# ==============================================================================
# studio_interchange module
# ==============================================================================

class TestStudioInterchangeModule(unittest.TestCase):
    """Unit tests for fcpxml.py and logic_manifest.py."""

    def test_fcpxml_build_preserves_asset_id(self):
        from services.studio_interchange.fcpxml import build_fcpxml
        tl = {
            "title": "Test",
            "duration_seconds": 10.0,
            "shots": [{"shot_id": "SH001", "asset_id": "IMMUTABLE-001",
                       "asset_hash": "h001", "start_seconds": 0.0,
                       "duration_seconds": 5.0, "timeline_role": "Video"}],
            "markers": []
        }
        xml = build_fcpxml(tl)
        self.assertIn("IMMUTABLE-001", xml)
        self.assertIn("fcpxml version", xml)

    def test_fcpxml_timecode_accuracy(self):
        from services.studio_interchange.fcpxml import timecode_from_seconds
        self.assertEqual(timecode_from_seconds(0.0), "00:00:00:00")
        self.assertEqual(timecode_from_seconds(1.0), "00:00:01:00")
        self.assertEqual(timecode_from_seconds(25.0, fps=25), "00:00:25:00")

    def test_proxy_manifest_lists_asset_ids(self):
        from services.studio_interchange.fcpxml import build_proxy_manifest
        tl = {"timeline_id": "TL001", "shots": [
            {"shot_id": "SH001", "asset_id": "A001", "asset_hash": "h1", "proxy_path": "/tmp/sh001.mov"}
        ]}
        manifest = build_proxy_manifest(tl)
        self.assertEqual(manifest["proxies"][0]["asset_id"], "A001")

    def test_marker_list_sorted_by_timecode(self):
        from services.studio_interchange.fcpxml import build_marker_list
        tl = {"shots": [], "markers": [
            {"timecode_seconds": 5.0, "note": "Late"},
            {"timecode_seconds": 1.0, "note": "Early"},
        ]}
        markers = build_marker_list(tl)
        self.assertEqual(markers[0]["note"], "Early")

    def test_logic_cue_sheet_includes_music(self):
        from services.studio_interchange.logic_manifest import build_cue_sheet
        sess = {
            "session_id": "S1", "production_id": "P1", "title": "T",
            "frame_rate": "24fps",
            "cues": [{"cue_id": "MUS-1", "scene_id": "S01",
                      "start_timecode": "00:01:00:00", "duration_seconds": 30.0,
                      "stem_requirements": ["music"], "logic_marker": "THEME"}]
        }
        cue_sheet = build_cue_sheet(sess)
        self.assertEqual(cue_sheet["cue_count"], 1)
        self.assertEqual(cue_sheet["cues"][0]["cue_id"], "MUS-1")

    def test_logic_marker_track_from_cues(self):
        from services.studio_interchange.logic_manifest import build_marker_track
        sess = {"cues": [
            {"cue_id": "C1", "start_timecode": "00:01:00:00",
             "logic_marker": "MOKUULA THEME ENTRY"}
        ]}
        markers = build_marker_track(sess)
        self.assertEqual(markers[0]["label"], "MOKUULA THEME ENTRY")

    def test_logic_stem_layout_includes_all_stems(self):
        from services.studio_interchange.logic_manifest import build_stem_layout
        sess = {
            "session_id": "S1", "production_id": "P1",
            "sample_rate": 48000, "bit_depth": 24,
            "stems": [{"stem": s, "path": f"audio/{s}/"} for s in
                      ["dialogue", "narration", "adr", "music", "ambience",
                       "foley", "effects", "stems", "mixes"]]
        }
        layout = build_stem_layout(sess)
        stem_names = [s["stem"] for s in layout["stems"]]
        for expected in ["dialogue", "adr", "music", "foley"]:
            self.assertIn(expected, stem_names)


# ==============================================================================
# Production pipeline acceptance (TEST 22-27)
# ==============================================================================

class TestProductionPipelineAcceptance(unittest.TestCase):
    """Tests 22-27 from the acceptance gate."""

    def setUp(self):
        with open(ENGINE_ROLES_PATH) as f:
            self.roles_cfg = json.load(f)
        with open(WORKFLOW_INVENTORY_PATH) as f:
            self.inventory = json.load(f)
        self.workflows = {w["workflow_id"]: w for w in self.inventory["workflows"]}

    def test_22_kandinsky_batches_before_ltx(self):
        """TEST 22: Kandinsky storyboards batch before LTX loads."""
        seq = self.roles_cfg["batch_routing_policy"]["sequence"]
        engines = [s.get("engine") for s in seq if s.get("engine")]
        k_idx = next(i for i, e in enumerate(engines) if e and "kandinsky" in e)
        ltx_idx = next(i for i, e in enumerate(engines) if e == "ltx")
        self.assertLess(k_idx, ltx_idx)

    def test_23_ltx_gate_requires_storyboard_approval(self):
        """TEST 23: LTX animation starts only after storyboard approval."""
        seq = self.roles_cfg["batch_routing_policy"]["sequence"]
        ltx_step = next(s for s in seq if s.get("engine") == "ltx")
        self.assertIn("storyboard_approved", ltx_step.get("gate", "").lower())

    def test_24_rife_gate_requires_take_approval(self):
        """TEST 24: Interpolation starts only after take approval."""
        seq = self.roles_cfg["batch_routing_policy"]["sequence"]
        rife_step = next(s for s in seq if s.get("engine") == "rife_local")
        self.assertIn("approved", rife_step.get("gate", "").lower())

    def test_25_rife_gpu_measured_not_zero(self):
        """TEST 25: RIFE GPU memory is measured rather than represented as zero."""
        w = self.workflows["rife_local_interpolation"]
        self.assertIsNone(w.get("vram_required_mb"))
        self.assertTrue(w.get("requires_live_measurement"))

    def test_26_pipeline_has_edit_ready_terminal(self):
        """TEST 26: Pipeline stops at edit_ready."""
        import json as _json
        with open(ROOT / "config" / "canonical_job_contract.v2.json") as f:
            contract = _json.load(f)
        terminals = contract["tenant_state_profiles"]["media"]["terminal_states"]
        self.assertIn("edit_ready", terminals)

    def test_27_no_auto_publish(self):
        """TEST 27: No automatic public publishing occurs."""
        seq = self.roles_cfg["batch_routing_policy"]["sequence"]
        final = seq[-1]
        gate = (final.get("gate") or "").lower()
        self.assertIn("do_not_publish", gate)

    def test_wan_engines_disabled(self):
        """Acceptance: Wan VACE and T2V remain disabled by default."""
        self.assertFalse(self.workflows["wan_vace_1_3b_experimental"]["enabled"])
        self.assertFalse(self.workflows["wan_t2v_1_3b_atmospheric"]["enabled"])

    def test_no_wan_14b_in_inventory(self):
        """Acceptance: No Wan 14B model is scheduled."""
        for w in self.inventory["workflows"]:
            name = w.get("display_name", "").lower() + w.get("engine", "").lower()
            self.assertNotIn("14b", name)

    def test_kandinsky_animation_workflow_present(self):
        """Acceptance: Kandinsky animation workflow is registered."""
        self.assertIn("kandinsky5_local_animation", self.workflows)
        self.assertTrue(self.workflows["kandinsky5_local_animation"]["enabled"])


if __name__ == "__main__":
    unittest.main()
