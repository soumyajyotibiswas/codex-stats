from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_usage_data import build_summary, write_outputs

ROOT = Path(__file__).resolve().parents[1]


class BuildUsageDataTests(unittest.TestCase):
    def test_synthetic_fixture_generates_metadata_only_outputs(self) -> None:
        fixture_root = ROOT / "tests" / "fixtures"
        summary = build_summary([("custom", fixture_root)], redact_paths=True)

        self.assertEqual(summary["totals"]["sessions"], 1)
        self.assertEqual(summary["totals"]["turns"], 2)
        self.assertEqual(summary["totals"]["total_tokens"], 450)
        self.assertEqual(summary["totals"]["cached_input_tokens"], 105)
        self.assertTrue(summary["sessions"][0]["memory_citation_detected"])
        self.assertIsNone(summary["sessions"][0]["cwd"])
        self.assertEqual(summary["sessions"][0]["project"], "Project 1")

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            write_outputs(summary, output_dir)
            rendered = "\n".join(path.read_text(encoding="utf-8") for path in output_dir.iterdir())
            self.assertNotIn("SYNTHETIC_PROMPT_TEXT_SHOULD_NOT_APPEAR", rendered)

            summary_json = json.loads((output_dir / "codex_usage_summary.json").read_text(encoding="utf-8"))
            self.assertTrue(summary_json["privacy"]["content_fields_ignored"])

    def test_malformed_records_are_counted_without_breaking_rollups(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            session = root / "rollout-synthetic-2.jsonl"
            session.write_text(
                "\n".join(
                    [
                        '{"timestamp":"2026-05-02T09:00:00Z","type":"session_meta","payload":{"id":"s2","cwd":"/tmp/project-two","model":"gpt-test"}}',
                        '{"timestamp":"2026-05-02T09:01:00Z","type":"turn_context","payload":{}}',
                        '{"timestamp":"2026-05-02T09:02:00Z","type":"response_item","payload":{"info":{"total_token_usage":{"input_tokens":10,"cached_input_tokens":5,"output_tokens":4,"total_tokens":14}}}}',
                        "{not json",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            summary = build_summary([("custom", root)], redact_paths=True)

            self.assertEqual(summary["freshness"]["records_skipped"], 1)
            self.assertEqual(summary["totals"]["total_tokens"], 14)
            self.assertEqual(summary["daily"][0]["cache_ratio"], 0.5)
            self.assertEqual(summary["sessions"][0]["source_root"], "custom:Input root 1")
            self.assertEqual(summary["insights"]["cache_label"], "Moderate context reuse")

    def test_project_names_can_be_kept_without_raw_paths(self) -> None:
        fixture_root = ROOT / "tests" / "fixtures"
        summary = build_summary(
            [("custom", fixture_root)],
            redact_paths=True,
            project_label_mode="name",
        )

        session = summary["sessions"][0]
        self.assertEqual(session["project"], "synthetic-alpha")
        self.assertIsNone(session["cwd"])
        self.assertTrue(summary["privacy"]["redact_paths"])
        self.assertEqual(summary["privacy"]["project_label_mode"], "name")

    def test_sample_data_is_rich_enough_for_portfolio_screenshots(self) -> None:
        sample_root = ROOT / "tests" / "sample_data"
        summary = build_summary(
            [("custom", sample_root)],
            redact_paths=True,
            project_label_mode="name",
        )

        self.assertEqual(summary["totals"]["sessions"], 7)
        self.assertEqual(summary["totals"]["total_tokens"], 337100)
        self.assertGreaterEqual(len(summary["daily"]), 10)
        self.assertGreaterEqual(len(summary["project_breakdown"]), 4)
        self.assertEqual(len(summary["memory_reuse_signals"]["candidates_for_memory_or_skill_creation"]), 2)
        self.assertTrue(summary["privacy"]["content_fields_ignored"])

    def test_daily_usage_uses_token_event_deltas_by_timestamp(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            session = root / "rollout-multi-day.jsonl"
            session.write_text(
                "\n".join(
                    [
                        '{"timestamp":"2026-05-01T09:00:00Z","type":"session_meta","payload":{"id":"multi","cwd":"/tmp/project","model":"gpt-test"}}',
                        '{"timestamp":"2026-05-01T09:01:00Z","type":"response_item","payload":{"info":{"total_token_usage":{"input_tokens":8,"cached_input_tokens":2,"output_tokens":2,"total_tokens":10}}}}',
                        '{"timestamp":"2026-05-02T09:01:00Z","type":"response_item","payload":{"info":{"total_token_usage":{"input_tokens":20,"cached_input_tokens":7,"output_tokens":5,"total_tokens":25}}}}',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            summary = build_summary([("custom", root)], redact_paths=True)
            daily = {row["date"]: row for row in summary["daily"]}

            self.assertEqual(summary["totals"]["total_tokens"], 25)
            self.assertEqual(daily["2026-05-01"]["total_tokens"], 10)
            self.assertEqual(daily["2026-05-02"]["total_tokens"], 15)
            self.assertEqual(daily["2026-05-02"]["input_tokens"], 12)
            self.assertEqual(daily["2026-05-02"]["usage_events"], 1)


if __name__ == "__main__":
    unittest.main()
