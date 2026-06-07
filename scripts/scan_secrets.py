"""High-confidence repository secret scan for public CI.

This is a small complement to GitHub native secret scanning. It intentionally
checks only high-signal token shapes so public CI does not become noisy, and it
never prints the matched secret value.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

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

MAX_FILE_BYTES = 2_000_000


@dataclass(frozen=True)
class SecretPattern:
    name: str
    pattern: re.Pattern[str]


PATTERNS = (
    SecretPattern(
        "private_key",
        re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC |DSA |)?PRIVATE KEY-----"),
    ),
    SecretPattern(
        "github_token",
        re.compile(r"\b(?:github_pat_[A-Za-z0-9_]{22,}|gh[pousr]_[A-Za-z0-9_]{36,})\b"),
    ),
    SecretPattern("aws_access_key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    SecretPattern("google_api_key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    SecretPattern("openai_api_key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{32,}\b")),
    SecretPattern("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b")),
    SecretPattern("stripe_secret_key", re.compile(r"\bsk_(?:live|test)_[0-9A-Za-z]{24,}\b")),
)


@dataclass(frozen=True)
class Finding:
    source: str
    path: str
    line: int
    pattern_name: str
    fingerprint: str


def run_git(*args: str, text: bool = True) -> str | bytes:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=text,
    )
    return result.stdout


def tracked_and_public_untracked_files() -> list[str]:
    output = run_git("ls-files", "--cached", "--others", "--exclude-standard")
    assert isinstance(output, str)
    return [line.strip() for line in output.splitlines() if line.strip()]


def all_revisions() -> list[str]:
    output = run_git("rev-list", "--all")
    assert isinstance(output, str)
    return [line.strip() for line in output.splitlines() if line.strip()]


def files_at_revision(revision: str) -> list[str]:
    output = run_git("ls-tree", "-r", "--name-only", "-z", revision, text=False)
    assert isinstance(output, bytes)
    return [part.decode("utf-8", errors="replace") for part in output.split(b"\0") if part]


def is_text_candidate(file_name: str) -> bool:
    path = Path(file_name)
    return path.suffix.lower() in TEXT_SUFFIXES or path.name in {".gitignore", "LICENSE", "README"}


def decode_text(content: bytes) -> str | None:
    if b"\0" in content:
        return None
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        return None


def content_fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def scan_text(source: str, path: str, text: str) -> list[Finding]:
    findings: list[Finding] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        for secret_pattern in PATTERNS:
            for match in secret_pattern.pattern.finditer(line):
                findings.append(
                    Finding(
                        source=source,
                        path=path,
                        line=line_no,
                        pattern_name=secret_pattern.name,
                        fingerprint=content_fingerprint(match.group(0)),
                    )
                )
    return findings


def scan_worktree() -> list[Finding]:
    findings: list[Finding] = []
    for file_name in tracked_and_public_untracked_files():
        if not is_text_candidate(file_name):
            continue
        path = ROOT / file_name
        if not path.exists() or path.stat().st_size > MAX_FILE_BYTES:
            continue
        text = decode_text(path.read_bytes())
        if text is None:
            continue
        findings.extend(scan_text("worktree", file_name, text))
    return findings


def blob_at_revision(revision: str, file_name: str) -> bytes | None:
    try:
        output = run_git("show", f"{revision}:{file_name}", text=False)
    except subprocess.CalledProcessError:
        return None
    assert isinstance(output, bytes)
    if len(output) > MAX_FILE_BYTES:
        return None
    return output


def scan_history() -> list[Finding]:
    findings: list[Finding] = []
    seen_blobs: set[tuple[str, str]] = set()
    for revision in all_revisions():
        short_revision = revision[:12]
        for file_name in files_at_revision(revision):
            if not is_text_candidate(file_name):
                continue
            blob = blob_at_revision(revision, file_name)
            if blob is None:
                continue
            blob_digest = hashlib.sha256(blob).hexdigest()
            blob_key = (file_name, blob_digest)
            if blob_key in seen_blobs:
                continue
            seen_blobs.add(blob_key)
            text = decode_text(blob)
            if text is None:
                continue
            findings.extend(scan_text(f"history:{short_revision}", file_name, text))
    return findings


def unique_findings(findings: list[Finding]) -> list[Finding]:
    seen: set[tuple[str, str, int, str, str]] = set()
    unique: list[Finding] = []
    for finding in findings:
        key = (
            finding.source,
            finding.path,
            finding.line,
            finding.pattern_name,
            finding.fingerprint,
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(finding)
    return unique


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan public repo content for high-confidence secrets.")
    parser.add_argument("--history", action="store_true", help="Scan all reachable git history.")
    args = parser.parse_args()

    findings = scan_worktree()
    if args.history:
        findings.extend(scan_history())
    findings = unique_findings(findings)

    if findings:
        print("Secret scan failed. Matched values are redacted; rotate any real leaked value.", file=sys.stderr)
        for finding in findings:
            print(
                f"- {finding.source} {finding.path}:{finding.line} "
                f"{finding.pattern_name} sha256:{finding.fingerprint}",
                file=sys.stderr,
            )
        return 1

    history_suffix = " and git history" if args.history else ""
    print(f"Secret scan passed for public worktree{history_suffix}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
