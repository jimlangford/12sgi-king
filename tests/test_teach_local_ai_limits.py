import json
import unittest
from pathlib import Path

from tools import claude_code_bridge, teach_local_ai

ROOT = Path(__file__).resolve().parents[1]


class TeachLocalAiLimitTests(unittest.TestCase):
    def test_claude_instruction_limit_matches_runtime_contract(self):
        registry = json.loads(
            (ROOT / "config" / "ai_tool_registry.v2.json").read_text(encoding="utf-8")
        )
        review_tool = next(
            tool for tool in registry if tool["tool_id"] == "claude_code.review"
        )
        schema_limit = review_tool["arguments_schema"]["properties"]["task"]["maxLength"]

        self.assertEqual(teach_local_ai.CLAUDE_TASK_MIN_CHARS, 12)
        self.assertEqual(teach_local_ai.CLAUDE_TASK_MAX_CHARS, schema_limit)
        self.assertEqual(teach_local_ai.CLAUDE_TASK_MAX_CHARS, claude_code_bridge.MAX_TASK_CHARS)

    def test_training_prompt_teaches_fail_closed_size_boundary(self):
        prompt = teach_local_ai.SYSTEM_KNOWLEDGE

        self.assertIn("must contain 12 to 4000 characters", prompt)
        self.assertIn("split a larger request before dispatch", prompt)
        self.assertNotIn("__CLAUDE_TASK_MAX_CHARS__", prompt)


if __name__ == "__main__":
    unittest.main()
