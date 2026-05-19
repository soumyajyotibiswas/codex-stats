#!/usr/bin/env python3
"""Serve the static dashboard on localhost with Python standard library only."""

from __future__ import annotations

import argparse
import http.server
import ipaddress
import json
import secrets
import socketserver
import subprocess
import sys
import threading
from http import HTTPStatus
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
ALLOWED_STATIC_PREFIXES = ("/web/", "/data/generated/")
MAX_API_BODY_BYTES = 4096
HELP_COMMANDS = {
    "install.py": [sys.executable, "install.py", "--help"],
    "scripts/build_usage_data.py": [sys.executable, "scripts/build_usage_data.py", "--help"],
    "scripts/schedule_dashboard.py": [sys.executable, "scripts/schedule_dashboard.py", "--help"],
    "scripts/privacy_audit.py": [sys.executable, "scripts/privacy_audit.py", "--help"],
}


class DashboardRequestHandler(http.server.SimpleHTTPRequestHandler):
    server: DashboardServer

    def __init__(self, request: Any, client_address: Any, server: Any) -> None:
        super().__init__(request, client_address, server, directory=str(ROOT))

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            self.handle_api("GET", parsed.path, parse_qs(parsed.query))
            return
        if parsed.path in ("", "/"):
            self.send_response(HTTPStatus.FOUND)
            self.send_header("Location", "/web/index.html")
            self.end_headers()
            return
        if not self.static_path_allowed(parsed.path):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        self.path = parsed.path
        super().do_GET()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            if self.request_body_too_large():
                self.write_json(
                    {"ok": False, "error": "request_too_large"}, HTTPStatus.REQUEST_ENTITY_TOO_LARGE
                )
                return
            self.handle_api("POST", parsed.path, parse_qs(parsed.query))
            return
        self.send_error(HTTPStatus.METHOD_NOT_ALLOWED)

    def list_directory(self, _path: str) -> None:
        self.send_error(HTTPStatus.NOT_FOUND)

    def end_headers(self) -> None:
        csp = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "connect-src 'self'; "
            "img-src 'self' data:; "
            "base-uri 'none'; "
            "frame-ancestors 'none'"
        )
        self.send_header("Content-Security-Policy", csp)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        if self.path.startswith("/data/generated/"):
            self.send_header("Cache-Control", "no-store")
        else:
            self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def static_path_allowed(self, path: str) -> bool:
        return self.resolve_static_path(path) is not None

    def translate_path(self, path: str) -> str:
        resolved = self.resolve_static_path(urlparse(path).path)
        return str(resolved if resolved else ROOT / "__not_found__")

    def resolve_static_path(self, path: str) -> Path | None:
        decoded = unquote(path)
        for prefix in ALLOWED_STATIC_PREFIXES:
            if not decoded.startswith(prefix):
                continue
            base = (ROOT / prefix.strip("/")).resolve()
            relative = decoded[len(prefix) :]
            parts = [part for part in relative.split("/") if part]
            if not parts or any(part in (".", "..") or part.startswith(".") for part in parts):
                return None
            candidate = (base / Path(*parts)).resolve()
            try:
                candidate.relative_to(base)
            except ValueError:
                return None
            return candidate
        return None

    def token_valid(self, query: dict[str, list[str]]) -> bool:
        if not self.server.auth_token:
            return True
        provided = self.headers.get("X-Dashboard-Token") or (query.get("token") or [""])[0]
        return secrets.compare_digest(provided, self.server.auth_token)

    def request_body_too_large(self) -> bool:
        length = self.headers.get("Content-Length")
        if not length:
            return False
        try:
            return int(length) > MAX_API_BODY_BYTES
        except ValueError:
            return True

    def handle_api(self, method: str, path: str, query: dict[str, list[str]]) -> None:
        if path in ("/api/status", "/api/help"):
            if not self.token_valid(query):
                self.write_json({"ok": False, "error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
                return
            if path == "/api/status":
                self.write_json(
                    {
                        "ok": True,
                        "auto_shutdown": self.server.auto_shutdown,
                        "server": "Codex Usage Dashboard",
                    }
                )
            else:
                self.write_json({"ok": True, "help": collect_help()})
            return

        if method != "POST":
            self.write_json({"ok": False, "error": "method_not_allowed"}, HTTPStatus.METHOD_NOT_ALLOWED)
            return
        if not self.token_valid(query):
            self.write_json({"ok": False, "error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
            return
        if path == "/api/refresh":
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/build_usage_data.py",
                    "--output-dir",
                    "data/generated",
                    "--redact-paths",
                    *(["--project-names"] if self.server.project_names else []),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.write_json(
                {
                    "ok": result.returncode == 0,
                    "returncode": result.returncode,
                    "stdout": result.stdout[-4000:],
                    "stderr": result.stderr[-4000:],
                },
                HTTPStatus.OK if result.returncode == 0 else HTTPStatus.INTERNAL_SERVER_ERROR,
            )
            return
        if path == "/api/page-opened":
            self.server.cancel_shutdown_timer()
            self.write_json({"ok": True})
            return
        if path == "/api/page-closed":
            if self.server.auto_shutdown:
                self.server.schedule_shutdown()
            self.write_json({"ok": True, "scheduled_shutdown": self.server.auto_shutdown})
            return
        if path == "/api/shutdown":
            self.write_json({"ok": True, "scheduled_shutdown": True})
            self.server.schedule_shutdown(delay=0.2)
            return
        self.write_json({"ok": False, "error": "not_found"}, HTTPStatus.NOT_FOUND)

    def write_json(self, payload: dict[str, object], status: HTTPStatus = HTTPStatus.OK) -> None:
        encoded = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


class DashboardServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(
        self,
        server_address: tuple[str, int],
        handler_class: type[DashboardRequestHandler],
        auth_token: str | None = None,
        auto_shutdown: bool = False,
        shutdown_grace_seconds: float = 2.0,
        project_names: bool = False,
    ) -> None:
        super().__init__(server_address, handler_class)
        self.auth_token = auth_token
        self.auto_shutdown = auto_shutdown
        self.shutdown_grace_seconds = shutdown_grace_seconds
        self.project_names = project_names
        self._shutdown_timer: threading.Timer | None = None

    def schedule_shutdown(self, delay: float | None = None) -> None:
        self.cancel_shutdown_timer()
        timer = threading.Timer(delay if delay is not None else self.shutdown_grace_seconds, self.shutdown)
        timer.daemon = True
        self._shutdown_timer = timer
        timer.start()

    def cancel_shutdown_timer(self) -> None:
        if self._shutdown_timer:
            self._shutdown_timer.cancel()
            self._shutdown_timer = None


def collect_help() -> dict[str, str]:
    help_text: dict[str, str] = {}
    for name, command in HELP_COMMANDS.items():
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
        text = result.stdout if result.returncode == 0 else result.stderr
        help_text[name] = text[-12000:]
    return help_text


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve the Codex usage dashboard locally.")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument(
        "--allow-non-loopback",
        action="store_true",
        help="Allow binding outside localhost. Not recommended for normal use.",
    )
    parser.add_argument("--auth-token", default="", help="Optional token required for local API calls.")
    parser.add_argument(
        "--auto-shutdown", action="store_true", help="Shutdown after the dashboard page closes."
    )
    parser.add_argument("--shutdown-grace-seconds", type=float, default=2.0)
    parser.add_argument("--project-names", action="store_true", help="Refresh with basename project labels.")
    return parser.parse_args()


def is_loopback_host(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def main() -> int:
    args = parse_args()
    if not args.allow_non_loopback and not is_loopback_host(args.host):
        raise SystemExit("Refusing to bind outside localhost without --allow-non-loopback.")
    with DashboardServer(
        (args.host, args.port),
        DashboardRequestHandler,
        auth_token=args.auth_token,
        auto_shutdown=args.auto_shutdown,
        shutdown_grace_seconds=args.shutdown_grace_seconds,
        project_names=args.project_names,
    ) as httpd:
        print(f"Serving Codex Usage Dashboard at http://{args.host}:{args.port}/web/index.html", flush=True)
        httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
