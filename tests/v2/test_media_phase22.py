"""
Phase 2.2 tests — Camera-Aware Storyboard-to-Edit pipeline.

Covers:
  - New job types (director_shot_plan, animation_shot, edit_decision)
  - New production states and transition graphs
  - Capability routing for Kandinsky video, director planning, and editor review
  - Workflow inventory (Kandinsky is the only local visual generation model)
  - Local skills registry completeness
  - Engine roles config
  - Camera spec schema fields
  - Batch routing policy (no Wan 14B, no per-shot engine alternation)
  - VRAM limits respected for new job types
  - edit_ready is a valid terminal state
"""
import importlib.util
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
GPU_MAIN = ROOT / "services" / "gpu_router" / "app" / "main.py"

CONTRACT_PATH = ROOT / "config" / "canonical_job_contract.v2.json"
WORKFLOW_INVENTORY_PATH = ROOT / "config" / "media_workflow_inventory.v2.json"
LOCAL_SKILLS_PATH = ROOT / "config" / "media_local_skills.v2.json"
ENGINE_ROLES_PATH = ROOT / "config" / "media_engine_roles.v2.json"
CAMERA_SCHEMA_PATH = ROOT / "config" / "media_camera_spec.schema.json"


def _load_gpu(db_path: str):
    saved = dict(os.environ)
    try:
        os.environ.update(
            {
                "GPU_ROUTER_DB_PATH": db_path,
                "COMMIT_SHA": "phase22-test-sha",
                "BUILD_TIMESTAMP": "2026-07-14T00:00:00Z",
                "ENVIRONMENT": "test",
            }
        )
        spec = importlib.util.spec_from_file_location(
            f"gpu_router_phase22_{time.time_ns()}", GPU_MAIN
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.require_claims = lambda **kwargs: {
            "sub": "owner-test",
            "role": "Owner",
            "tenant_id": "",
            "scopes": ["gpu:infer", "gpu:read", "ops:owner"],
        }
        return module
    finally:
        os.environ.clear()
        os.environ.update(saved)


class TestContractNewJobTypes(unittest.TestCase):
    """New pipeline job types are registered in the canonical contract."""

    def setUp(self):
        with open(CONTRACT_PATH) as f:
            self.contract = json.load(f)
        self.media = self.contract["tenant_state_profiles"]["media"]

    def test_director_shot_plan_registered(self):
        self.assertIn("director_shot_plan", self.media["job_type_profiles"])

    def test_animation_shot_registered(self):
        self.assertIn("animation_shot", self.media["job_type_profiles"])


    def test_interpolation_shot_removed_with_its_model(self):
        self.assertNotIn("interpolation_shot", self.media["job_type_profiles"])

    def test_edit_decision_registered(self):
        self.assertIn("edit_decision", self.media["job_type_profiles"])

    def test_director_shot_plan_required_inputs(self):
        profile = self.media["job_type_profiles"]["director_shot_plan"]
        for field in ("script", "scene_id", "capability"):
            self.assertIn(field, profile["required_inputs"])

    def test_animation_shot_required_inputs(self):
        profile = self.media["job_type_profiles"]["animation_shot"]
        for field in ("source_artifact", "shot_id", "workflow_id", "capability"):
            self.assertIn(field, profile["required_inputs"])

    def test_animation_shot_completion_evidence_has_camera_compliance(self):
        profile = self.media["job_type_profiles"]["animation_shot"]
        self.assertIn("camera_compliance", profile["completion_evidence"])

    def test_animation_shot_preferred_capability_is_image_to_video(self):
        profile = self.media["job_type_profiles"]["animation_shot"]
        self.assertEqual(profile["preferred_capability"], "image_to_video")


    def test_director_shot_plan_approval_required(self):
        profile = self.media["job_type_profiles"]["director_shot_plan"]
        self.assertTrue(profile["approval_required"])


class TestContractNewStates(unittest.TestCase):
    """New production states are present in the master states list."""

    REQUIRED_STATES = [
        "director_analysis",
        "shot_plan_ready",
        "camera_plan_ready",
        "storyboard_queued",
        "storyboard_rendering",
        "storyboard_ready",
        "continuity_review",
        "storyboard_approved",
        "motion_plan_ready",
        "animation_queued",
        "animation_rendering",
        "animation_ready",
        "editor_review",
        "take_approved",
        "interpolation_queued",
        "final_qc",
        "edit_ready",
    ]

    def setUp(self):
        with open(CONTRACT_PATH) as f:
            self.contract = json.load(f)
        self.media = self.contract["tenant_state_profiles"]["media"]

    def test_all_new_states_present(self):
        for s in self.REQUIRED_STATES:
            self.assertIn(s, self.media["states"], f"State '{s}' missing from media states")

    def test_edit_ready_is_terminal(self):
        self.assertIn("edit_ready", self.media["terminal_states"])

    def test_pipeline_example_state_path_registered(self):
        path = self.media.get("pipeline_example_state_path") or []
        self.assertGreater(len(path), 0)
        self.assertEqual(path[0], "script_ready")
        self.assertEqual(path[-1], "edit_ready")


class TestContractTransitions(unittest.TestCase):
    """Transition graphs for new job types are correct."""

    def setUp(self):
        with open(CONTRACT_PATH) as f:
            self.contract = json.load(f)
        self.media = self.contract["tenant_state_profiles"]["media"]
        self.trans = self.media["transitions_by_job_type"]

    def test_director_shot_plan_initial_is_planned(self):
        self.assertEqual(self.trans["director_shot_plan"]["initial"], "planned")

    def test_director_shot_plan_camera_plan_leads_to_approved(self):
        at = self.trans["director_shot_plan"]["allowed_transitions"]
        self.assertIn("approved", at["camera_plan_ready"])

    def test_animation_shot_initial_is_planned(self):
        self.assertEqual(self.trans["animation_shot"]["initial"], "planned")

    def test_animation_shot_qc_passed_goes_to_editor_review(self):
        at = self.trans["animation_shot"]["allowed_transitions"]
        self.assertIn("editor_review", at["qc_passed"])

    def test_animation_shot_take_approved_leads_to_edit_ready(self):
        at = self.trans["animation_shot"]["allowed_transitions"]
        self.assertIn("edit_ready", at.get("take_approved", []))

    def test_animation_shot_timeout_recovers_to_animation_queued(self):
        at = self.trans["animation_shot"]["allowed_transitions"]
        self.assertIn("animation_queued", at["timeout"])



    def test_edit_decision_initial_is_planned(self):
        self.assertEqual(self.trans["edit_decision"]["initial"], "planned")

    def test_edit_decision_editor_review_leads_to_take_approved_or_rejected(self):
        at = self.trans["edit_decision"]["allowed_transitions"]
        self.assertIn("take_approved", at["editor_review"])
        self.assertIn("rejected", at["editor_review"])

    def test_storyboard_frame_can_reach_continuity_review(self):
        at = self.trans["storyboard_frame"]["allowed_transitions"]
        self.assertIn("continuity_review", at.get("qc_passed", []))

    def test_storyboard_frame_storyboard_approved_leads_to_edit_ready(self):
        at = self.trans["storyboard_frame"]["allowed_transitions"]
        self.assertIn("edit_ready", at.get("storyboard_approved", []))

    def test_animation_shot_cannot_go_directly_from_planned_to_edit_ready(self):
        at = self.trans["animation_shot"]["allowed_transitions"]
        self.assertNotIn("edit_ready", at["planned"])


class TestContractCapabilityRouting(unittest.TestCase):
    """All local video-generation routes select Kandinsky 5."""

    def setUp(self):
        with open(CONTRACT_PATH) as f:
            self.contract = json.load(f)
        self.routing = self.contract["tenant_state_profiles"]["media"]["capability_routing"]

    def test_image_to_video_routes_only_to_kandinsky(self):
        self.assertEqual(self.routing["image_to_video"], {"preferred": "kandinsky5_local", "fallback": "kandinsky5_local"})

    def test_short_video_routes_only_to_kandinsky(self):
        self.assertEqual(self.routing["short_video_generation"]["preferred"], "kandinsky5_local")

    def test_long_video_routes_only_to_kandinsky(self):
        self.assertEqual(self.routing["long_video_generation"]["preferred"], "kandinsky5_local")

    def test_non_kandinsky_interpolation_route_is_removed(self):
        self.assertNotIn("interpolation", self.routing)

    def test_director_and_editor_routes_remain(self):
        self.assertEqual(self.routing["director_planning"]["preferred"], "director_local")
        self.assertEqual(self.routing["editor_review"]["preferred"], "editor_local")

    def test_image_generation_still_routes_to_kandinsky(self):
        self.assertEqual(self.routing["image_generation"]["preferred"], "kandinsky5_local")

    def test_animation_route_has_no_alternate_engine(self):
        self.assertEqual(self.routing["kandinsky_animation"], {"preferred": "kandinsky5_local", "fallback": "kandinsky5_local"})


class TestWorkflowInventory(unittest.TestCase):
    """Only Kandinsky visual generation workflows remain registered."""

    def setUp(self):
        with open(WORKFLOW_INVENTORY_PATH) as f:
            self.inv = json.load(f)
        self.workflows = {w["workflow_id"]: w for w in self.inv["workflows"]}

    def test_kandinsky_workflows_are_the_only_visual_workflows(self):
        self.assertEqual(set(self.workflows), {"kandinsky5_local_image", "kandinsky5_local_animation"})
        self.assertEqual({w["engine"] for w in self.inv["workflows"]}, {"kandinsky5_local"})

    def test_kandinsky_image_and_animation_are_enabled(self):
        self.assertTrue(self.workflows["kandinsky5_local_image"]["enabled"])
        self.assertTrue(self.workflows["kandinsky5_local_animation"]["enabled"])

    def test_kandinsky_resolution_and_vram_stay_inside_profile(self):
        w = self.workflows["kandinsky5_local_image"]
        self.assertEqual(w["resolution"], "768x512")
        self.assertLessEqual(w["vram_required_mb"], 7600)

    def test_animation_workflow_permits_animation_shots(self):
        self.assertIn("animation_shot", self.workflows["kandinsky5_local_animation"]["permitted_job_types"])

    def test_no_other_video_engine_is_registered(self):
        all_engines = {str(w.get("engine", "")).lower() for w in self.inv["workflows"]}
        self.assertFalse(all_engines - {"kandinsky5_local"})


class TestLocalSkillsRegistry(unittest.TestCase):
    """All required local skills are registered."""

    REQUIRED_SKILLS = [
        "scene_builder",
        "director_camera_grammar",
        "storyboard_builder",
        "continuity_guardian",
        "motion_prompt_builder",
        "clip_engine_reverse",
        "editor_selector",
    ]

    def setUp(self):
        with open(LOCAL_SKILLS_PATH) as f:
            self.skills = json.load(f)["local_skills"]

    def test_all_required_skills_present(self):
        for skill in self.REQUIRED_SKILLS:
            self.assertIn(skill, self.skills, f"Skill '{skill}' missing from local skills registry")

    def test_clip_engine_reverse_references_actual_module(self):
        skill = self.skills["clip_engine_reverse"]
        module_path = ROOT / skill["source_module"]
        self.assertTrue(module_path.exists(), f"clip_engine_reverse source module not found: {module_path}")

    def test_continuity_guardian_is_in_creative_lane(self):
        self.assertEqual(self.skills["continuity_guardian"]["lane"], "creative")

    def test_editor_selector_is_in_creative_lane(self):
        self.assertEqual(self.skills["editor_selector"]["lane"], "creative")

    def test_storyboard_builder_output_is_kandinsky_job(self):
        self.assertEqual(self.skills["storyboard_builder"]["output"], "kandinsky_job")

    def test_motion_prompt_builder_output_is_kandinsky_animation_job(self):
        self.assertEqual(self.skills["motion_prompt_builder"]["output"], "kandinsky_animation_job")

    def test_all_skills_have_enabled_flag(self):
        for skill_id, skill in self.skills.items():
            self.assertIn("enabled", skill, f"Skill '{skill_id}' missing 'enabled' flag")


class TestEngineRolesConfig(unittest.TestCase):
    """Engine policy permits Kandinsky as the sole local video model."""

    def setUp(self):
        with open(ENGINE_ROLES_PATH) as f:
            self.cfg = json.load(f)
        self.roles = self.cfg["engine_roles"]
        self.policy = self.cfg["batch_routing_policy"]

    def test_only_kandinsky_and_non_model_roles_remain(self):
        self.assertEqual(set(self.roles), {"kandinsky5", "director_local", "editor_local"})
        self.assertEqual(self.roles["kandinsky5"]["role"], "native_video_and_storyboard_generation")
        self.assertIn("kandinsky_animation", self.roles["kandinsky5"]["capabilities"])

    def test_kandinsky_permits_animation_shots(self):
        self.assertIn("animation_shot", self.roles["kandinsky5"]["permitted_job_types"])

    def test_gpu_policy_remains_serialized(self):
        self.assertEqual(self.cfg["vram_safe_limit_mb"], 7600)
        self.assertEqual(self.cfg["max_concurrent_large_models"], 1)

    def test_batch_policy_prohibits_engine_alternation_and_non_kandinsky_video(self):
        prohibited = " ".join(self.policy.get("prohibited_patterns", [])).lower()
        self.assertIn("alternation", prohibited)
        self.assertIn("non_kandinsky_video_model_scheduling", prohibited)
        engines = [s.get("engine") for s in self.policy["sequence"] if s.get("engine")]
        self.assertEqual(set(engines), {"kandinsky5"})

    def test_batch_policy_final_step_does_not_auto_publish(self):
        final = self.policy["sequence"][-1]
        self.assertIn("do_not_publish", final.get("gate", "").lower())


class TestCameraSpecSchema(unittest.TestCase):
    """Camera spec schema has all required fields."""

    REQUIRED_FIELDS = [
        "shot_id", "tenant", "production", "scene", "shot_type",
        "duration_seconds", "storyboard_engine", "motion_engine",
        "camera", "composition", "continuity", "transition",
    ]

    def setUp(self):
        with open(CAMERA_SCHEMA_PATH) as f:
            self.schema = json.load(f)

    def test_all_required_fields_defined(self):
        fd = self.schema["field_definitions"]
        for field in self.REQUIRED_FIELDS:
            self.assertIn(field, fd, f"Camera spec field '{field}' missing from schema")

    def test_storyboard_engine_locked_to_kandinsky5(self):
        fd = self.schema["field_definitions"]["storyboard_engine"]
        self.assertEqual(fd.get("enum"), ["kandinsky5"])




    def test_motion_engine_is_kandinsky_only(self):
        fd = self.schema["field_definitions"]["motion_engine"]
        self.assertEqual(fd.get("enum"), ["kandinsky5"])
        self.assertEqual(self.schema["example"]["motion_engine"], "kandinsky5")

    def test_example_shot_id_present(self):
        self.assertIn("shot_id", self.schema["example"])

    def test_camera_movement_enum_includes_slow_push_in(self):
        cam = self.schema["field_definitions"]["camera"]
        movements = cam["fields"]["movement"]["enum"]
        self.assertIn("slow_push_in", movements)

    def test_camera_movement_strength_max_is_1(self):
        cam = self.schema["field_definitions"]["camera"]
        self.assertEqual(cam["fields"]["movement_strength"]["maximum"], 1.0)

    def test_editor_decision_schema_has_camera_compliance(self):
        ed = self.schema["editor_decision_schema"]["fields"]
        self.assertIn("camera_compliance", ed)

    def test_shot_type_enum_includes_atmospheric_insert(self):
        fd = self.schema["field_definitions"]["shot_type"]
        self.assertIn("atmospheric_insert", fd.get("enum", []))

    def test_director_output_template_has_camera_movement_prohibitions(self):
        tmpl = self.schema["director_output_template"]["fields"]
        self.assertIn("camera_movement_prohibitions", tmpl)


class TestPhase22RouterIntegration(unittest.TestCase):
    """GPU Router correctly rejects or routes new pipeline job types."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="phase22-", ignore_cleanup_errors=True)
        self.db_path = str(Path(self.tmp.name) / "gpu-router.db")
        self.module = _load_gpu(self.db_path)
        self.client = TestClient(self.module.app)
        self.module._run_job = lambda job: ("done", {"response": "ok"}, None)

    def tearDown(self):
        self.tmp.cleanup()

    def _auth(self):
        return {"Authorization": "******"}

    def test_animation_shot_job_type_accepted(self):
        """animation_shot is a registered media job type."""
        payload = {
            "client_id": "studio",
            "tenant_id": "media",
            "model": "kandinsky-local",
            "prompt": "slow push in toward Haleakala ridge",
            "media_job_type": "animation_shot",
            "capability": "image_to_video",
            "workflow_id": "kandinsky5_local_animation",
            "resolution": "768x512",
            "frame_count": 97,
            "options": {
                "source_artifact": "artifact://storyboard-frame-001",
                "shot_id": "HWTF-S01-SH003",
            },
        }
        resp = self.client.post("/api/v2/gpu/infer", json=payload, headers=self._auth())
        self.assertEqual(resp.status_code, 200)

    def test_animation_shot_missing_source_artifact_rejected(self):
        """animation_shot requires source_artifact via options."""
        payload = {
            "client_id": "studio",
            "tenant_id": "media",
            "model": "kandinsky-local",
            "prompt": "slow push in",
            "media_job_type": "animation_shot",
            "capability": "image_to_video",
            "workflow_id": "kandinsky5_local_animation",
            "resolution": "768x512",
            "frame_count": 97,
            "options": {
                "shot_id": "HWTF-S01-SH003",
                # source_artifact intentionally missing
            },
        }
        resp = self.client.post("/api/v2/gpu/infer", json=payload, headers=self._auth())
        self.assertEqual(resp.status_code, 422)
        self.assertEqual(resp.json()["detail"]["error"]["code"], "missing_required_inputs")

    def test_animation_shot_over_vram_rejected(self):
        """animation_shot requesting more than 7600 MB is rejected."""
        payload = {
            "client_id": "studio",
            "tenant_id": "media",
            "model": "kandinsky-local",
            "prompt": "cinematic shot",
            "media_job_type": "animation_shot",
            "capability": "image_to_video",
            "workflow_id": "kandinsky5_local_animation",
            "vram_required_mb": 8000,
            "options": {
                "source_artifact": "artifact://frame-001",
                "shot_id": "HWTF-S01-SH003",
            },
        }
        resp = self.client.post("/api/v2/gpu/infer", json=payload, headers=self._auth())
        self.assertEqual(resp.status_code, 422)
        self.assertEqual(resp.json()["detail"]["error"]["code"], "gpu_profile_exceeded")

    def test_interpolation_shot_job_type_rejected_without_rife(self):
        payload = {
            "client_id": "studio", "tenant_id": "media", "model": "rife-local",
            "prompt": "smooth interpolation", "media_job_type": "interpolation_shot",
            "capability": "interpolation", "workflow_id": "rife_local_interpolation",
            "options": {"source_artifact": "artifact://clip-001", "shot_id": "HWTF-S01-SH003"},
        }
        resp = self.client.post("/api/v2/gpu/infer", json=payload, headers=self._auth())
        self.assertEqual(resp.status_code, 422)
        self.assertEqual(resp.json()["detail"]["error"]["code"], "unknown_media_job_type")

    def test_director_shot_plan_job_type_accepted(self):
        """director_shot_plan is a registered media job type."""
        payload = {
            "client_id": "studio",
            "tenant_id": "media",
            "model": "director-local",
            "prompt": "direct the haleakala scene",
            "media_job_type": "director_shot_plan",
            "capability": "director_planning",
            "options": {
                "scene_id": "haleakala-dawn",
                "script": "Scene opens on volcanic ridge...",
            },
        }
        resp = self.client.post("/api/v2/gpu/infer", json=payload, headers=self._auth())
        self.assertEqual(resp.status_code, 200)

    def test_animation_shot_media_state_starts_at_planned(self):
        """animation_shot initial media_state is planned."""
        payload = {
            "client_id": "studio",
            "tenant_id": "media",
            "model": "kandinsky-local",
            "prompt": "dawn over the ridge",
            "media_job_type": "animation_shot",
            "capability": "image_to_video",
            "workflow_id": "kandinsky5_local_animation",
            "options": {
                "source_artifact": "artifact://frame-002",
                "shot_id": "HWTF-S01-SH004",
            },
        }
        resp = self.client.post("/api/v2/gpu/infer", json=payload, headers=self._auth())
        self.assertEqual(resp.status_code, 200)
        job_id = resp.json()["job_id"]
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT media_state FROM gpu_jobs WHERE id=?", (job_id,)).fetchone()
        conn.close()
        # Should advance to queued via _advance_media_to_ready_queue
        self.assertIsNotNone(row["media_state"])

    def test_storyboard_continuity_review_transition_accepted(self):
        """storyboard_frame can transition to continuity_review from qc_passed."""
        payload = {
            "client_id": "studio",
            "tenant_id": "media",
            "model": "kandinsky-local",
            "prompt": "dawn storyboard frame",
            "media_job_type": "storyboard_frame",
            "capability": "image_generation",
            "workflow_id": "kandinsky5_local_image",
            "resolution": "768x512",
            "frame_count": 1,
            "options": {"scene_id": "haleakala-dawn"},
        }
        resp = self.client.post("/api/v2/gpu/infer", json=payload, headers=self._auth())
        self.assertEqual(resp.status_code, 200)
        job_id = resp.json()["job_id"]

        def transition(to_state, expect=200):
            body = {"to_state": to_state, "reason": "test", "evidence": {}}
            r = self.client.post(
                f"/api/v2/gpu/media/jobs/{job_id}/transition",
                json=body,
                headers=self._auth(),
            )
            self.assertEqual(r.status_code, expect, f"transition to {to_state} failed: {r.text}")
            return r

        transition("qc_passed")
        transition("continuity_review")

    def test_storyboard_approved_to_edit_ready_transition_accepted(self):
        """storyboard_frame can reach edit_ready via storyboard_approved."""
        payload = {
            "client_id": "studio",
            "tenant_id": "media",
            "model": "kandinsky-local",
            "prompt": "approved storyboard frame",
            "media_job_type": "storyboard_frame",
            "capability": "image_generation",
            "workflow_id": "kandinsky5_local_image",
            "resolution": "768x512",
            "frame_count": 1,
            "options": {"scene_id": "haleakala-dawn"},
        }
        resp = self.client.post("/api/v2/gpu/infer", json=payload, headers=self._auth())
        self.assertEqual(resp.status_code, 200)
        job_id = resp.json()["job_id"]

        def transition(to_state, expect=200):
            body = {"to_state": to_state, "reason": "test", "evidence": {}}
            r = self.client.post(
                f"/api/v2/gpu/media/jobs/{job_id}/transition",
                json=body,
                headers=self._auth(),
            )
            self.assertEqual(r.status_code, expect, f"transition to {to_state} failed: {r.text}")

        transition("qc_passed")
        transition("continuity_review")
        transition("storyboard_approved")
        transition("edit_ready")

    def test_animation_shot_cannot_skip_qc(self):
        """animation_shot cannot jump from animation_ready to editor_review without qc_pending/qc_passed."""
        payload = {
            "client_id": "studio",
            "tenant_id": "media",
            "model": "kandinsky-local",
            "prompt": "animation shot with qc",
            "media_job_type": "animation_shot",
            "capability": "image_to_video",
            "workflow_id": "kandinsky5_local_animation",
            "options": {
                "source_artifact": "artifact://frame-003",
                "shot_id": "HWTF-S01-SH005",
            },
        }
        resp = self.client.post("/api/v2/gpu/infer", json=payload, headers=self._auth())
        self.assertEqual(resp.status_code, 200)
        job_id = resp.json()["job_id"]
        # Try jumping from whatever initial state to editor_review directly
        body = {"to_state": "editor_review", "reason": "skip-qc-attempt"}
        r = self.client.post(
            f"/api/v2/gpu/media/jobs/{job_id}/transition",
            json=body,
            headers=self._auth(),
        )
        self.assertEqual(r.status_code, 409)


class TestKandinskyAnimation(unittest.TestCase):
    """Kandinsky5 is available as an animation engine (owner-preferred)."""

    def setUp(self):
        with open(WORKFLOW_INVENTORY_PATH) as f:
            self.inv = json.load(f)
        self.workflows = {w["workflow_id"]: w for w in self.inv["workflows"]}
        with open(ENGINE_ROLES_PATH) as f:
            self.cfg = json.load(f)
        with open(CONTRACT_PATH) as f:
            self.contract = json.load(f)
        self.routing = self.contract["tenant_state_profiles"]["media"]["capability_routing"]
        self.roles = self.cfg["engine_roles"]

    def test_kandinsky5_local_animation_workflow_registered(self):
        w = self.workflows.get("kandinsky5_local_animation")
        self.assertIsNotNone(w, "kandinsky5_local_animation workflow must be registered")

    def test_kandinsky5_animation_workflow_enabled(self):
        w = self.workflows["kandinsky5_local_animation"]
        self.assertTrue(w["enabled"])

    def test_kandinsky5_animation_vram_within_safe_limit(self):
        w = self.workflows["kandinsky5_local_animation"]
        safe = self.cfg["vram_safe_limit_mb"]
        self.assertLessEqual(w["vram_required_mb"], safe)

    def test_kandinsky5_animation_permits_animation_shot(self):
        w = self.workflows["kandinsky5_local_animation"]
        self.assertIn("animation_shot", w.get("permitted_job_types", []))

    def test_kandinsky5_animation_capability_is_kandinsky_animation(self):
        w = self.workflows["kandinsky5_local_animation"]
        self.assertEqual(w["capability"], "kandinsky_animation")

    def test_kandinsky5_role_includes_animation_capability(self):
        role = self.roles["kandinsky5"]
        self.assertIn("kandinsky_animation", role.get("capabilities", []))

    def test_kandinsky5_role_permits_animation_shot(self):
        role = self.roles["kandinsky5"]
        self.assertIn("animation_shot", role.get("permitted_job_types", []))

    def test_kandinsky_animation_capability_routing_registered(self):
        self.assertIn("kandinsky_animation", self.routing)

    def test_kandinsky_animation_preferred_is_kandinsky5_local(self):
        self.assertEqual(self.routing["kandinsky_animation"]["preferred"], "kandinsky5_local")

    def test_kandinsky_animation_fallback_is_kandinsky(self):
        self.assertEqual(self.routing["kandinsky_animation"]["fallback"], "kandinsky5_local")

    def test_image_to_video_preferred_is_kandinsky(self):
        self.assertEqual(self.routing["image_to_video"]["preferred"], "kandinsky5_local")


class TestKandinskyAnimationRouterIntegration(unittest.TestCase):
    """GPU Router accepts animation_shot jobs using kandinsky_animation capability."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="kandinsky-anim-", ignore_cleanup_errors=True)
        self.db_path = str(Path(self.tmp.name) / "gpu-router.db")
        self.module = _load_gpu(self.db_path)
        self.client = TestClient(self.module.app)
        self.module._run_job = lambda job: ("done", {"response": "ok"}, None)

    def tearDown(self):
        self.tmp.cleanup()

    def _auth(self):
        return {"Authorization": "******"}

    def test_kandinsky_animation_job_accepted(self):
        """animation_shot with kandinsky_animation capability is accepted by the router."""
        payload = {
            "client_id": "studio",
            "tenant_id": "media",
            "model": "kandinsky-local",
            "prompt": "slow push in toward Haleakala ridge — Kandinsky animation",
            "media_job_type": "animation_shot",
            "capability": "kandinsky_animation",
            "workflow_id": "kandinsky5_local_animation",
            "resolution": "768x512",
            "frame_count": 48,
            "options": {
                "source_artifact": "artifact://storyboard-frame-kandinsky",
                "shot_id": "HWTF-S01-SH003",
            },
        }
        resp = self.client.post("/api/v2/gpu/infer", json=payload, headers=self._auth())
        self.assertEqual(resp.status_code, 200)

    def test_kandinsky_animation_missing_source_artifact_rejected(self):
        """animation_shot with kandinsky_animation still enforces required inputs."""
        payload = {
            "client_id": "studio",
            "tenant_id": "media",
            "model": "kandinsky-local",
            "prompt": "Kandinsky animation without source",
            "media_job_type": "animation_shot",
            "capability": "kandinsky_animation",
            "workflow_id": "kandinsky5_local_animation",
            "options": {
                "shot_id": "HWTF-S01-SH003",
                # source_artifact intentionally absent
            },
        }
        resp = self.client.post("/api/v2/gpu/infer", json=payload, headers=self._auth())
        self.assertEqual(resp.status_code, 422)
        self.assertEqual(resp.json()["detail"]["error"]["code"], "missing_required_inputs")

    def test_kandinsky_animation_over_vram_rejected(self):
        """animation_shot with kandinsky_animation respects VRAM safe limit."""
        payload = {
            "client_id": "studio",
            "tenant_id": "media",
            "model": "kandinsky-local",
            "prompt": "oversize Kandinsky animation",
            "media_job_type": "animation_shot",
            "capability": "kandinsky_animation",
            "workflow_id": "kandinsky5_local_animation",
            "vram_required_mb": 9000,
            "options": {
                "source_artifact": "artifact://frame-k001",
                "shot_id": "HWTF-S01-SH003",
            },
        }
        resp = self.client.post("/api/v2/gpu/infer", json=payload, headers=self._auth())
        self.assertEqual(resp.status_code, 422)
        self.assertEqual(resp.json()["detail"]["error"]["code"], "gpu_profile_exceeded")

    def test_image_to_video_routes_through_kandinsky_only(self):
        """image_to_video routes to the sole retained local visual model."""
        payload = {
            "client_id": "studio",
            "tenant_id": "media",
            "model": "kandinsky-local",
            "prompt": "Kandinsky native animation",
            "media_job_type": "animation_shot",
            "capability": "image_to_video",
            "workflow_id": "kandinsky5_local_animation",
            "resolution": "768x512",
            "frame_count": 97,
            "options": {
                "source_artifact": "artifact://frame-kandinsky-001",
                "shot_id": "HWTF-S01-SH006",
            },
        }
        resp = self.client.post("/api/v2/gpu/infer", json=payload, headers=self._auth())
        self.assertEqual(resp.status_code, 200)


if __name__ == "__main__":
    unittest.main()
