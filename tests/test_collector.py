import json
import tempfile
import unittest
from pathlib import Path

import collector


class CollectorSmokeTests(unittest.TestCase):
    def test_run_collection_writes_jsonl_and_stats_from_sample_session_and_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output_dir = root / "out"
            logs_dir = root / "logs"
            sessions_dir = root / "sessions"
            logs_dir.mkdir(parents=True)
            sessions_dir.mkdir(parents=True)

            (logs_dir / "gateway.log").write_text(
                "INFO tool_call browser_navigate result success opened example.com and returned a detailed preview for the operator to review immediately.\n",
                encoding="utf-8",
            )
            (sessions_dir / "session_1.json").write_text(
                json.dumps(
                    {
                        "messages": [
                            {"role": "user", "content": "Check the site and report back"},
                            {
                                "role": "assistant",
                                "content": "I checked the site and used the browser tool.",
                                "tool_calls": [
                                    {"function": {"name": "browser_navigate"}},
                                    {"function": {"name": "browser_snapshot"}},
                                ],
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )

            old_output = collector.OUTPUT_DIR
            old_logs = collector.LOG_DIRS
            old_sessions = collector.SESSION_DIRS
            try:
                collector.OUTPUT_DIR = output_dir
                collector.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
                collector.LOG_DIRS = [logs_dir]
                collector.SESSION_DIRS = [sessions_dir]

                stats = collector.run_collection()
            finally:
                collector.OUTPUT_DIR = old_output
                collector.LOG_DIRS = old_logs
                collector.SESSION_DIRS = old_sessions

            output_file = output_dir / "agent_interactions.jsonl"
            stats_file = output_dir / "collection_stats.json"
            self.assertTrue(output_file.exists())
            self.assertTrue(stats_file.exists())

            examples = [json.loads(line) for line in output_file.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(stats["total_interactions_found"], 1)
            self.assertEqual(stats["unique_training_examples"], 1)
            self.assertEqual(len(examples), 1)
            self.assertTrue(any(example["source"] == "gateway.log" for example in examples))
            self.assertTrue(all("messages" in example for example in examples))


if __name__ == "__main__":
    unittest.main()
