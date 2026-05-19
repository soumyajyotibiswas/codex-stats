#!/usr/bin/env python3
"""Print or install local dashboard refresh schedules."""

from __future__ import annotations

import argparse
import platform
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER_START = "# codex-usage-dashboard:start"
MARKER_END = "# codex-usage-dashboard:end"


def posix_command() -> str:
    return f"cd {shlex.quote(str(ROOT))} && {shlex.quote(sys.executable)} install.py --real"


def cron_block(hours: list[int]) -> str:
    hour_expr = ",".join(str(hour) for hour in sorted(set(hours)))
    command = posix_command() + f" >> {shlex.quote(str(ROOT / '.local' / 'scheduler.log'))} 2>&1"
    return f"{MARKER_START}\n0 {hour_expr} * * * {command}\n{MARKER_END}"


def launchd_plist(hours: list[int]) -> str:
    start_calendar = "\n".join(
        f"""    <dict>
      <key>Hour</key>
      <integer>{hour}</integer>
      <key>Minute</key>
      <integer>0</integer>
    </dict>"""
        for hour in sorted(set(hours))
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>local.codex-usage-dashboard.refresh</string>
  <key>ProgramArguments</key>
  <array>
    <string>{sys.executable}</string>
    <string>{ROOT / "install.py"}</string>
    <string>--real</string>
  </array>
  <key>WorkingDirectory</key>
  <string>{ROOT}</string>
  <key>StartCalendarInterval</key>
  <array>
{start_calendar}
  </array>
  <key>StandardOutPath</key>
  <string>{ROOT / ".local" / "scheduler.log"}</string>
  <key>StandardErrorPath</key>
  <string>{ROOT / ".local" / "scheduler.log"}</string>
</dict>
</plist>"""


def windows_commands(hours: list[int]) -> str:
    rows = []
    for hour in sorted(set(hours)):
        task_name = f"CodexUsageDashboardRefresh{hour:02d}00"
        rows.append(
            "schtasks /Create /F "
            f"/TN {task_name} "
            "/SC DAILY "
            f"/ST {hour:02d}:00 "
            f'/TR "\\"{sys.executable}\\" \\"{ROOT / "install.py"}\\" --real"'
        )
    return "\n".join(rows)


def install_cron(hours: list[int]) -> None:
    crontab = shutil.which("crontab")
    if not crontab:
        raise SystemExit("Could not find crontab on this system.")
    block = cron_block(hours)
    existing = subprocess.run([crontab, "-l"], capture_output=True, text=True, check=False)
    current = existing.stdout if existing.returncode == 0 else ""
    lines = current.splitlines()
    cleaned: list[str] = []
    skipping = False
    for line in lines:
        if line.strip() == MARKER_START:
            skipping = True
            continue
        if line.strip() == MARKER_END:
            skipping = False
            continue
        if not skipping:
            cleaned.append(line)
    updated = "\n".join([line for line in cleaned if line.strip()] + [block]) + "\n"
    subprocess.run([crontab, "-"], input=updated, text=True, check=True)
    print("Installed cron refresh schedule.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manage scheduled dashboard refresh commands.")
    parser.add_argument("--hours", default="8,20", help="Comma-separated local hours, 0-23.")
    parser.add_argument(
        "--target",
        choices=["auto", "cron", "launchd", "windows"],
        default="auto",
        help="Scheduler format to print or install.",
    )
    parser.add_argument("--install-cron", action="store_true", help="Install/update the cron schedule.")
    parser.add_argument("--yes", action="store_true", help="Required with --install-cron.")
    return parser.parse_args()


def parse_hours(value: str) -> list[int]:
    hours = [int(item.strip()) for item in value.split(",") if item.strip()]
    bad = [hour for hour in hours if hour < 0 or hour > 23]
    if bad:
        raise SystemExit(f"Invalid hour(s): {bad}")
    return hours or [8, 20]


def resolved_target(target: str) -> str:
    if target != "auto":
        return target
    system = platform.system().lower()
    if system == "darwin":
        return "cron"
    if system == "windows":
        return "windows"
    return "cron"


def main() -> int:
    args = parse_args()
    hours = parse_hours(args.hours)
    target = resolved_target(args.target)
    if args.install_cron:
        if not args.yes:
            raise SystemExit("Refusing to modify crontab without --yes.")
        install_cron(hours)
        return 0
    if target == "cron":
        print(cron_block(hours))
    elif target == "launchd":
        print(launchd_plist(hours))
    else:
        print(windows_commands(hours))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
