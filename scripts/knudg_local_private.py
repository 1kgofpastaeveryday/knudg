#!/usr/bin/env python3
import argparse
import ipaddress
import json
import re
import sys
import unicodedata
from pathlib import Path
from urllib.parse import urlparse, urlunparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.card_payload import canonical_digest, canonicalize, load_json_without_duplicate_keys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


SCHEMA_VERSION = "local-private-card-v0"
SOURCE_CLASS = "local_private_dogfood"

ALLOWED_FIELDS = {
    "source_class",
    "title",
    "human_summary",
    "problem_summary",
    "solution_summary",
    "public_packages",
    "environment_tags",
    "public_reference_urls",
    "command_labels",
    "error_fingerprints",
    "lessons",
}
REQUIRED_FIELDS = set(ALLOWED_FIELDS)

TEXT_BOUNDS = {
    "title": (8, 120),
    "problem_summary": (20, 600),
    "solution_summary": (20, 900),
}
HUMAN_SUMMARY_BOUNDS = {
    "content": (20, 240),
    "redaction_summary": (20, 240),
}
LIST_BOUNDS = {
    "public_packages": (8, 1, 80),
    "environment_tags": (12, 1, 40),
    "public_reference_urls": (3, 1, 2048),
    "command_labels": (6, 1, 80),
    "error_fingerprints": (6, 1, 120),
    "lessons": (6, 1, 200),
}

PRIVATE_HOST_SUFFIXES = (
    ".corp",
    ".home",
    ".internal",
    ".intranet",
    ".lan",
    ".local",
    ".localhost",
    ".private",
)
PUBLIC_URL_HOST_ALLOWLIST = {
    "docs.github.com",
    "github.com",
    "gitlab.com",
    "pypi.org",
    "www.npmjs.com",
    "nodejs.org",
    "docs.python.org",
    "developer.mozilla.org",
    "learn.microsoft.com",
}

URL_RE = re.compile(r"\bhttps?://", re.IGNORECASE)
WINDOWS_PATH_RE = re.compile(r"(?:^|[\s\"'`])(?:[A-Z]:[\\/]|\\\\[A-Za-z0-9_.-]+[\\/])", re.IGNORECASE)
UNIX_PRIVATE_PATH_RE = re.compile(
    r"(?:^|[\s\"'`])/(?:Users|home|root|var|etc|tmp|opt|mnt|Volumes|private)(?:/|\b)",
    re.IGNORECASE,
)
RELATIVE_PRIVATE_PATH_RE = re.compile(r"(?:^|[\s\"'`])(?:~[\\/]|\.{1,2}[\\/])")
PRIVATE_HOST_RE = re.compile(
    r"\b(?:localhost|127\.0\.0\.1|0\.0\.0\.0|\[?::1\]?|[a-z0-9][a-z0-9-]*(?:\.local|\.internal|\.corp|\.lan|\.home|\.intranet|\.private))\b",
    re.IGNORECASE,
)
HOST_LABEL_RE = re.compile(r"\b(?:host|hostname|machine|server|workstation)\s*[:=]\s*[a-z0-9][a-z0-9-]{1,}\b", re.IGNORECASE)
SECRET_WORD_RE = re.compile(
    r"\b(?:password|passwd|secret|token|api[_-]?key|credential|authorization|bearer|private[_ -]?key)\b",
    re.IGNORECASE,
)
TOKEN_PREFIX_RE = re.compile(
    r"\b(?:sk-[A-Za-z0-9_-]{8,}|gh[opusr]_[A-Za-z0-9_]{12,}|xox[baprs]-[A-Za-z0-9-]{8,}|AKIA[0-9A-Z]{16})\b"
)
HIGH_ENTROPY_RE = re.compile(r"\b(?:[A-Fa-f0-9]{32,}|[A-Za-z0-9+/]{40,}={0,2})\b")
STACK_TRACE_RE = re.compile(
    r"(?:traceback\s*\(most recent call last\)|\bfile\s+\"[^\"]+\",\s+line\s+\d+|\bat\s+[A-Za-z0-9_.$<>]+\([^)]*:\d+(?::\d+)?\)|exception in thread)",
    re.IGNORECASE,
)
SHELL_META_RE = re.compile(r"(?:&&|\|\||[;&|<>`]|[$]\()")
FLAG_RE = re.compile(r"(?:^|\s)--?[A-Za-z0-9][A-Za-z0-9_-]*\b")
ASSIGNMENT_RE = re.compile(r"(?:^|\s)[A-Z_][A-Z0-9_]{1,}=")
DESTRUCTIVE_TARGET_RE = re.compile(r"\b(?:rm|del|erase|rmdir|remove-item)\s+(?:-[^\s]+\s+)?\S+", re.IGNORECASE)
COMMAND_OUTPUT_RE = re.compile(
    r"(?:^|\s)(?:exit code:\s*\d+|wall time:|npm\s+err!|error command failed|ps\s+[a-z]:\\|[$>]\s+\S+)",
    re.IGNORECASE,
)
EXECUTABLE_COMMAND_RE = re.compile(
    r"^\s*(?:python(?:3)?|node|npm|npx|pnpm|yarn|git|curl|wget|docker|kubectl|psql|pip|uv|poetry|powershell|pwsh|cmd|bash|sh)\b(?=.*(?:\s--?|\s-m\b|[\\/]|[;&|<>`]|[$]\())",
    re.IGNORECASE,
)


