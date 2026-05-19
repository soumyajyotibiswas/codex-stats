#!/usr/bin/env python3
"""Repository-wide checks for non-generated portfolio artifacts."""

from __future__ import annotations

import json
import re
import stat
import tomllib
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCAL_USER_PATH_MARKER = Path.home().as_posix()
SKIP_DIRS = {
    ".git",
    ".local",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "data",
}
TEXT_EXTENSIONS = {
    ".bat",
    ".command",
    ".css",
    ".html",
    ".js",
    ".json",
    ".jsonl",
    ".lock",
    ".md",
    ".py",
    ".sh",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
TEXT_NAMES = {
    ".gitignore",
    "LICENSE",
    "Pipfile",
    "README.md",
    "SECURITY.md",
}
KNOWN_BINARY_EXTENSIONS = {
    ".png",
}
SECRET_PATTERNS = {
    "private key block": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "OpenAI-style API key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "Anthropic-style API key": re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}\b"),
    "GitHub token": re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
    "Google API key": re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b"),
    "Slack token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
}
SHELL_FORBIDDEN = (
    "rm -rf",
    "sudo ",
    "curl ",
    "wget ",
    "| sh",
    "| bash",
)
BATCH_FORBIDDEN = (
    "powershell",
    "curl ",
    "bitsadmin",
    "certutil",
    "del /",
    "rmdir ",
)
JS_FORBIDDEN = (
    "eval(",
    "new Function",
    "document.write",
    'setTimeout("',
    'setInterval("',
)
CSS_FORBIDDEN = (
    "@import",
    "url(http://",
    "url(https://",
    "expression(",
)


@dataclass(frozen=True)
class SecurityIssue:
    path: Path | None
    code: str

    def render(self) -> str:
        if self.path is None:
            return self.code
        return f"{self.path.as_posix()}: {self.code}"


class HtmlRuntimeReferenceParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.issues: list[str] = []

    def handle_starttag(self, _tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {name.lower(): value or "" for name, value in attrs}
        for name, value in attr_map.items():
            lowered = value.lower()
            if name.startswith("on"):
                self.issues.append("inline event handler")
            if lowered.startswith("javascript:"):
                self.issues.append("javascript URL")
            if name in {"src", "href", "action"} and lowered.startswith(("http://", "https://", "//")):
                self.issues.append("remote runtime reference")


def iter_repo_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        if path.is_dir():
            continue
        relative_parts = path.relative_to(ROOT).parts
        if any(part in SKIP_DIRS for part in relative_parts):
            continue
        files.append(path)
    return sorted(files)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def is_text_artifact(path: Path) -> bool:
    return path.suffix in TEXT_EXTENSIONS or path.name in TEXT_NAMES


def is_known_binary_artifact(path: Path) -> bool:
    return path.suffix in KNOWN_BINARY_EXTENSIONS and "assets" in path.parts


def check_known_binary(path: Path, issues: list[SecurityIssue]) -> None:
    if path.suffix == ".png" and not path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"):
        issues.append(SecurityIssue(path.relative_to(ROOT), "invalid PNG header"))


def check_secret_patterns(path: Path, text: str, issues: list[SecurityIssue]) -> None:
    if LOCAL_USER_PATH_MARKER in text:
        issues.append(SecurityIssue(path, "contains absolute local user path"))
    for name, pattern in SECRET_PATTERNS.items():
        if pattern.search(text):
            issues.append(SecurityIssue(path, f"possible secret pattern: {name}"))


def check_html(path: Path, text: str, issues: list[SecurityIssue]) -> None:
    parser = HtmlRuntimeReferenceParser()
    parser.feed(text)
    for issue in parser.issues:
        issues.append(SecurityIssue(path, issue))


def check_css(path: Path, text: str, issues: list[SecurityIssue]) -> None:
    lowered = text.lower()
    for pattern in CSS_FORBIDDEN:
        if pattern in lowered:
            issues.append(SecurityIssue(path, f"forbidden CSS pattern: {pattern}"))


def check_js(path: Path, text: str, issues: list[SecurityIssue]) -> None:
    for pattern in JS_FORBIDDEN:
        if pattern in text:
            issues.append(SecurityIssue(path, f"forbidden JS pattern: {pattern}"))


def check_shell(path: Path, text: str, issues: list[SecurityIssue]) -> None:
    lowered = text.lower()
    for pattern in SHELL_FORBIDDEN:
        if pattern in lowered:
            issues.append(SecurityIssue(path, f"forbidden shell pattern: {pattern}"))


def check_batch(path: Path, text: str, issues: list[SecurityIssue]) -> None:
    lowered = text.lower()
    for pattern in BATCH_FORBIDDEN:
        if pattern in lowered:
            issues.append(SecurityIssue(path, f"forbidden batch pattern: {pattern}"))


def check_structured(path: Path, text: str, issues: list[SecurityIssue]) -> None:
    try:
        if path.suffix == ".json" or path.name == "Pipfile.lock":
            json.loads(text)
        elif path.suffix == ".jsonl":
            for line in text.splitlines():
                if line.strip():
                    json.loads(line)
        elif path.suffix == ".toml" or path.name == "Pipfile":
            tomllib.loads(text)
    except (json.JSONDecodeError, tomllib.TOMLDecodeError):
        issues.append(SecurityIssue(path, "invalid structured file"))


def check_executable_modes(issues: list[SecurityIssue]) -> None:
    expected = [
        "install.py",
        "install.sh",
        "quickstart.command",
        "quickstart.sh",
        "scripts/build_usage_data.py",
        "scripts/check_repo_security.py",
        "scripts/privacy_audit.py",
        "scripts/schedule_dashboard.py",
        "scripts/serve_dashboard.py",
    ]
    for relative in expected:
        path = ROOT / relative
        if not path.exists():
            issues.append(SecurityIssue(Path(relative), "expected executable file is missing"))
            continue
        if not (path.stat().st_mode & stat.S_IXUSR):
            issues.append(SecurityIssue(Path(relative), "expected executable bit for owner"))


def main() -> int:
    issues: list[SecurityIssue] = []
    for path in iter_repo_files():
        if not is_text_artifact(path):
            if is_known_binary_artifact(path):
                check_known_binary(path, issues)
                continue
            issues.append(SecurityIssue(path.relative_to(ROOT), "unexpected binary or unknown file type"))
            continue
        text = read_text(path)
        relative = path.relative_to(ROOT)
        check_secret_patterns(relative, text, issues)
        check_structured(relative, text, issues)
        if path.suffix == ".html":
            check_html(relative, text, issues)
        elif path.suffix == ".css":
            check_css(relative, text, issues)
        elif path.suffix == ".js":
            check_js(relative, text, issues)
        elif path.suffix in {".sh", ".command"}:
            check_shell(relative, text, issues)
        elif path.suffix == ".bat":
            check_batch(relative, text, issues)
    check_executable_modes(issues)
    if issues:
        print("Repository security check failed:")
        for issue in issues:
            print(f"  - {issue.render()}")
        return 1
    print("Repository security check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
