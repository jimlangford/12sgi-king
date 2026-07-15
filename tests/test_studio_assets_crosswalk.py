import inspect
import json
import os
import tempfile
import unittest
from unittest import mock

from services.studio_assets.app import main


class StudioAssetCrosswalkTests(unittest.TestCase):
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
                    "assignment_id": "film_keys::KAI::animated", "scene": 1, "shot": 2,
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
        self.assertEqual(row["aspect"], "9:16")

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
        self.assertIn("MATCH (n:StudioAssetNode) DETACH DELETE n", source)
        self.assertNotIn("MATCH (n) DETACH DELETE n", source)
        clip_source = inspect.getsource(main.sync_clip_graph)
        self.assertIn("MATCH (n:StudioClipNode) DETACH DELETE n", clip_source)
        self.assertNotIn("MATCH (n) DETACH DELETE n", clip_source)

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

    def test_maintenance_auth_switch_is_enforced(self):
        with mock.patch.object(main, "REQUIRE_AUTH", True):
            with self.assertRaises(main.HTTPException) as raised:
                main._require_maintenance_auth(None)
        self.assertEqual(raised.exception.status_code, 401)

        with mock.patch.object(main, "REQUIRE_AUTH", False), \
                mock.patch.object(main, "require_claims") as require:
            self.assertIsNone(main._require_maintenance_auth(None))
        require.assert_not_called()

    def test_maintenance_auth_requires_owner_scope(self):
        claims = {"sub": "owner", "role": "Owner", "scopes": ["ops:owner"]}
        with mock.patch.object(main, "REQUIRE_AUTH", True), \
                mock.patch.object(main, "require_claims", return_value=claims) as require:
            self.assertEqual(main._require_maintenance_auth("Bearer token"), claims)
        self.assertEqual(require.call_args.kwargs["required_scopes"], {"ops:owner"})


if __name__ == "__main__":
    unittest.main()
