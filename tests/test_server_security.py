from __future__ import annotations

import unittest

from scripts.serve_dashboard import ROOT, DashboardRequestHandler, is_loopback_host


class ServerSecurityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.handler = object.__new__(DashboardRequestHandler)

    def test_allows_dashboard_static_files(self) -> None:
        resolved = self.handler.resolve_static_path("/web/index.html")

        self.assertEqual(resolved, (ROOT / "web" / "index.html").resolve())

    def test_allows_generated_data_files(self) -> None:
        resolved = self.handler.resolve_static_path("/data/generated/codex_usage_summary.js")

        self.assertEqual(resolved, (ROOT / "data" / "generated" / "codex_usage_summary.js").resolve())

    def test_blocks_traversal_and_hidden_paths(self) -> None:
        self.assertIsNone(self.handler.resolve_static_path("/web/%2e%2e/install.py"))
        self.assertIsNone(self.handler.resolve_static_path("/web/.secret"))
        self.assertIsNone(self.handler.resolve_static_path("/.local/server.json"))

    def test_loopback_host_validation(self) -> None:
        self.assertTrue(is_loopback_host("127.0.0.1"))
        self.assertTrue(is_loopback_host("::1"))
        self.assertTrue(is_loopback_host("localhost"))
        self.assertFalse(is_loopback_host("0.0.0.0"))


if __name__ == "__main__":
    unittest.main()
