#!/usr/bin/env python3
"""Build local Codex usage data from metadata-only JSONL parsing."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
DEFAULT_ROOTS = (
    Path.home() / ".codex" / "sessions",
    Path.home() / ".codex" / "archived_sessions",
)
SOURCE_REGISTRY = {
    "codex": {
        "description": "Codex JSONL session logs with token metadata.",
        "roots": DEFAULT_ROOTS,
        "enabled_by_default": True,
        "status": "supported",
    },
    "claude": {
        "description": "Claude Code local JSONL project logs, if present. Opt-in because schemas can vary.",
        "roots": (Path.home() / ".claude" / "projects",),
        "enabled_by_default": False,
        "status": "experimental",
    },
    "gemini": {
        "description": "Gemini CLI local JSONL logs, if present. Opt-in because schemas can vary.",
        "roots": (Path.home() / ".gemini",),
        "enabled_by_default": False,
        "status": "experimental",
    },
    "chatgpt": {
        "description": "ChatGPT desktop does not expose a stable metadata-only JSONL root here.",
        "roots": (),
        "enabled_by_default": False,
        "status": "manual-root-required",
    },
}
GENERATED_FILES = {
    "summary_json": "codex_usage_summary.json",
    "summary_js": "codex_usage_summary.js",
    "daily_csv": "codex_usage_daily.csv",
    "sessions_csv": "codex_usage_sessions.csv",
}
TOKEN_KEYS = ("input_tokens", "cached_input_tokens", "output_tokens", "total_tokens")


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def safe_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str) and value.strip().isdigit():
        return int(value)
    return 0


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def parse_dt(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    candidate = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(candidate)
    except ValueError:
        return None


def max_iso(current: str | None, candidate: str | None) -> str | None:
    if not candidate:
        return current
    if not current:
        return candidate
    current_dt = parse_dt(current)
    candidate_dt = parse_dt(candidate)
    if current_dt and candidate_dt:
        return candidate if candidate_dt >= current_dt else current
    return max(current, candidate)


def min_iso(current: str | None, candidate: str | None) -> str | None:
    if not candidate:
        return current
    if not current:
        return candidate
    current_dt = parse_dt(current)
    candidate_dt = parse_dt(candidate)
    if current_dt and candidate_dt:
        return candidate if candidate_dt <= current_dt else current
    return min(current, candidate)


def date_from_timestamp(value: str | None) -> str:
    parsed = parse_dt(value)
    if parsed:
        return parsed.date().isoformat()
    if value and len(value) >= 10:
        return value[:10]
    return "unknown"


def extract_token_usage(value: Any) -> dict[str, int]:
    usage = as_dict(value)
    result = {key: safe_int(usage.get(key)) for key in TOKEN_KEYS}
    if result["total_tokens"] == 0:
        result["total_tokens"] = result["input_tokens"] + result["output_tokens"]
    return result


def relative_or_name(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return path.name


@dataclass
class SessionAccumulator:
    source_root: str
    source_file_raw: str
    fallback_session_id: str
    records_seen: int = 0
    malformed_records: int = 0
    session_id_raw: str | None = None
    first_timestamp: str | None = None
    last_updated_at: str | None = None
    cwd_raw: str | None = None
    model: str | None = None
    reported_turn_count: int = 0
    turn_context_count: int = 0
    token_events_count: int = 0
    max_single_turn_total_tokens: int = 0
    memory_citation_detected: bool = False
    previous_total_usage: dict[str, int] | None = None
    token_events: list[dict[str, Any]] = field(default_factory=list)
    turn_event_dates: list[str] = field(default_factory=list)
    total_usage: dict[str, int] = field(
        default_factory=lambda: {
            "input_tokens": 0,
            "cached_input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
        }
    )

    def ingest(self, obj: dict[str, Any]) -> None:
        self.records_seen += 1
        payload = as_dict(obj.get("payload"))
        event_type = str(obj.get("type") or payload.get("type") or "")

        timestamp = (
            obj.get("timestamp")
            or payload.get("timestamp")
            or payload.get("started_at")
            or payload.get("completed_at")
        )
        if isinstance(timestamp, str):
            self.first_timestamp = min_iso(self.first_timestamp, timestamp)
            self.last_updated_at = max_iso(self.last_updated_at, timestamp)

        completed_at = payload.get("completed_at")
        if isinstance(completed_at, str):
            self.last_updated_at = max_iso(self.last_updated_at, completed_at)

        if event_type == "session_meta":
            payload_id = payload.get("id")
            if isinstance(payload_id, str) and payload_id and not self.session_id_raw:
                self.session_id_raw = payload_id

        cwd = payload.get("cwd")
        if isinstance(cwd, str) and cwd and not self.cwd_raw:
            self.cwd_raw = cwd

        model = payload.get("model")
        if isinstance(model, str) and model:
            self.model = model

        num_turns = safe_int(payload.get("num_turns"))
        event_date = date_from_timestamp(timestamp if isinstance(timestamp, str) else None)

        if num_turns:
            self.reported_turn_count = max(self.reported_turn_count, num_turns)
        elif event_type == "turn_context":
            self.turn_context_count += 1
            self.turn_event_dates.append(event_date)

        if "memory_citation" in payload and payload.get("memory_citation") not in (None, "", [], {}):
            self.memory_citation_detected = True

        info = as_dict(payload.get("info"))
        total_usage = extract_token_usage(info.get("total_token_usage"))
        last_usage = extract_token_usage(info.get("last_token_usage"))
        has_total_usage = any(total_usage.values())
        if has_total_usage:
            event_usage = self.delta_from_total_usage(total_usage)
            if any(event_usage.values()):
                self.token_events.append({"date": event_date, **event_usage})
                self.max_single_turn_total_tokens = max(
                    self.max_single_turn_total_tokens, event_usage["total_tokens"]
                )
            self.token_events_count += 1
            self.total_usage = total_usage
        elif any(last_usage.values()):
            self.token_events.append({"date": event_date, **last_usage})
            self.token_events_count += 1
            self.max_single_turn_total_tokens = max(
                self.max_single_turn_total_tokens, last_usage["total_tokens"]
            )

    def delta_from_total_usage(self, total_usage: dict[str, int]) -> dict[str, int]:
        if self.previous_total_usage is None:
            self.previous_total_usage = dict(total_usage)
            return dict(total_usage)
        delta: dict[str, int] = {}
        for key in TOKEN_KEYS:
            current = total_usage[key]
            previous = self.previous_total_usage.get(key, 0)
            delta[key] = current - previous if current >= previous else current
        self.previous_total_usage = dict(total_usage)
        if delta["total_tokens"] == 0:
            delta["total_tokens"] = delta["input_tokens"] + delta["output_tokens"]
        return delta

    def finalize(
        self,
        session_label: str,
        source_label: str,
        project_label: str,
        redact_paths: bool,
    ) -> dict[str, Any]:
        session_id = session_label if redact_paths else (self.session_id_raw or self.fallback_session_id)
        source_file = source_label if redact_paths else self.source_file_raw
        project = project_label
        cwd = None if redact_paths else self.cwd_raw
        first_timestamp = self.first_timestamp or self.last_updated_at
        cache_ratio = ratio(self.total_usage["cached_input_tokens"], self.total_usage["input_tokens"])
        output_input_ratio = ratio(self.total_usage["output_tokens"], self.total_usage["input_tokens"])
        turn_count = max(self.reported_turn_count, self.turn_context_count)
        return {
            "session_id": session_id,
            "source_root": self.source_root,
            "source_file": source_file,
            "date": date_from_timestamp(first_timestamp),
            "first_timestamp": first_timestamp,
            "last_updated_at": self.last_updated_at,
            "project": project,
            "cwd": cwd,
            "model": self.model or "unknown",
            "input_tokens": self.total_usage["input_tokens"],
            "cached_input_tokens": self.total_usage["cached_input_tokens"],
            "output_tokens": self.total_usage["output_tokens"],
            "total_tokens": self.total_usage["total_tokens"],
            "turn_count": turn_count,
            "token_events_count": self.token_events_count,
            "max_single_turn_total_tokens": self.max_single_turn_total_tokens,
            "cache_ratio": cache_ratio,
            "output_input_ratio": output_input_ratio,
            "memory_citation_detected": self.memory_citation_detected,
            "records_seen": self.records_seen,
            "malformed_records": self.malformed_records,
        }


def ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


def discover_files(roots: list[tuple[str, Path]]) -> list[tuple[str, Path, Path]]:
    files: list[tuple[str, Path, Path]] = []
    for source, root in roots:
        if not root.exists():
            continue
        if root.is_file() and root.suffix == ".jsonl":
            files.append((source, root.parent, root))
            continue
        for path in sorted(root.rglob("*.jsonl")):
            files.append((source, root, path))
    return files


def parse_jsonl_file(source: str, root: Path, path: Path, source_root: str) -> SessionAccumulator:
    acc = SessionAccumulator(
        source_root=f"{source}:{source_root}",
        source_file_raw=relative_or_name(path, root),
        fallback_session_id=path.stem,
    )
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                acc.malformed_records += 1
                continue
            if not isinstance(obj, dict):
                acc.malformed_records += 1
                continue
            acc.ingest(obj)
    return acc


def assign_labels(raw_values: list[str | None], prefix: str) -> dict[str | None, str]:
    labels: dict[str | None, str] = {None: "Unknown"}
    counter = 1
    for value in raw_values:
        if value in labels:
            continue
        labels[value] = f"{prefix} {counter}"
        counter += 1
    return labels


def project_name_from_cwd(cwd: str | None) -> str:
    if not cwd:
        return "Unknown"
    name = Path(cwd).name
    return name or "Unknown"


def project_label_from_cwd(cwd: str | None, mode: str, fallback_label: str) -> str:
    if not cwd:
        return "Unknown"
    if mode == "path":
        return cwd
    if mode == "name":
        return project_name_from_cwd(cwd)
    return fallback_label


def display_root(root: Path, index: int, redact_paths: bool) -> str:
    if not redact_paths:
        return str(root)
    try:
        home_relative = root.resolve().relative_to(Path.home().resolve())
        return "~/" + str(home_relative)
    except ValueError:
        return f"Input root {index}"


def build_daily(
    token_events: list[dict[str, Any]], turn_events: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    session_sets: dict[str, set[str]] = defaultdict(set)
    for event in token_events:
        day = event["date"]
        if day not in grouped:
            grouped[day] = {
                "date": day,
                "sessions": 0,
                "turns": 0,
                "usage_events": 0,
                "input_tokens": 0,
                "cached_input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "max_single_turn_total_tokens": 0,
            }
        row = grouped[day]
        session_sets[day].add(str(event.get("session_id") or "unknown"))
        row["usage_events"] += 1
        row["input_tokens"] += safe_int(event.get("input_tokens"))
        row["cached_input_tokens"] += safe_int(event.get("cached_input_tokens"))
        row["output_tokens"] += safe_int(event.get("output_tokens"))
        row["total_tokens"] += safe_int(event.get("total_tokens"))
        row["max_single_turn_total_tokens"] = max(
            row["max_single_turn_total_tokens"], safe_int(event.get("total_tokens"))
        )
    for event in turn_events:
        day = event["date"]
        grouped.setdefault(
            day,
            {
                "date": day,
                "sessions": 0,
                "turns": 0,
                "usage_events": 0,
                "input_tokens": 0,
                "cached_input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "max_single_turn_total_tokens": 0,
            },
        )
        grouped[day]["turns"] += 1
        session_sets[day].add(str(event.get("session_id") or "unknown"))

    days = sorted(day for day in grouped if day != "unknown")
    if days:
        start = date.fromisoformat(days[0])
        end = date.fromisoformat(days[-1])
        span = (end - start).days
        for offset in range(span + 1):
            day = start.fromordinal(start.toordinal() + offset).isoformat()
            grouped.setdefault(
                day,
                {
                    "date": day,
                    "sessions": 0,
                    "turns": 0,
                    "usage_events": 0,
                    "input_tokens": 0,
                    "cached_input_tokens": 0,
                    "output_tokens": 0,
                    "total_tokens": 0,
                    "max_single_turn_total_tokens": 0,
                },
            )

    rows = [grouped[key] for key in sorted(grouped)]
    rolling: list[int] = []
    for index, row in enumerate(rows):
        row["sessions"] = len(session_sets.get(row["date"], set()))
        window = rows[max(0, index - 6) : index + 1]
        rolling.append(sum(safe_int(item["total_tokens"]) for item in window))
        row["cache_ratio"] = ratio(row["cached_input_tokens"], row["input_tokens"])
        row["output_input_ratio"] = ratio(row["output_tokens"], row["input_tokens"])
        row["rolling_7_day_total_tokens"] = rolling[-1]
    return rows


def aggregate_by(sessions: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            key: "",
            "sessions": 0,
            "turns": 0,
            "input_tokens": 0,
            "cached_input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
        }
    )
    for session in sessions:
        value = str(session.get(key) or "unknown")
        row = grouped[value]
        row[key] = value
        row["sessions"] += 1
        row["turns"] += safe_int(session.get("turn_count"))
        row["input_tokens"] += safe_int(session.get("input_tokens"))
        row["cached_input_tokens"] += safe_int(session.get("cached_input_tokens"))
        row["output_tokens"] += safe_int(session.get("output_tokens"))
        row["total_tokens"] += safe_int(session.get("total_tokens"))
    rows = list(grouped.values())
    for row in rows:
        row["cache_ratio"] = ratio(row["cached_input_tokens"], row["input_tokens"])
        row["output_input_ratio"] = ratio(row["output_tokens"], row["input_tokens"])
    return sorted(rows, key=lambda item: item["total_tokens"], reverse=True)


def build_memory_reuse_signals(
    sessions: list[dict[str, Any]],
    project_breakdown: list[dict[str, Any]],
) -> dict[str, Any]:
    citation_sessions = [
        {
            "session_id": session["session_id"],
            "date": session["date"],
            "project": session["project"],
            "total_tokens": session["total_tokens"],
            "turn_count": session["turn_count"],
        }
        for session in sessions
        if session.get("memory_citation_detected")
    ]
    repeated_projects = [
        row
        for row in project_breakdown
        if row["project"] != "Unknown" and row["sessions"] >= 2 and row["total_tokens"] > 0
    ]
    candidates = []
    for row in repeated_projects:
        avg_tokens = row["total_tokens"] // max(row["sessions"], 1)
        if avg_tokens >= 50000 or row["total_tokens"] >= 100000:
            candidates.append(
                {
                    "project": row["project"],
                    "sessions": row["sessions"],
                    "total_tokens": row["total_tokens"],
                    "average_tokens_per_session": avg_tokens,
                    "signal": (
                        "Repeated high-token project activity may benefit from durable memory "
                        "or a reusable skill."
                    ),
                }
            )
    return {
        "sessions_with_memory_citations": citation_sessions,
        "high_token_repeated_project_sessions": repeated_projects[:10],
        "candidates_for_memory_or_skill_creation": candidates[:10],
        "detection_notes": (
            "Memory citation detection uses metadata keys only. It does not persist citation text "
            "or conversation content."
        ),
    }


def qualitative_cache_label(cache_ratio: float) -> str:
    if cache_ratio >= 0.65:
        return "Strong context reuse"
    if cache_ratio >= 0.35:
        return "Moderate context reuse"
    if cache_ratio > 0:
        return "Low context reuse"
    return "No cache signal"


def qualitative_output_label(output_input_ratio: float) -> str:
    if output_input_ratio >= 0.6:
        return "Generation-heavy work"
    if output_input_ratio >= 0.25:
        return "Balanced collaboration"
    if output_input_ratio > 0:
        return "Context-heavy work"
    return "No output/input signal"


def build_insights(
    totals: dict[str, Any],
    daily: list[dict[str, Any]],
    project_breakdown: list[dict[str, Any]],
    memory_reuse_signals: dict[str, Any],
) -> dict[str, Any]:
    active_days = [row for row in daily if row.get("total_tokens")]
    peak_day = max(active_days, key=lambda row: row["total_tokens"], default=None)
    latest_active_day = active_days[-1] if active_days else None
    top_project = project_breakdown[0] if project_breakdown else None
    candidate_count = len(memory_reuse_signals.get("candidates_for_memory_or_skill_creation", []))
    cache_ratio = float(totals.get("cache_ratio") or 0)
    output_input_ratio = float(totals.get("output_input_ratio") or 0)
    return {
        "cache_label": qualitative_cache_label(cache_ratio),
        "output_input_label": qualitative_output_label(output_input_ratio),
        "latest_active_day": latest_active_day,
        "peak_day": peak_day,
        "top_project": top_project,
        "memory_candidate_count": candidate_count,
        "developer_value": [
            "High total tokens identify work that consumed the most context and review attention.",
            "Cache ratio shows whether repeated context is being reused efficiently.",
            (
                "Largest sessions reveal workflows that may benefit from smaller prompts, "
                "better project memory, or a reusable skill."
            ),
            (
                "Output/input ratio helps separate generation-heavy work from context-heavy "
                "debugging or exploration."
            ),
        ],
    }


def build_summary(
    roots: list[tuple[str, Path]], redact_paths: bool, project_label_mode: str = "redacted"
) -> dict[str, Any]:
    files = discover_files(roots)
    root_labels = {
        (source, root): display_root(root, index, redact_paths)
        for index, (source, root) in enumerate(roots, start=1)
    }
    accumulators = [
        parse_jsonl_file(source, root, path, root_labels.get((source, root), "Input root"))
        for source, root, path in files
    ]

    session_labels = assign_labels(
        [acc.session_id_raw or acc.fallback_session_id for acc in accumulators], "Session"
    )
    source_labels = assign_labels([acc.source_file_raw for acc in accumulators], "Source")
    redacted_project_labels = assign_labels([acc.cwd_raw for acc in accumulators], "Project")
    project_labels = {
        acc.cwd_raw: project_label_from_cwd(
            acc.cwd_raw,
            project_label_mode,
            redacted_project_labels.get(acc.cwd_raw, "Unknown"),
        )
        for acc in accumulators
    }
    project_labels[None] = "Unknown"

    sessions = [
        acc.finalize(
            session_label=session_labels[acc.session_id_raw or acc.fallback_session_id],
            source_label=source_labels[acc.source_file_raw],
            project_label=project_labels.get(acc.cwd_raw, "Unknown"),
            redact_paths=redact_paths,
        )
        for acc in accumulators
    ]
    sessions.sort(key=lambda item: (item["date"], item.get("last_updated_at") or ""), reverse=True)

    token_events: list[dict[str, Any]] = []
    turn_events: list[dict[str, Any]] = []
    for acc in accumulators:
        session_label = session_labels[acc.session_id_raw or acc.fallback_session_id]
        project_label = project_labels.get(acc.cwd_raw, "Unknown")
        for event in acc.token_events:
            token_events.append(
                {
                    **event,
                    "session_id": session_label,
                    "project": project_label,
                    "model": acc.model or "unknown",
                    "source_root": acc.source_root,
                }
            )
        for event_date in acc.turn_event_dates:
            turn_events.append(
                {
                    "date": event_date,
                    "session_id": session_label,
                    "project": project_label,
                    "model": acc.model or "unknown",
                    "source_root": acc.source_root,
                }
            )

    daily = build_daily(token_events, turn_events)
    project_breakdown = aggregate_by(sessions, "project")
    model_breakdown = aggregate_by(sessions, "model")
    largest_sessions = sorted(sessions, key=lambda item: item["total_tokens"], reverse=True)[:20]
    last_parsed_timestamp = None
    for session in sessions:
        last_parsed_timestamp = max_iso(last_parsed_timestamp, session.get("last_updated_at"))

    records_seen = sum(acc.records_seen for acc in accumulators)
    malformed_records = sum(acc.malformed_records for acc in accumulators)
    total_tokens = sum(safe_int(session.get("total_tokens")) for session in sessions)
    input_tokens = sum(safe_int(session.get("input_tokens")) for session in sessions)
    cached_input_tokens = sum(safe_int(session.get("cached_input_tokens")) for session in sessions)
    output_tokens = sum(safe_int(session.get("output_tokens")) for session in sessions)
    turns = sum(safe_int(session.get("turn_count")) for session in sessions)

    memory_reuse_signals = build_memory_reuse_signals(sessions, project_breakdown)
    totals = {
        "sessions": len(sessions),
        "turns": turns,
        "input_tokens": input_tokens,
        "cached_input_tokens": cached_input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "cache_ratio": ratio(cached_input_tokens, input_tokens),
        "output_input_ratio": ratio(output_tokens, input_tokens),
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now_iso(),
        "freshness": {
            "last_parsed_timestamp": last_parsed_timestamp,
            "files_scanned": len(files),
            "sessions_parsed": len(sessions),
            "records_seen": records_seen,
            "records_skipped": malformed_records,
            "malformed_records": malformed_records,
            "roots_scanned": [f"{source}:{root_labels[(source, root)]}" for source, root in roots],
            "sources": sorted({source for source, _root in roots}),
        },
        "privacy": {
            "local_only": True,
            "content_fields_ignored": True,
            "raw_conversation_text_persisted": False,
            "redact_paths": redact_paths,
            "project_label_mode": project_label_mode,
            "allowed_default_roots": [
                display_root(root, index, redact_paths) for index, root in enumerate(DEFAULT_ROOTS, start=1)
            ],
            "notes": [
                "Parser reads JSONL records but extracts only allowlisted metadata fields.",
                (
                    "Payload fields such as content, message, input, output, summary, "
                    "and text_elements are ignored."
                ),
                "Generated real usage files are intended to stay local and are ignored by git.",
            ],
        },
        "totals": totals,
        "insights": build_insights(totals, daily, project_breakdown, memory_reuse_signals),
        "daily": daily,
        "token_events": token_events,
        "sessions": sessions,
        "largest_sessions": largest_sessions,
        "project_breakdown": project_breakdown,
        "model_breakdown": model_breakdown,
        "memory_reuse_signals": memory_reuse_signals,
    }


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_outputs(summary: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_json = output_dir / GENERATED_FILES["summary_json"]
    summary_js = output_dir / GENERATED_FILES["summary_js"]
    summary_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary_js.write_text(
        "window.CODEX_USAGE_DATA = " + json.dumps(summary, separators=(",", ":"), sort_keys=True) + ";\n",
        encoding="utf-8",
    )
    daily_fields = [
        "date",
        "sessions",
        "turns",
        "usage_events",
        "input_tokens",
        "cached_input_tokens",
        "output_tokens",
        "total_tokens",
        "cache_ratio",
        "output_input_ratio",
        "rolling_7_day_total_tokens",
        "max_single_turn_total_tokens",
    ]
    session_fields = [
        "session_id",
        "source_root",
        "source_file",
        "date",
        "first_timestamp",
        "last_updated_at",
        "project",
        "cwd",
        "model",
        "input_tokens",
        "cached_input_tokens",
        "output_tokens",
        "total_tokens",
        "turn_count",
        "token_events_count",
        "max_single_turn_total_tokens",
        "cache_ratio",
        "output_input_ratio",
        "memory_citation_detected",
        "records_seen",
        "malformed_records",
    ]
    write_csv(output_dir / GENERATED_FILES["daily_csv"], summary["daily"], daily_fields)
    write_csv(output_dir / GENERATED_FILES["sessions_csv"], summary["sessions"], session_fields)


def print_run_summary(summary: dict[str, Any], dry_run: bool, output_dir: Path) -> None:
    freshness = summary["freshness"]
    totals = summary["totals"]
    mode = "Dry run" if dry_run else "Generated"
    print(f"{mode} summary")
    print(f"  files_scanned: {freshness['files_scanned']}")
    print(f"  sessions_parsed: {freshness['sessions_parsed']}")
    print(f"  records_seen: {freshness['records_seen']}")
    print(f"  records_skipped: {freshness['records_skipped']}")
    print(f"  total_tokens: {totals['total_tokens']}")
    print(f"  turns: {totals['turns']}")
    print("  privacy: content fields ignored, paths redacted by default")
    if not dry_run:
        print(f"  output_dir: {output_dir}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Codex usage dashboard data.")
    parser.add_argument(
        "--source",
        action="append",
        choices=sorted([*list(SOURCE_REGISTRY), "all"]),
        default=[],
        help="Built-in local metadata source to include. Defaults to codex. Use all for known JSONL sources.",
    )
    parser.add_argument(
        "--list-sources", action="store_true", help="List built-in source roots without parsing files."
    )
    parser.add_argument(
        "--input-root",
        action="append",
        default=[],
        help=(
            "Explicit JSONL input root. Repeatable. If omitted, only ~/.codex/sessions and "
            "~/.codex/archived_sessions are read."
        ),
    )
    parser.add_argument("--output-dir", default="data/generated", help="Generated output directory.")
    parser.add_argument("--dry-run", action="store_true", help="Parse and summarize without writing files.")
    parser.add_argument("--redact-paths", dest="redact_paths", action="store_true", default=True)
    parser.add_argument("--no-redact-paths", dest="redact_paths", action="store_false")
    parser.add_argument(
        "--project-label-mode",
        choices=["redacted", "name", "path"],
        default="redacted",
        help="How to label projects in generated data. Use name for basename-only project names.",
    )
    parser.add_argument(
        "--project-names",
        action="store_true",
        help="Shortcut for --project-label-mode name while keeping raw paths redacted.",
    )
    return parser.parse_args(argv)


def selected_source_roots(sources: list[str], input_roots: list[str]) -> list[tuple[str, Path]]:
    roots: list[tuple[str, Path]] = []
    requested = sources or ([] if input_roots else ["codex"])
    if "all" in requested:
        requested = [
            name for name, definition in SOURCE_REGISTRY.items() if definition["roots"] and name != "chatgpt"
        ]
    for source in requested:
        if source == "all":
            continue
        definition = SOURCE_REGISTRY[source]
        for root in definition["roots"]:
            roots.append((source, Path(root).expanduser()))
    for item in input_roots:
        roots.append(("custom", Path(item).expanduser().resolve()))
    return roots


def print_sources() -> None:
    for name, definition in SOURCE_REGISTRY.items():
        print(f"{name}: {definition['status']}")
        print(f"  {definition['description']}")
        if not definition["roots"]:
            print("  roots: none; use --input-root for explicit local data")
        for root in definition["roots"]:
            status = "exists" if Path(root).exists() else "missing"
            print(f"  {status}: {root}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.list_sources:
        print_sources()
        return 0
    roots = selected_source_roots(args.source, args.input_root)
    output_dir = Path(args.output_dir).expanduser().resolve()
    project_label_mode = "name" if args.project_names else args.project_label_mode
    if not args.redact_paths and project_label_mode == "redacted":
        project_label_mode = "path"
    summary = build_summary(
        roots=roots,
        redact_paths=args.redact_paths,
        project_label_mode=project_label_mode,
    )
    if not args.dry_run:
        write_outputs(summary, output_dir)
    print_run_summary(summary, dry_run=args.dry_run, output_dir=output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
