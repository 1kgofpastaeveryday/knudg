#!/usr/bin/env python3
import argparse
import json
import re
import sys
from pathlib import Path


PRIVATE_SEARCH_FIELDS = {
    "schema_version",
    "request_id",
    "tenant_scope",
    "namespace_ids",
    "delivery_mode_requested",
    "goal_category",
    "sanitized_error_signature",
    "error_signature_hash",
    "public_packages_claimed",
    "public_frameworks_tools_claimed",
    "language_runtime",
    "coarse_os",
    "dependency_major_versions",
    "repo_shape_category",
    "risk_flags_claimed",
    "latency_budget_ms",
    "privacy_budget_class_claimed",
}

PRIVATE_REQUIRED_FIELDS = {
    "schema_version",
    "request_id",
    "tenant_scope",
    "namespace_ids",
    "delivery_mode_requested",
    "goal_category",
    "latency_budget_ms",
}

PUBLIC_SEARCH_FIELDS = {
    "schema_version",
    "request_id",
    "goal_category",
    "public_tool_family",
    "public_framework_family",
    "public_package_family",
    "coarse_os",
    "language_runtime",
    "dependency_major_versions",
    "bounded_public_error_category",
    "delivery_mode_requested",
}

PUBLIC_FORBIDDEN_FIELDS = PRIVATE_SEARCH_FIELDS - PUBLIC_SEARCH_FIELDS | {
    "tenant_scope",
    "namespace_ids",
    "error_signature_hash",
    "card_id",
    "card_version_id",
    "internal_card_id",
    "fingerprint",
}

FORBIDDEN_RAW_FIELDS = {
    "raw_log",
    "raw_logs",
    "stack_trace",
    "full_stack_trace",
    "absolute_path",
    "username",
    "hostname",
    "private_repo_name",
    "customer_name",
    "secret",
    "token",
    "file_contents",
    "command_output",
}

DELIVERY_MODES = {"bootstrap", "retrieval_panel", "inline_hint", "no_suggestion"}
TENANT_SCOPES = {"private", "team", "enterprise"}
ABSTENTION_REASONS = {
    "low_confidence",
    "no_authorized_match",
    "safety_gate",
    "stale_index",
    "rate_limited",
    "service_degraded",
    "none",
}

RAW_PATTERNS = [
    re.compile(r"https?://", re.IGNORECASE),
    re.compile(r"\b[A-Z]:\\", re.IGNORECASE),
    re.compile(r"\b/Users/|/home/|/var/|/etc/", re.IGNORECASE),
    re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b"),
    re.compile(r"\b(?:password|secret|token|api[_-]?key|credential)\b", re.IGNORECASE),
    re.compile(r"\b(?:github\.com|gitlab\.com|bitbucket\.org)\b", re.IGNORECASE),
]


class RetrievalError(ValueError):
    pass


class PublicRequestRejected(ValueError):
    pass


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def emit_json(value):
    print(json.dumps(value, sort_keys=True))


def reject_raw_string(path, value):
    if len(value) > 240:
        raise RetrievalError(f"{path}: value exceeds bounded profile length")
    for pattern in RAW_PATTERNS:
        if pattern.search(value):
            raise RetrievalError(f"{path}: raw/private-looking value is not allowed")


def walk_profile(path, value):
    if isinstance(value, str):
        reject_raw_string(path, value)
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            walk_profile(f"{path}[{index}]", item)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            walk_profile(f"{path}.{key}", item)


def require_object(profile):
    if not isinstance(profile, dict):
        raise RetrievalError("profile: expected object")


def require_enum(path, value, allowed):
    if value not in allowed:
        raise RetrievalError(f"{path}: invalid value")


def require_no_forbidden_raw_fields(profile):
    forbidden = sorted(set(profile) & FORBIDDEN_RAW_FIELDS)
    if forbidden:
        raise RetrievalError(f"profile: forbidden raw fields present: {', '.join(forbidden)}")


def require_private_profile(profile):
    require_object(profile)
    require_no_forbidden_raw_fields(profile)
    extra = sorted(set(profile) - PRIVATE_SEARCH_FIELDS)
    if extra:
        raise RetrievalError(f"profile: unknown fields ({len(extra)} field(s))")
    missing = sorted(PRIVATE_REQUIRED_FIELDS - set(profile))
    if missing:
        raise RetrievalError(f"profile: missing required fields: {', '.join(missing)}")
    require_enum("profile.tenant_scope", profile["tenant_scope"], TENANT_SCOPES)
    require_enum("profile.delivery_mode_requested", profile["delivery_mode_requested"], DELIVERY_MODES)
    if not isinstance(profile["namespace_ids"], list) or not profile["namespace_ids"]:
        raise RetrievalError("profile.namespace_ids: expected non-empty array")
    if not isinstance(profile["latency_budget_ms"], int) or profile["latency_budget_ms"] < 1:
        raise RetrievalError("profile.latency_budget_ms: expected positive integer")
    walk_profile("profile", profile)
    return profile


