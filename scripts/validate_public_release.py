"""Fail if a public release commit contains private-only material.

This check is intentionally conservative about project-specific artifacts and
operator paths. Broader schema canaries such as synthetic `/home/...` examples
belong in their own focused tests so this gate can run in every public CI pass.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

DENIED_PATH_PREFIXES = (
    ".agents/",
    ".codex/",
    ".letta/",
    ".playwright-mcp/",
    "docs/plans/",
    "public/",
    "workingknudg.codexknudglp-replay-shots/",
)

DENIED_PATHS = {
    "user-said.md",
    "scripts/export_public_repo.ps1",
    "scripts/knudg_mine_chat_logs.py",
}

DENIED_PATH_PATTERNS = (
    re.compile(r"^knudg-.*-live\.png$"),
)

DENIED_CONTENT_PATTERNS = (
    re.compile(r"C:[/\\]Users[/\\]4\b", re.IGNORECASE),
    re.compile(r"D:[/\\]working[/\\]knudg\b", re.IGNORECASE),
    re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC |DSA |)PRIVATE KEY-----"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{36,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
)

TEXT_SUFFIXES = {
    ".cfg",
    ".css",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".lock",
    ".md",
    ".mjs",
    ".py",
    ".sh",
    ".sql",
    ".toml",
    ".ts",
    ".txt",
    ".yaml",
    ".yml",
}


def git_lines(*args: str) -> list[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def tracked_files() -> list[str]:
    return git_lines("ls-files")


def local_refs() -> list[str]:
    return git_lines("for-each-ref", "--format=%(refname)")


def is_text_candidate(path: Path) -> bool:
    return path.suffix.lower() in TEXT_SUFFIXES or path.name in {".gitignore", "LICENSE", "README"}


def validate_paths(files: list[str]) -> list[str]:
    failures: list[str] = []
    for file_name in files:
        normalized = file_name.replace("\\", "/")
        if normalized in DENIED_PATHS:
            failures.append(f"denied tracked path: {normalized}")
        if any(normalized.startswith(prefix) for prefix in DENIED_PATH_PREFIXES):
            failures.append(f"denied tracked path prefix: {normalized}")
        if any(pattern.match(normalized) for pattern in DENIED_PATH_PATTERNS):
            failures.append(f"denied tracked path pattern: {normalized}")
    return failures


def validate_content(files: list[str]) -> list[str]:
    failures: list[str] = []
    for file_name in files:
        path = ROOT / file_name
        if not is_text_candidate(path):
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for pattern in DENIED_CONTENT_PATTERNS:
            if pattern.search(content):
                failures.append(f"denied content pattern {pattern.pattern!r}: {file_name}")
    return failures


def validate_refs(refs: list[str]) -> list[str]:
    failures: list[str] = []
    for ref in refs:
        if "private-pre-public-history" in ref:
            failures.append(f"denied local ref: {ref}")
    return failures


def main() -> int:
    files = tracked_files()
    failures = validate_paths(files)
    failures.extend(validate_content(files))
    failures.extend(validate_refs(local_refs()))

    if failures:
        print("Public release validation failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print("Public release validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
