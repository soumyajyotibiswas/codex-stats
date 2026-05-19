#!/usr/bin/env python3
"""Cross-platform local setup helper for the Codex Usage Dashboard."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
DEFAULT_PORT = 8765
STATE_DIR = ROOT / ".local"
SERVER_STATE_FILE = STATE_DIR / "server.json"
SERVER_LOG_FILE = STATE_DIR / "server.log"
SERVER_URL_PATH = "/web/index.html"


def run(cmd: list[str]) -> None:
    print("+ " + " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=ROOT, check=True)


def build_parser_command(args: argparse.Namespace) -> list[str]:
    cmd = [sys.executable, "scripts/build_usage_data.py", "--output-dir", "data/generated"]
    if args.mode == "sample":
        cmd.extend(["--input-root", "tests/sample_data"])
    for source in args.source or []:
        cmd.extend(["--source", source])
    if args.no_redact_paths:
        cmd.append("--no-redact-paths")
    else:
        cmd.append("--redact-paths")
    if args.project_names:
        cmd.append("--project-names")
    if args.dry_run:
        cmd.append("--dry-run")
    return cmd


def server_url(port: int, token: str | None = None) -> str:
    suffix = f"?token={token}" if token else ""
    return f"http://127.0.0.1:{port}{SERVER_URL_PATH}{suffix}"


def is_port_open(port: int) -> bool | None:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except PermissionError:
        return None
    except OSError:
        return False


def read_server_state() -> dict[str, Any] | None:
    if not SERVER_STATE_FILE.exists():
        return None
    try:
        return json.loads(SERVER_STATE_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def write_server_state(pid: int, port: int, token: str | None = None, quickstart: bool = False) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    SERVER_STATE_FILE.write_text(
        json.dumps(
            {
                "pid": pid,
                "port": port,
                "url": server_url(port),
                "quickstart": quickstart,
                "auth_token_present": bool(token),
                "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "log_file": str(SERVER_LOG_FILE),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def pid_is_running(pid: int) -> bool | None:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except PermissionError:
        return None
    except OSError:
        return False


def start_server(
    port: int,
    auth_token: str | None = None,
    auto_shutdown: bool = False,
    open_browser: bool = False,
    project_names: bool = False,
) -> None:
    existing = read_server_state()
    if existing:
        pid = int(existing.get("pid") or 0)
        existing_port = int(existing.get("port") or port)
        port_open = is_port_open(existing_port)
        pid_running = pid_is_running(pid)
        if pid_running is not False and port_open is not False:
            print(f"Server already running at {server_url(existing_port)}")
            print(f"Stop it with: {sys.executable} install.py --stop-server")
            return

    if is_port_open(port) is True:
        raise SystemExit(f"Port {port} is already in use. Choose another port with --port.")

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    log_handle = SERVER_LOG_FILE.open("a", encoding="utf-8")
    cmd = [sys.executable, "scripts/serve_dashboard.py", "--port", str(port)]
    if auth_token:
        cmd.extend(["--auth-token", auth_token])
    if auto_shutdown:
        cmd.append("--auto-shutdown")
    if project_names:
        cmd.append("--project-names")
    if os.name == "nt":
        creation_flags = int(getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)) | int(
            getattr(subprocess, "DETACHED_PROCESS", 0)
        )
        process = subprocess.Popen(
            cmd,
            cwd=ROOT,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            creationflags=creation_flags,
        )
    else:
        process = subprocess.Popen(
            cmd,
            cwd=ROOT,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
    time.sleep(0.8)
    if process.poll() is not None:
        raise SystemExit(f"Server failed to start. See {SERVER_LOG_FILE}")
    write_server_state(process.pid, port, token=auth_token, quickstart=auto_shutdown)
    url = server_url(port, auth_token)
    print(f"Server started at {url}")
    print(f"PID {process.pid}; log {SERVER_LOG_FILE}")
    print(f"Stop it with: {sys.executable} install.py --stop-server")
    if open_browser:
        webbrowser.open(url)


def stop_server() -> None:
    state = read_server_state()
    if not state:
        print("No server state file found.")
        return
    pid = int(state.get("pid") or 0)
    pid_running = pid_is_running(pid)
    if pid_running is False:
        SERVER_STATE_FILE.unlink(missing_ok=True)
        print("No running dashboard server found; stale state removed.")
        return

    if os.name == "nt":
        taskkill = shutil.which("taskkill")
        if not taskkill:
            raise SystemExit("Could not find taskkill to stop the dashboard server.")
        subprocess.run([taskkill, "/PID", str(pid), "/T", "/F"], check=False)
    else:
        os.kill(pid, signal.SIGTERM)
        deadline = time.time() + 5
        while time.time() < deadline and pid_is_running(pid):
            time.sleep(0.2)
        if pid_is_running(pid):
            os.kill(pid, signal.SIGKILL)
    SERVER_STATE_FILE.unlink(missing_ok=True)
    print(f"Stopped dashboard server PID {pid}.")


def server_status() -> None:
    state = read_server_state()
    if not state:
        print("Server status: stopped")
        return
    pid = int(state.get("pid") or 0)
    port = int(state.get("port") or DEFAULT_PORT)
    pid_running = pid_is_running(pid)
    port_open = is_port_open(port)
    running = pid_running is not False and port_open is not False
    if running and (port_open is None or pid_running is None):
        status = "running (verification limited)"
    else:
        status = "running" if running else "stale"
    print(f"Server status: {status}")
    print(f"  pid: {pid}")
    print(f"  url: {server_url(port)}")
    print(f"  log: {SERVER_LOG_FILE}")


def serve_foreground(port: int) -> None:
    run([sys.executable, "scripts/serve_dashboard.py", "--port", str(port)])


def quickstart(args: argparse.Namespace) -> None:
    args.mode = "real"
    run(build_parser_command(args))
    token = secrets.token_urlsafe(24)
    start_server(
        port=args.port,
        auth_token=token,
        auto_shutdown=True,
        open_browser=True,
        project_names=args.project_names,
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build, serve, and manage the local dashboard.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--sample", dest="mode", action="store_const", const="sample", help="Build sample data."
    )
    mode.add_argument(
        "--real", dest="mode", action="store_const", const="real", help="Build real local data."
    )
    parser.add_argument(
        "--quickstart",
        action="store_true",
        help="Build live data, start a tokenized local server, and open the dashboard.",
    )
    parser.add_argument("--serve", action="store_true", help="Serve in the foreground after building.")
    parser.add_argument("--start-server", action="store_true", help="Start a background local server.")
    parser.add_argument("--stop-server", action="store_true", help="Stop the background local server.")
    parser.add_argument("--server-status", action="store_true", help="Show background server status.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Local server port.")
    parser.add_argument(
        "--source", action="append", default=[], help="Pass-through source for data generation."
    )
    parser.add_argument(
        "--project-names",
        action="store_true",
        help="Show basename project names while keeping raw paths redacted.",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Inspect and summarize without writing outputs."
    )
    parser.add_argument(
        "--no-redact-paths",
        action="store_true",
        help="Keep raw local paths and session IDs in generated data. Redaction is on by default.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if args.stop_server:
        stop_server()
        return 0
    if args.server_status:
        server_status()
        return 0
    if args.quickstart:
        quickstart(args)
        return 0

    if args.mode:
        run(build_parser_command(args))
    elif not args.start_server:
        raise SystemExit("Choose --sample, --real, --start-server, --stop-server, or --server-status.")

    if args.start_server and not args.dry_run:
        start_server(args.port, project_names=args.project_names)
    elif args.serve and not args.dry_run:
        serve_foreground(args.port)
    elif args.mode and not args.dry_run:
        print("Dashboard data generated. Open web/index.html or run with --serve.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
