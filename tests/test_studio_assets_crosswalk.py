import inspect
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from services.studio_assets.app import main, project_api, security


class StudioAssetCrosswalkTests(unittest.TestCase):
    def test_routine_health_is_logged_as_a_receipt_not_queued_as_work(self):
        stderr = io.StringIO()
        with mock.patch.object(main.sys, "stderr", stderr):
            main._log_receipt("studio.assets.online", "online", {"total": 2})
        receipt = json.loads(stderr.getvalue())
        self.assertEqual(receipt["kind"], "studio-assets-receipt")
        self.assertEqual(receipt["action"], "studio.assets.online")
        self.assertNotIn("workboard-job-v2", stderr.getvalue())

    def test_resolves_tenant_character_style_assignment(self):
        data = {
            "_schema": "studio-asset-crosswalk-v1",
            "tenants": [{"id": "film_keys", "film_key": "KEYS_OF_STARFORGE", "default_style": "animated"}],
            "assignments": [{
                "id": "film_keys::KAI::animated", "tenant": "film_keys", "character_id": "KAI",
                "character": "Kai Awai", "aliases": ["Kai"], "style": "animated",
            }],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "crosswalk.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(data, handle)
            with mock.patch.object(main, "STUDIO_CROSSWALK_JSON", path):
                main._CROSSWALK_CACHE.update({"mtime": -1.0, "data": {}})
                assignment = main.resolve_assignment("KEYS_OF_STARFORGE", "Kai", "")
        self.assertEqual(assignment["id"], "film_keys::KAI::animated")

    def test_ingest_preserves_render_provenance_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = os.path.join(tmp, "assets.db")
            index = os.path.join(tmp, "index.json")
            meta = {"tenant": "film_keys", "character_id": "KAI", "style": "animated",
                    "assignment_id": "film_keys::KAI::animated", "scene": 0, "shot": 0,
                    "aspect": "9:16", "workflow": "storyboard:wan2.2_i2v"}
            with open(index, "w", encoding="utf-8") as handle:
                json.dump({"items": [{"key": "asset-1", "name": "clip.mp4", "rel": "X:/clip.mp4",
                                      "size": 12, "mtime": 1, "meta": meta}]}, handle)
            with mock.patch.object(main, "DB_PATH", db), mock.patch.object(main, "INDEX_JSON", index):
                main._init_db()
                self.assertEqual(main.ingest_index(), 1)
                with main._db() as connection:
                    row = dict(connection.execute("SELECT * FROM assets WHERE key='asset-1'").fetchone())
        self.assertEqual(row["tenant"], "film_keys")
        self.assertEqual(row["character_id"], "KAI")
        self.assertEqual(row["style_id"], "animated")
        self.assertEqual(row["scene"], "0")
        self.assertEqual(row["shot"], "0")
        self.assertEqual(row["aspect"], "9:16")

    def test_relative_index_paths_resolve_to_canonical_vault_mounts(self):
        self.assertEqual(main.host_to_container(r"finals\shorts\clip.mp4"),
                         "/data/assets/finals/shorts/clip.mp4")
        self.assertEqual(main.host_to_container(r"reports\_status\agenda_reels\reel.mp4"),
                         "/data/index/agenda_reels/reel.mp4")
        self.assertTrue(main.canonical_host_path(r"finals\clip.mp4").endswith(r"finals\clip.mp4"))
        self.assertIsNone(main.host_to_container(r"..\private\secret.mp4"))

    def test_reindex_prunes_stale_rows_and_reports_servable_catalog(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = os.path.join(tmp, "assets.db")
            index = os.path.join(tmp, "index.json")
            mount = os.path.join(tmp, "mounted-finals")
            host = os.path.join(tmp, "host-finals")
            os.makedirs(mount)
            clip = os.path.join(mount, "clip.mp4")
            with open(clip, "wb") as handle:
                handle.write(b"clip")
            with open(index, "w", encoding="utf-8") as handle:
                json.dump({"items": [{"key": "relative-1", "name": "clip.mp4",
                                      "rel": r"finals\clip.mp4", "size": 4, "mtime": 1}]}, handle)
            relative_map = [("finals", host, mount.replace("\\", "/"), "finals")]
            with mock.patch.object(main, "DB_PATH", db), mock.patch.object(main, "INDEX_JSON", index), \
                    mock.patch.object(main, "_RELATIVE_PATH_MAP", relative_map), \
                    mock.patch.object(main, "SCAN_ROOTS", []):
                main._init_db()
                first = main.reindex()
                with open(index, "w", encoding="utf-8") as handle:
                    json.dump({"items": []}, handle)
                second = main.reindex()
        self.assertTrue(first["catalog"]["ready"])
        self.assertEqual(first["catalog"]["unavailable"], 0)
        self.assertEqual(second["total"], 0)
        self.assertEqual(second["catalog"]["index"]["pruned"], 1)

    def test_cold_archive_pointer_stays_searchable_without_blocking_readiness(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = os.path.join(tmp, "assets.db")
            index = os.path.join(tmp, "index.json")
            mount = os.path.join(tmp, "mounted-finals")
            host = os.path.join(tmp, "host-finals")
            os.makedirs(mount)
            with open(index, "w", encoding="utf-8") as handle:
                json.dump({"items": [{"key": "archived-1", "name": "clip.mp4",
                                      "rel": r"finals\clip.mp4", "archived": True,
                                      "archived_to": r"X:\cold\clip.mp4"}]}, handle)
            relative_map = [("finals", host, mount.replace("\\", "/"), "finals")]
            with mock.patch.object(main, "DB_PATH", db), mock.patch.object(main, "INDEX_JSON", index), \
                    mock.patch.object(main, "_RELATIVE_PATH_MAP", relative_map), \
                    mock.patch.object(main, "SCAN_ROOTS", []):
                main._init_db()
                result = main.reindex()
                listing = main.list_assets(q=None, label=None, ext=None, tenant=None,
                                           character_id=None, style=None, tenant_id=None,
                                           limit=10, offset=0)
        self.assertTrue(result["catalog"]["ready"])
        self.assertEqual(result["catalog"]["unavailable"], 0)
        self.assertEqual(result["catalog"]["index"]["offline_archived"], 1)
        self.assertEqual(listing["assets"][0]["key"], "archived-1")
        self.assertTrue(listing["assets"][0]["archived"])

    def test_supplemental_scan_prunes_files_removed_from_present_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = os.path.join(tmp, "assets.db")
            mount = os.path.join(tmp, "vault")
            host = os.path.join(tmp, "host-vault")
            os.makedirs(mount)
            clip = os.path.join(mount, "clip.mp4")
            with open(clip, "wb") as handle:
                handle.write(b"clip")
            path_map = [(host, mount, "vault")]
            with mock.patch.object(main, "DB_PATH", db), mock.patch.object(main, "SCAN_ROOTS", [mount]), \
                    mock.patch.object(main, "_PATH_MAP", path_map):
                main._init_db()
                main.scan_supplemental()
                os.remove(clip)
                main.scan_supplemental()
                with main._db() as connection:
                    count = connection.execute("SELECT COUNT(*) FROM assets WHERE source='scan'").fetchone()[0]
        self.assertEqual(count, 0)

    def test_asset_listing_keeps_structured_and_legacy_tenant_filters(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = os.path.join(tmp, "assets.db")
            index = os.path.join(tmp, "index.json")
            with open(index, "w", encoding="utf-8") as handle:
                json.dump({"items": [{
                    "key": "asset-1", "name": "clip.mp4", "rel": "X:/film_keys/clip.mp4",
                    "size": 12, "mtime": 1,
                    "meta": {"tenant": "film_keys", "character_id": "KAI", "style": "animated"},
                }]}, handle)
            with mock.patch.object(main, "DB_PATH", db), mock.patch.object(main, "INDEX_JSON", index):
                main._init_db()
                main.ingest_index()
                result = main.list_assets(q=None, label=None, ext=None, tenant="film_keys",
                                          character_id="KAI", style="animated", tenant_id="film_keys",
                                          limit=10, offset=0)
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["assets"][0]["key"], "asset-1")

    def test_neo4j_reset_is_structurally_scoped(self):
        source = inspect.getsource(main.sync_crosswalk_graph)
        self.assertIn('active_label="StudioAssetNode"', source)
        self.assertIn('stage_label="StudioAssetStage"', source)
        self.assertNotIn("MATCH (n) DETACH DELETE n", source)
        clip_source = inspect.getsource(main.sync_clip_graph)
        self.assertIn('active_label="StudioClipNode"', clip_source)
        self.assertIn('stage_label="StudioClipStage"', clip_source)
        self.assertNotIn("MATCH (n) DETACH DELETE n", clip_source)

    def test_neo4j_replacement_stages_then_atomically_switches_labels(self):
        data = {
            "nodes": [{"id": "node:1", "kind": "character"}],
            "edges": [{"eid": "edge:1", "src": "node:1", "dst": "node:1", "kind": "SELF"}],
        }
        calls = []

        def fake_neo4j(statements, timeout=90):
            calls.append((statements, timeout))
            first = statements[0]["statement"]
            if "StudioProjectionState" in first and len(statements) == 3:
                return {"results": [{"data": []}, {"data": [{"row": [0]}]},
                                    {"data": [{"row": [0]}]}], "errors": []}
            if len(statements) == 1 and "RETURN count(n)" in first:
                return {"results": [{"data": [{"row": [0]}]}], "errors": []}
            if len(statements) == 2 and "StudioAssetStage" in first:
                return {"results": [{"data": [{"row": [1]}]},
                                    {"data": [{"row": [1]}]}], "errors": []}
            results = [{} for _ in statements]
            if len(statements) == 6:
                results[-2] = {"data": [{"row": [1]}]}
                results[-1] = {"data": [{"row": [1]}]}
            return {"results": results, "errors": []}

        with mock.patch.object(main, "STUDIO_NEO4J_HTTP", "http://neo4j"), \
                mock.patch.object(main, "_crosswalk", return_value=data), \
                mock.patch.object(main, "_neo4j", side_effect=fake_neo4j):
            result = main.sync_crosswalk_graph()
        self.assertTrue(result["ok"])
        statements = [statement["statement"] for call, _timeout in calls for statement in call]
        self.assertTrue(any("MERGE (n:StudioAssetStage" in statement for statement in statements))
        self.assertTrue(any("REMOVE n:StudioAssetNode SET n:StudioAssetRetired" in statement
                            for statement in statements))
        self.assertFalse(any(statement == "MATCH (n) DETACH DELETE n" for statement in statements))
        switch_call = next((call, timeout) for call, timeout in calls if len(call) == 6)
        self.assertEqual(switch_call[1], 90)

    def test_neo4j_stage_failure_never_relabels_the_active_projection(self):
        data = {"nodes": [{"id": "node:1", "kind": "character"}], "edges": []}
        statements_seen = []

        def fail_during_stage(statements, timeout=90):
            del timeout
            statements_seen.extend(statement["statement"] for statement in statements)
            first = statements[0]["statement"]
            if "StudioProjectionState" in first:
                return {"results": [{"data": []}, {"data": [{"row": [1]}]},
                                    {"data": [{"row": [0]}]}], "errors": []}
            if "RETURN count(n)" in first:
                return {"results": [{"data": [{"row": [0]}]}], "errors": []}
            if "MERGE (n:StudioAssetStage" in first:
                raise RuntimeError("simulated stage failure")
            return {"results": [{} for _ in statements], "errors": []}

        with mock.patch.object(main, "STUDIO_NEO4J_HTTP", "http://neo4j"), \
                mock.patch.object(main, "_crosswalk", return_value=data), \
                mock.patch.object(main, "_neo4j", side_effect=fail_during_stage):
            with self.assertRaises(RuntimeError):
                main.sync_crosswalk_graph()
        self.assertFalse(any("REMOVE n:StudioAssetNode" in statement for statement in statements_seen))

    def test_neo4j_readiness_requires_complete_projection(self):
        data = {"counts": {"nodes": 4, "edges": 7}, "nodes": [], "edges": []}
        response = {"results": [
            {"data": [{"row": [4]}]},
            {"data": [{"row": [6]}]},
        ]}
        with mock.patch.object(main, "STUDIO_NEO4J_HTTP", "http://neo4j"), \
                mock.patch.object(main, "_crosswalk", return_value=data), \
                mock.patch.object(main, "_neo4j", return_value=response):
            status = main.neo4j_projection_status()
        self.assertFalse(status["ready"])
        self.assertEqual(status["expected_edges"], 7)

    def test_clip_projection_readiness_requires_complete_projection(self):
        data = {"counts": {"nodes": 8, "edges": 11}, "nodes": [], "edges": []}
        response = {"results": [
            {"data": [{"row": [8]}]},
            {"data": [{"row": [11]}]},
        ]}
        with mock.patch.object(main, "STUDIO_NEO4J_HTTP", "http://neo4j"), \
                mock.patch.object(main, "_clip_crosswalk", return_value=data), \
                mock.patch.object(main, "_neo4j", return_value=response):
            status = main.clip_projection_status()
        self.assertTrue(status["ready"])

    def test_startup_projection_runs_in_a_daemon_worker(self):
        main._STARTUP_REFRESH.update({"state": "pending", "error": "", "started_at": 0,
                                      "finished_at": 0})
        with mock.patch.object(main, "reindex", return_value={"total": 12}), \
                mock.patch.object(main, "STUDIO_NEO4J_HTTP", "http://neo4j"), \
                mock.patch.object(main, "sync_crosswalk_graph", return_value={"ok": True}), \
                mock.patch.object(main, "sync_clip_graph", return_value={"ok": True}), \
                mock.patch.object(main, "_crosswalk", return_value={"counts": {}}), \
                mock.patch.object(main, "_clip_crosswalk", return_value={"counts": {}}), \
                mock.patch.object(main, "_log_receipt"):
            worker = main._start_startup_refresh()
            worker.join(timeout=2)

        self.assertTrue(worker.daemon)
        self.assertFalse(worker.is_alive())
        self.assertEqual(main._STARTUP_REFRESH["state"], "ready")

    def test_clip_recommendations_filter_semantic_state_and_tracking_role(self):
        data = {"_schema": "studio-clip-learning-v1", "clips": [
            {"id": "one", "emotion": "hope", "role": "coverage",
             "tracking_roles": ["rig_reference"], "semantic_state": "semantic_ready",
             "confidence": 0.9, "rig_reference_score": 0.8, "size": 20},
            {"id": "two", "emotion": "hope", "role": "coverage",
             "tracking_roles": ["rig_reference"], "semantic_state": "needs_description",
             "confidence": 0.2, "rig_reference_score": 0.7, "size": 10},
        ]}
        with mock.patch.object(main, "_clip_crosswalk", return_value=data):
            result = main.clip_recommendations(emotion="hope", role="rig_reference",
                                               project="", state="semantic_ready", limit=24)
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["clips"][0]["id"], "one")

    def test_crosswalk_edges_follow_resolved_fallback_assignment(self):
        assignment = {"id": "film_keys::KAI::animated"}
        edge = {"src": "assignment:film_keys::KAI::animated", "dst": "style:animated"}
        with tempfile.TemporaryDirectory() as tmp:
            db = os.path.join(tmp, "assets.db")
            with mock.patch.object(main, "DB_PATH", db):
                main._init_db()
                with main._db() as connection:
                    main._upsert(connection, {
                        "key": "asset-1", "label": "renders", "name": "clip.mp4", "ext": "mp4",
                        "host_path": "X:/clip.mp4", "container_path": None, "size": 1, "mtime": 1,
                        "thumb_file": None, "archivable": 0, "archived": 0, "source": "index",
                        "tenant": "film_keys", "character_id": "KAI", "style_id": "animated",
                        "assignment_id": "", "scene": "1", "shot": "1", "aspect": "16:9",
                        "workflow": "ltx", "provenance_json": "", "indexed_at": 1,
                    })
                    connection.commit()
                with mock.patch.object(main, "_crosswalk", return_value={"edges": [edge]}), \
                        mock.patch.object(main, "resolve_assignment", return_value=assignment):
                    result = main.get_asset_crosswalk("asset-1")
        self.assertEqual(result["assignment"], assignment)
        self.assertEqual(result["edges"], [edge])

    def test_maintenance_routes_fail_closed_as_503(self):
        with mock.patch.object(security, "REQUIRE_AUTH", False):
            for target, operation in (
                ("sync_crosswalk_graph", main.post_crosswalk_sync),
                ("sync_clip_graph", main.post_clip_sync),
                ("reindex", main.post_reindex),
            ):
                with self.subTest(target=target), mock.patch.object(main, target, side_effect=RuntimeError("down")):
                    response = operation(None)
                    self.assertEqual(response.status_code, 503)

    def test_project_mutations_require_the_shared_owner_dependency(self):
        post_routes = [route for route in project_api.router.routes if "POST" in route.methods]
        self.assertEqual(len(post_routes), 3)
        for route in post_routes:
            dependencies = [dependency.call for dependency in route.dependant.dependencies]
            self.assertIn(security.require_studio_owner, dependencies)

    def test_project_add_uses_writable_overlay_and_preserves_canonical_registry(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "tenant_registry.json"
            overlay = Path(tmp) / "state" / "tenant_registry.json"
            original = {"creative_tenants": [], "counts": {"creative": 0}}
            source.write_text(json.dumps(original), encoding="utf-8")
            with mock.patch.object(project_api, "REGISTRY_SOURCE_PATH", source), \
                    mock.patch.object(project_api, "REGISTRY_PATH", overlay), \
                    mock.patch.object(project_api, "_neo_merge", return_value=True), \
                    mock.patch.object(project_api, "_auth_verify", return_value=True), \
                    mock.patch.object(project_api, "_emit", return_value="job-1"):
                result = project_api.add_project(project_api.AddProjectRequest(
                    id="Film_New", name="New Film", status="in_production"
                ))
                loaded = project_api._load_registry()
            self.assertEqual(json.loads(source.read_text(encoding="utf-8")), original)
            self.assertTrue(overlay.exists())
            self.assertEqual(result["tenant_id"], "film_new")
            self.assertEqual(loaded["creative_tenants"][0]["name"], "New Film")

    def test_project_mutations_reject_invalid_status_and_mismatched_body_id(self):
        with self.assertRaises(project_api.HTTPException) as invalid_status:
            project_api._normalise_status("invented")
        self.assertEqual(invalid_status.exception.status_code, 400)
        with self.assertRaises(project_api.HTTPException) as mismatched:
            project_api._require_matching_id("film_other", "film_keys")
        self.assertEqual(mismatched.exception.status_code, 400)

    def test_maintenance_auth_switch_is_enforced(self):
        with mock.patch.object(security, "REQUIRE_AUTH", True):
            with self.assertRaises(main.HTTPException) as raised:
                main._require_maintenance_auth(None)
        self.assertEqual(raised.exception.status_code, 401)

        with mock.patch.object(security, "REQUIRE_AUTH", False), \
                mock.patch.object(security, "require_claims") as require:
            self.assertIsNone(main._require_maintenance_auth(None))
        require.assert_not_called()

    def test_auth_readiness_proves_service_trust_not_only_reachability(self):
        response = mock.MagicMock()
        response.__enter__.return_value.status = 200
        with mock.patch.object(main.security, "REQUIRE_AUTH", True), \
                mock.patch.object(main.security, "INTERNAL_SERVICE_TOKEN", "shared-secret"), \
                mock.patch.object(main.security, "AUTH_INTROSPECTION_URL", "http://auth/introspect"), \
                mock.patch.object(main.urllib.request, "urlopen", return_value=response) as urlopen:
            status = main.auth_dependency_status()
        request = urlopen.call_args.args[0]
        self.assertTrue(status["ready"])
        self.assertEqual(request.full_url, "http://auth/introspect")
        self.assertEqual(request.get_header("X-service-token"), "shared-secret")
        self.assertEqual(json.loads(request.data), {"token": "studio-assets-readiness-probe"})

    def test_maintenance_auth_requires_owner_scope(self):
        claims = {"sub": "owner", "role": "Owner", "scopes": ["ops:owner"]}
        with mock.patch.object(security, "REQUIRE_AUTH", True), \
                mock.patch.object(security, "require_claims", return_value=claims) as require:
            self.assertEqual(main._require_maintenance_auth("Bearer token"), claims)
        self.assertEqual(require.call_args.kwargs["required_scopes"], {"ops:owner"})


if __name__ == "__main__":
    unittest.main()
