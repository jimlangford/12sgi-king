import unittest

from services.local_ai_contract import (
    build_handoff_record,
    lane_resolution_policy,
    scorecard_from_cycles,
    validate_task_packet,
)


class LocalAiContractTests(unittest.TestCase):
    def test_validate_task_packet_success(self):
        packet = {
            "packet_id": "p-1",
            "goal": "Update local contract",
            "constraints": ["Do not expose private paths"],
            "boundary_label": "private",
            "expected_output": "Updated docs",
            "verification_target": "unit tests pass",
            "lane": "engineering",
        }

        result = validate_task_packet(packet)
        self.assertTrue(result["ok"])
        self.assertEqual(result["normalized"]["boundary_label"], "PRIVATE")

    def test_validate_task_packet_missing_fields(self):
        result = validate_task_packet({"goal": "x"})
        self.assertFalse(result["ok"])
        self.assertGreaterEqual(len(result["errors"]), 1)

    def test_lane_policy_engineering_auto_resolve(self):
        policy = lane_resolution_policy(
            {"lane": "engineering"},
            confidence=0.9,
            visibility="full",
        )
        self.assertTrue(policy["auto_resolve"])
        self.assertEqual(policy["decision"], "auto-resolve")

    def test_lane_policy_creative_owner_review(self):
        policy = lane_resolution_policy(
            {"lane": "creative"},
            confidence=0.95,
            visibility="full",
        )
        self.assertFalse(policy["auto_resolve"])
        self.assertTrue(policy["approval_required"])
        self.assertEqual(policy["decision"], "owner-review")

    def test_scorecard_metrics(self):
        records = [
            build_handoff_record(
                task_packet={"packet_id": "p1", "lane": "engineering"},
                context_in={"source": "a"},
                decision_request={"clarification_count": 1},
                execution_result={
                    "outcome": "completed",
                    "started_at": "2026-07-14T00:00:00+00:00",
                    "completed_at": "2026-07-14T00:01:00+00:00",
                },
                verification_result={"approval_status": "approved"},
                next_action={"requires_rework": False},
            ),
            build_handoff_record(
                task_packet={"packet_id": "p2", "lane": "creative"},
                context_in={"source": "b"},
                decision_request={"clarification_count": 0},
                execution_result={
                    "outcome": "rework",
                    "started_at": "2026-07-14T00:00:00+00:00",
                    "completed_at": "2026-07-14T00:03:00+00:00",
                },
                verification_result={"approval_status": "approved"},
                next_action={"requires_rework": True},
            ),
        ]

        scorecard = scorecard_from_cycles(records)
        self.assertEqual(scorecard["tasks_total"], 2)
        self.assertEqual(scorecard["rework_count"], 1)
        self.assertEqual(scorecard["clarification_count"], 1)
        self.assertEqual(scorecard["approval_pass_rate"], 1.0)
        self.assertEqual(scorecard["avg_turnaround_seconds"], 120.0)


if __name__ == "__main__":
    unittest.main()