def require_public_request(profile):
    try:
        require_object(profile)
        require_no_forbidden_raw_fields(profile)
        forbidden = sorted(set(profile) & PUBLIC_FORBIDDEN_FIELDS)
        if forbidden:
            raise PublicRequestRejected()
        extra = sorted(set(profile) - PUBLIC_SEARCH_FIELDS)
        if extra:
            raise PublicRequestRejected()
        missing = sorted({"schema_version", "request_id", "goal_category", "delivery_mode_requested"} - set(profile))
        if missing:
            raise PublicRequestRejected()
        if profile["delivery_mode_requested"] != "retrieval_panel":
            raise PublicRequestRejected()
        walk_profile("public_request", profile)
    except RetrievalError as exc:
        raise PublicRequestRejected() from exc
    return profile


def no_suggestion(*, audience, delivery_mode_requested, reason="service_degraded", latency_budget_ms=None):
    if audience == "public":
        return {
            "decision": "no_suggestion",
            "delivery_mode": "no_suggestion",
            "abstention_reason": "generic_abstention",
            "threshold_version": "public-threshold-unconfigured",
            "served_from": "none",
            "latency_budget_ms": latency_budget_ms,
            "cards": [],
        }
    require_enum("abstention_reason", reason, ABSTENTION_REASONS)
    mode = delivery_mode_requested if delivery_mode_requested in {"bootstrap", "retrieval_panel"} else "no_suggestion"
    return {
        "decision": "no_suggestion",
        "delivery_mode": "no_suggestion" if reason != "none" else mode,
        "abstention_reason": reason,
        "consent_state": "withheld",
        "served_from": "none",
        "latency_budget_ms": latency_budget_ms,
        "cards": [],
    }


def search_similar(profile):
    require_private_profile(profile)
    return no_suggestion(
        audience="private",
        delivery_mode_requested=profile["delivery_mode_requested"],
        reason="service_degraded",
        latency_budget_ms=profile["latency_budget_ms"],
    )


def public_search(profile):
    try:
        require_public_request(profile)
    except PublicRequestRejected:
        return no_suggestion(
            audience="public",
            delivery_mode_requested="retrieval_panel",
            latency_budget_ms=None,
        )
    return no_suggestion(
        audience="public",
        delivery_mode_requested=profile["delivery_mode_requested"],
        latency_budget_ms=None,
    )


def mcp_tools_list(request_id):
    properties = {field: {} for field in sorted(PRIVATE_SEARCH_FIELDS)}
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "tools": [
                {
                    "name": "search_similar",
                    "description": "Validate a sanitized SearchProfile and abstain until retrieval backend is configured.",
                    "inputSchema": {
                        "type": "object",
                        "properties": properties,
                        "required": sorted(PRIVATE_REQUIRED_FIELDS),
                        "additionalProperties": False,
                    },
                }
            ]
        },
    }


def mcp_error(request_id, code, message):
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def mcp_response(request):
    if not isinstance(request, dict) or request.get("jsonrpc") != "2.0" or "method" not in request:
        return mcp_error(None, -32600, "Invalid Request")
    if "id" not in request:
        return None
    request_id = request.get("id")
    method = request["method"]
    if method == "tools/list":
        return mcp_tools_list(request_id)
    if method != "tools/call":
        return mcp_error(request_id, -32601, "Method not found")
    params = request.get("params") or {}
    if params.get("name") != "search_similar":
        return mcp_error(request_id, -32601, "Method not found")
    try:
        result = search_similar(params.get("arguments") or {})
    except RetrievalError:
        result = no_suggestion(audience="private", delivery_mode_requested="no_suggestion", reason="service_degraded")
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "content": [{"type": "text", "text": json.dumps(result, sort_keys=True)}],
            "isError": False,
        },
    }


def build_parser():
    parser = argparse.ArgumentParser(description="Knudg retrieval/API/MCP abstention skeleton.")
    sub = parser.add_subparsers(dest="command", required=True)
    private = sub.add_parser("search-similar")
    private.add_argument("--input", required=True)
    public = sub.add_parser("public-search")
    public.add_argument("--input", required=True)
    mcp = sub.add_parser("mcp-once")
    mcp.add_argument("--input", required=True)
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        payload = load_json(args.input)
        if args.command == "search-similar":
            emit_json(search_similar(payload))
        elif args.command == "public-search":
            emit_json(public_search(payload))
        else:
            response = mcp_response(payload)
            if response is not None:
                emit_json(response)
        return 0
    except (RetrievalError, json.JSONDecodeError) as exc:
        emit_json({"decision": "no_suggestion", "delivery_mode": "no_suggestion", "abstention_reason": "payload_rejected", "error": str(exc), "cards": []})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
