#!/usr/bin/env python3
"""Audit generated dashboard data for content-like fields."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

DISALLOWED_KEYS = {
    "content",
    "message",
    "input",
    "output",
    "summary",
    "text_elements",
    "last_agent_message",
    "stdout",
    "stderr",
}


def walk_keys(value: Any, found: set[str]) -> None:
    if isinstance(value, dict):
        found.update(str(key) for key in value)
        for item in value.values():
            walk_keys(item, found)
    elif isinstance(value, list):
        for item in value:
            walk_keys(item, found)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit generated JSON for disallowed content-like keys.")
    parser.add_argument("--summary", default="data/generated/codex_usage_summary.json")
    parser.add_argument("--forbid", action="append", default=[], help="Literal string that must not appear.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    path = Path(args.summary)
    if not path.exists():
        raise SystemExit(f"Missing generated summary: {path}")
    text = path.read_text(encoding="utf-8")
    data = json.loads(text)
    found: set[str] = set()
    walk_keys(data, found)
    bad_keys = sorted(DISALLOWED_KEYS & found)
    bad_literals = sorted(item for item in args.forbid if item and item in text)
    if bad_keys or bad_literals:
        print("Privacy audit failed")
        if bad_keys:
            print("  disallowed_keys:", ", ".join(bad_keys))
        if bad_literals:
            print("  forbidden_literals:", ", ".join(bad_literals))
        return 1
    print("Privacy audit passed")
    print("  disallowed_keys: none")
    print("  forbidden_literals: none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