class LocalPrivateCardError(ValueError):
    def __init__(self, reject_class="invalid_payload"):
        self.reject_class = reject_class
        super().__init__(f"local private card rejected: {reject_class}")


def _reject(reject_class):
    raise LocalPrivateCardError(reject_class)


def _normalize_text(value, reject_class="invalid_payload"):
    if not isinstance(value, str):
        _reject(reject_class)
    normalized = unicodedata.normalize("NFC", value)
    chars = []
    for char in normalized:
        category = unicodedata.category(char)
        if category == "Cc":
            if char in "\t\n\r\f\v":
                chars.append(" ")
            continue
        if category == "Cf":
            continue
        chars.append(char)
    return re.sub(r"\s+", " ", "".join(chars)).strip()


def _check_length(field, value, min_length, max_length):
    length = len(value)
    if length < min_length or length > max_length:
        _reject(f"{field}_bounds")


def _is_public_hostname(hostname):
    host = hostname.rstrip(".").lower()
    if not host or host == "localhost" or host.endswith(PRIVATE_HOST_SUFFIXES):
        return False
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        return ip.is_global
    if "." not in host:
        return False
    labels = host.split(".")
    return all(label and len(label) <= 63 and re.fullmatch(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?", label) for label in labels)


def _normalize_public_url(value):
    text = _normalize_text(value, "public_reference_urls_bounds")
    _check_length("public_reference_urls", text, 1, 2048)
    parsed = urlparse(text)
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        _reject("public_reference_url")
    if parsed.username or parsed.password or parsed.port is not None:
        _reject("public_reference_url")
    host = parsed.hostname.rstrip(".").lower()
    if not _is_public_hostname(host):
        _reject("public_reference_url")
    if host not in PUBLIC_URL_HOST_ALLOWLIST:
        _reject("public_reference_url")
    path = parsed.path or ""
    query = parsed.query or ""
    canonical = urlunparse(("https", host, path, "", query, ""))
    _scan_secret_or_trace(canonical)
    return canonical


def _looks_like_private_path(value):
    return bool(WINDOWS_PATH_RE.search(value) or UNIX_PRIVATE_PATH_RE.search(value) or RELATIVE_PRIVATE_PATH_RE.search(value))


def _scan_secret_or_trace(value):
    if SECRET_WORD_RE.search(value) or TOKEN_PREFIX_RE.search(value) or HIGH_ENTROPY_RE.search(value):
        _reject("secret_or_token")
    if STACK_TRACE_RE.search(value):
        _reject("stack_trace")


def _scan_private_identity(value):
    if _looks_like_private_path(value):
        _reject("private_path")
    if PRIVATE_HOST_RE.search(value) or HOST_LABEL_RE.search(value):
        _reject("private_hostname")


def _scan_command_or_output(value, *, command_label=False):
    if COMMAND_OUTPUT_RE.search(value):
        _reject("raw_command_output")
    if SHELL_META_RE.search(value) or ASSIGNMENT_RE.search(value) or DESTRUCTIVE_TARGET_RE.search(value):
        _reject("executable_command")
    if command_label and FLAG_RE.search(value):
        _reject("executable_command")
    if EXECUTABLE_COMMAND_RE.search(value):
        _reject("executable_command")


def _scan_sanitized_string(value, *, allow_url=False, command_label=False):
    if not allow_url and URL_RE.search(value):
        _reject("url_not_allowed")
    _scan_private_identity(value)
    _scan_secret_or_trace(value)
    _scan_command_or_output(value, command_label=command_label)


def _scan_cross_field_reconstruction(values):
    joined = " ".join(values)
    compact = "".join(values)
    _scan_private_identity(joined)
    _scan_secret_or_trace(joined)
    _scan_command_or_output(joined)
    _scan_private_identity(compact)
    if TOKEN_PREFIX_RE.search(compact):
        _reject("secret_or_token")
    _scan_command_or_output(compact)


def _normalize_string_list(field, values):
    if not isinstance(values, list):
        _reject(f"{field}_bounds")
    max_items, min_length, max_length = LIST_BOUNDS[field]
    if len(values) > max_items:
        _reject(f"{field}_bounds")
    normalized = []
    for item in values:
        text = _normalize_text(item, f"{field}_bounds")
        _check_length(field, text, min_length, max_length)
        _scan_sanitized_string(text, command_label=field == "command_labels")
        normalized.append(text)
    return normalized


def _normalize_human_summary(value):
    if not isinstance(value, dict):
        _reject("human_summary_bounds")
    extra = set(value) - set(HUMAN_SUMMARY_BOUNDS)
    missing = set(HUMAN_SUMMARY_BOUNDS) - set(value)
    if extra or missing:
        _reject("human_summary_fields")
    sanitized = {}
    for field, (min_length, max_length) in HUMAN_SUMMARY_BOUNDS.items():
        text = _normalize_text(value[field], f"human_summary_{field}_bounds")
        _check_length(f"human_summary_{field}", text, min_length, max_length)
        _scan_sanitized_string(text)
        sanitized[field] = text
    return sanitized


def validate_local_private_card_v0(payload):
    if not isinstance(payload, dict):
        _reject("invalid_payload")
    extra = set(payload) - ALLOWED_FIELDS
    missing = REQUIRED_FIELDS - set(payload)
    if extra or missing:
        _reject("invalid_fields")
    if payload.get("source_class") != SOURCE_CLASS:
        _reject("source_class")

    sanitized = {"source_class": SOURCE_CLASS}
    collected = [SOURCE_CLASS]
    sanitized["human_summary"] = _normalize_human_summary(payload["human_summary"])
    collected.extend(sanitized["human_summary"].values())
    for field, (min_length, max_length) in TEXT_BOUNDS.items():
        value = _normalize_text(payload[field], f"{field}_bounds")
        _check_length(field, value, min_length, max_length)
        _scan_sanitized_string(value)
        sanitized[field] = value
        collected.append(value)

    for field in (
        "public_packages",
        "environment_tags",
        "command_labels",
        "error_fingerprints",
        "lessons",
    ):
        values = _normalize_string_list(field, payload[field])
        sanitized[field] = values
        collected.extend(values)

    urls = payload["public_reference_urls"]
    if not isinstance(urls, list) or len(urls) > LIST_BOUNDS["public_reference_urls"][0]:
        _reject("public_reference_urls_bounds")
    sanitized_urls = []
    for url in urls:
        canonical_url = _normalize_public_url(url)
        sanitized_urls.append(canonical_url)
        collected.append(canonical_url)
    sanitized["public_reference_urls"] = sanitized_urls

    _scan_cross_field_reconstruction(collected)
    return {
        "source_class": sanitized["source_class"],
        "title": sanitized["title"],
        "human_summary": sanitized["human_summary"],
        "problem_summary": sanitized["problem_summary"],
        "solution_summary": sanitized["solution_summary"],
        "public_packages": sanitized["public_packages"],
        "environment_tags": sanitized["environment_tags"],
        "public_reference_urls": sanitized["public_reference_urls"],
        "command_labels": sanitized["command_labels"],
        "error_fingerprints": sanitized["error_fingerprints"],
        "lessons": sanitized["lessons"],
    }


def canonicalize_local_private_card(payload):
    return canonicalize(validate_local_private_card_v0(payload))


def local_private_card_digest(payload):
    return canonical_digest(validate_local_private_card_v0(payload))


def parse_and_digest(raw_text):
    payload = load_json_without_duplicate_keys(raw_text)
    sanitized = validate_local_private_card_v0(payload)
    canonical = canonicalize(sanitized)
    digest = canonical_digest(sanitized)
    return sanitized, canonical, digest


def emit(value):
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))


def build_parser():
    parser = argparse.ArgumentParser(description="Validate and digest a Knudg local-private card.")
    parser.add_argument("--input", required=True, help="Path to a local-private-card-v0 JSON object.")
    parser.add_argument("--canonical", action="store_true", help="Print canonical JSON instead of the digest.")
    parser.add_argument("--json", action="store_true", help="Print a JSON response envelope.")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        sanitized, canonical, digest = parse_and_digest(Path(args.input).read_text(encoding="utf-8"))
        if args.json:
            emit({"ok": True, "schema_version": SCHEMA_VERSION, "digest": digest, "canonical": canonical, "payload": sanitized})
        else:
            print(canonical if args.canonical else digest)
        return 0
    except (LocalPrivateCardError, json.JSONDecodeError) as exc:
        if args.json:
            reject_class = getattr(exc, "reject_class", "invalid_json")
            emit({"ok": False, "status": "rejected", "reject_class": reject_class})
        else:
            print("local private card rejected", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
