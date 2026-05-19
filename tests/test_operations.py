from __future__ import annotations

import unittest

import install
from scripts import schedule_dashboard


class OperationsTests(unittest.TestCase):
    def test_install_build_command_uses_sample_data(self) -> None:
        args = install.parse_args(["--sample", "--dry-run"])
        command = install.build_parser_command(args)

        self.assertIn("--input-root", command)
        self.assertIn("tests/sample_data", command)
        self.assertIn("--redact-paths", command)

    def test_cron_block_is_marker_wrapped_and_local(self) -> None:
        block = schedule_dashboard.cron_block([8, 20])

        self.assertIn(schedule_dashboard.MARKER_START, block)
        self.assertIn(schedule_dashboard.MARKER_END, block)
        self.assertIn("install.py --real", block)
        self.assertIn(".local", block)

    def test_windows_commands_include_one_task_per_hour(self) -> None:
        commands = schedule_dashboard.windows_commands([8, 20])

        self.assertIn("CodexUsageDashboardRefresh0800", commands)
        self.assertIn("CodexUsageDashboardRefresh2000", commands)
        self.assertEqual(commands.count("schtasks /Create"), 2)


if __name__ == "__main__":
    unittest.main()
