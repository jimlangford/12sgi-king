import sys
import unittest
from pathlib import Path

ROOT = Path('/home/runner/work/12sgi-king/12sgi-king')
sys.path.insert(0, str(ROOT))

from watchers import private_spine


class TestPrivateSpine(unittest.TestCase):
    def test_load_skill_catalog_covers_all_patterns(self):
        catalog = private_spine.load_skill_catalog()
        skill_ids = {row["id"] for row in catalog}
        self.assertEqual(skill_ids, set(private_spine.SKILL_PATTERNS.keys()))
        self.assertEqual(len(skill_ids), 17)

    def test_classify_skills_matches_multiple_areas(self):
        hits = private_spine.classify_skills(
            "GPU VRAM thrash during civic ingest handoff and self-heal redirect"
        )
        self.assertIn("gpu_orchestration", hits)
        self.assertIn("civic_ingest", hits)
        self.assertIn("self_heal", hits)

    def test_publish_ready_requires_approval_and_lineage(self):
        creative = {
            "kind": "job",
            "lane": "creative",
            "status": "queued",
            "iso": "2026-07-10 00:00:00",
            "job": {
                "id": "job-1",
                "action": "hina-balance",
                "payload": {
                    "offering_date": "2026-07-09",
                    "hina_node_id": 12,
                    "civic_source": "maui-council/2026-07-09/item-1",
                    "akua": "Kāne",
                    "wa_phase": "Pō",
                    "particles": "mist",
                    "output_types": ["cut-scene", "card-render"],
                },
            },
        }
        approved = {
            "kind": "tombstone",
            "status": "approved",
            "source": "owner",
            "job": {"id": "approval-1", "correlation_id": "job-1", "action": "approved", "payload": {}},
        }
        ready = private_spine.publish_ready_jobs([creative, approved])
        self.assertEqual([row["job"]["id"] for row in ready], ["job-1"])

    def test_publish_ready_rejects_missing_lineage(self):
        output = {
            "kind": "job",
            "lane": "output",
            "status": "queued",
            "job": {"id": "job-2", "action": "publish.staged", "payload": {}},
        }
        approved = {
            "kind": "tombstone",
            "status": "approved",
            "job": {"id": "approval-2", "correlation_id": "job-2", "action": "approved", "payload": {}},
        }
        self.assertEqual(private_spine.publish_ready_jobs([output, approved]), [])

    def test_build_private_spine_links_skills_jobs_and_artifacts(self):
        dispatch_entries = [
            {
                "id": "evt-1",
                "event": "POLICY: GPU VRAM lock",
                "instruction": "self-heal gpu queue",
                "source": "owner",
                "target_thread": "workboard-quad-os",
            }
        ]
        workboard_entries = [
            {
                "kind": "job",
                "lane": "creative",
                "status": "queued",
                "source": "civic-v2-catchup",
                "event": "HINA Pō balance",
                "iso": "2026-07-10 00:00:00",
                "target_thread": "workboard-quad-os",
                "job": {
                    "id": "job-3",
                    "action": "hina-balance",
                    "payload": {
                        "offering_date": "2026-07-09",
                        "hina_node_id": 9,
                        "akua": "Lono",
                        "wa_phase": "Pō",
                        "particles": "rain",
                        "civic_source": "maui-council/2026-07-09/item-3",
                        "output_types": ["cut-scene"],
                    },
                },
            },
            {
                "kind": "tombstone",
                "status": "approved",
                "source": "owner",
                "iso": "2026-07-10 01:00:00",
                "job": {"id": "approval-3", "correlation_id": "job-3", "action": "approved", "payload": {}},
            },
        ]
        built = private_spine.build_private_spine(dispatch_entries, workboard_entries)
        node_ids = {row["id"] for row in built["nodes"]}
        self.assertIn(private_spine.EDGE_CONTEXT_ID, node_ids)
        self.assertIn(private_spine.APEX_CONTEXT_ID, node_ids)
        self.assertIn(private_spine.RHYTHM_CONTEXT_ID, node_ids)
        self.assertIn("quadrant:game", node_ids)
        self.assertIn("thread:workboard-quad-os", node_ids)
        self.assertIn("skill:gpu_orchestration", node_ids)
        self.assertIn("evt-1", node_ids)
        self.assertIn("job:job-3", node_ids)
        self.assertIn("artifact:cut-scene:job-3", node_ids)
        self.assertIn("source:maui-council-2026-07-09-item-3", node_ids)
        self.assertIn("sage-node:9", node_ids)
        self.assertIn("job-3", built["publish_ready_ids"])
        self.assertIn("TOUCHES_SKILL", built["edges"])
        self.assertIn("HAS_ARTIFACT", built["edges"])
        self.assertIn("PUBLISH_READY", built["edges"])
        self.assertIn("CONTAINS", built["edges"])
        self.assertIn("GOVERNS", built["edges"])
        self.assertIn("FRAMES", built["edges"])
        self.assertIn("ROUTES_TO_THREAD", built["edges"])
        self.assertIn("BALANCES_THROUGH", built["edges"])


if __name__ == "__main__":
    unittest.main()
