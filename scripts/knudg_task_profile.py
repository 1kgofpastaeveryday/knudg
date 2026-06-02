#!/usr/bin/env python3
import argparse
import json
import re
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

from knudg_domain_policy import DomainPolicyError, normalize_retrieval_domains


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "task-profile-v0.schema.json"

RAW_PATTERNS = [
    re.compile(r"https?://", re.IGNORECASE),
    re.compile(r"\b[A-Z]:\\", re.IGNORECASE),
    re.compile(r"\b[A-Z]:/", re.IGNORECASE),
    re.compile(r"(^|\s)/(Users|home|var|etc|tmp)/", re.IGNORECASE),
    re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b"),
    re.compile(r"\b(?:password|secret|token|api[_-]?key|credential|private[_-]?key)\b", re.IGNORECASE),
    re.compile(r"\b(?:npm install|pip install|curl |rm -rf|git clone)\b", re.IGNORECASE),
]

INPUT_SCHEMA_VERSION = "task-profile-builder-input-v0"
PROFILE_SCHEMA_VERSION = "task_profile.v0"
ALLOWED_INPUT_FIELDS = {
    "schema_version",
    "intent",
    "explicit_query",
    "repo_shape_category",
    "subsystems",
    "safe_file_refs",
    "symbols",
    "error_fingerprints",
    "public_packages",
    "public_frameworks_tools",
    "language_runtime",
    "coarse_os",
    "dependency_major_versions",
    "risk_tags",
    "recent_event_kinds",
    "retrieval_domains",
}
ARRAY_FIELDS = {
    "subsystems",
    "safe_file_refs",
    "symbols",
    "error_fingerprints",
    "public_packages",
    "public_frameworks_tools",
    "dependency_major_versions",
    "risk_tags",
    "recent_event_kinds",
    "retrieval_domains",
}
QUERY_VIEW_FIELDS = {
    "exact_identifiers": (
        "error_fingerprints",
        "symbols",
        "public_packages",
        "public_frameworks_tools",
        "dependency_major_versions",
    ),
    "sparse_keywords": (
        "explicit_query",
        "repo_shape_category",
        "subsystems",
        "symbols",
        "error_fingerprints",
        "public_packages",
        "public_frameworks_tools",
        "language_runtime",
        "coarse_os",
        "dependency_major_versions",
    ),
    "semantic_summary": (
        "explicit_query",
        "repo_shape_category",
        "subsystems",
        "public_frameworks_tools",
    ),
    "hypothetical_relevant_card": (
        "explicit_query",
        "error_fingerprints",
        "repo_shape_category",
    ),
    "structured_filters": (
        "repo_shape_category",
        "language_runtime",
        "coarse_os",
        "dependency_major_versions",
        "risk_tags",
    ),
}


class TaskProfileError(ValueError):
    pass


def emit(value):
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validator():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def reject_raw_value(value):
    if isinstance(value, str):
        for pattern in RAW_PATTERNS:
            if pattern.search(value):
                raise TaskProfileError("input rejected")
        if any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise TaskProfileError("input rejected")
    elif isinstance(value, list):
        for item in value:
            reject_raw_value(item)
    elif isinstance(value, dict):
        for item in value.values():
            reject_raw_value(item)


def normalize_array(value):
    if value is None:
        return []
    if not isinstance(value, list):
        raise TaskProfileError("input rejected")
    result = []
    seen = set()
    for item in value:
        if not isinstance(item, str):
            raise TaskProfileError("input rejected")
        normalized = item.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def normalize_string(path, value):
    if not isinstance(value, str):
        raise TaskProfileError("input rejected")
    normalized = value.strip()
    if not normalized:
        raise TaskProfileError("input rejected")
    return normalized


def build_task_profile(input_payload):
    if not isinstance(input_payload, dict):
        raise TaskProfileError("input rejected")
    extra = sorted(set(input_payload) - ALLOWED_INPUT_FIELDS)
    if extra:
        raise TaskProfileError("input rejected")
    if input_payload.get("schema_version") != INPUT_SCHEMA_VERSION:
        raise TaskProfileError("input rejected")
    reject_raw_value(input_payload)

    profile = {
        "schema_version": PROFILE_SCHEMA_VERSION,
        "intent": normalize_string("intent", input_payload.get("intent")),
        "explicit_query": normalize_string("explicit_query", input_payload.get("explicit_query")),
        "repo_shape_category": normalize_string("repo_shape_category", input_payload.get("repo_shape_category")),
        "retrieval_domains": _normalize_retrieval_domains(input_payload.get("retrieval_domains")),
        "recent_event_kinds": normalize_array(input_payload.get("recent_event_kinds")),
    }
    for field in ARRAY_FIELDS - {"recent_event_kinds", "retrieval_domains"}:
        values = normalize_array(input_payload.get(field))
        if values:
            profile[field] = values
    for field in ("language_runtime", "coarse_os"):
        value = input_payload.get(field)
        if value is not None:
            profile[field] = normalize_string(field, value)

    errors = sorted(validator().iter_errors(profile), key=lambda error: list(error.path))
    if errors:
        raise TaskProfileError("input rejected")
    return profile


def _normalize_retrieval_domains(value):
    try:
        return normalize_retrieval_domains(value)
    except DomainPolicyError as error:
        raise TaskProfileError("input rejected") from error


def normalize_token(value):
    return re.sub(r"[^a-z0-9_.:+/@-]+", " ", value.lower()).strip()


def collect_terms(profile, fields):
    terms = []
    for field in fields:
        value = profile.get(field)
        values = value if isinstance(value, list) else [value]
        for item in values:
            if not isinstance(item, str):
                continue
            normalized = normalize_token(item)
            if normalized:
                terms.extend(term for term in normalized.split() if len(term) >= 2)
    return sorted(set(terms))[:24]


def build_query_views(profile):
    views = []
    for name, fields in QUERY_VIEW_FIELDS.items():
        terms = collect_terms(profile, fields)
        if terms:
            views.append({"name": name, "terms": terms})
    return views


def build_parser():
    parser = argparse.ArgumentParser(description="Build a sanitized Knudg task_profile.v0 from explicit current-work metadata.")
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build")
    build.add_argument("--input", required=True)
    build.add_argument("--with-query-views", action="store_true")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "build":
            profile = build_task_profile(load_json(args.input))
            if args.with_query_views:
                emit(
                    {
                        "schema_version": "task-profile-builder-result-v0",
                        "status": "ok",
                        "task_profile": profile,
                        "query_views": build_query_views(profile),
                    }
                )
            else:
                emit(profile)
        return 0
    except (TaskProfileError, json.JSONDecodeError, OSError):
        emit(
            {
                "schema_version": "task-profile-builder-result-v0",
                "status": "rejected",
                "reason": "input_rejected",
            }
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
