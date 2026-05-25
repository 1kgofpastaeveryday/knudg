#!/usr/bin/env python3
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.card_payload import CardPayloadError
from scripts.knudg_synthetic_retrieval import SyntheticRetrievalError, load_json, search_synthetic
from scripts.knudg_writer import WriterDraftError, draft_card


RAW_PATTERNS = [
    re.compile(r"https?://", re.IGNORECASE),
    re.compile(r"\b[A-Z]:\\", re.IGNORECASE),
    re.compile(r"\b/Users/|/home/|/var/|/etc/", re.IGNORECASE),
    re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b"),
    re.compile(r"\b(?:password|secret|token|api[_-]?key|credential)\b", re.IGNORECASE),
    re.compile(r"\b(?:npm install|pip install|curl |rm -rf|git clone)\b", re.IGNORECASE),
]

TASK_PROFILE_INTENTS = {"debug", "implement", "review", "docs", "migration", "test", "research"}
TASK_PROFILE_EVENTS = {
    "task_start",
    "before_edit",
    "after_edit",
    "test_failure",
    "test_success",
    "tool_failure",
    "tool_success",
    "review",
    "approval_handoff",
    "before_write_candidate",
}
TASK_PROFILE_RISK_TAGS = {
    "auth",
    "database",
    "privacy",
    "security",
    "publication",
    "migration",
    "deployment",
    "billing",
    "destructive_action",
    "user_data",
    "public_api",
    "correctness",
}


class RoleVerdictError(ValueError):
    pass


def emit(value):
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))


def reject_unsafe_summary(value):
    if not isinstance(value, str) or not value:
        raise RoleVerdictError("reason_summary: expected non-empty string")
    if len(value) > 240:
        raise RoleVerdictError("reason_summary: exceeds length limit")
    for pattern in RAW_PATTERNS:
        if pattern.search(value):
            raise RoleVerdictError("reason_summary: raw, private, or executable-looking detail is not allowed")


def require_object(path, value):
    if not isinstance(value, dict):
        raise RoleVerdictError(f"{path}: expected object")


def require_verdict_input(value):
    require_object("verdict", value)
    if value.get("schema_version") != "knudg_role_verdict.v0":
        raise RoleVerdictError("verdict.schema_version: invalid value")
    for field in ("role", "status", "confidence", "risk", "reason_summary", "recommended_action"):
        if field not in value:
            raise RoleVerdictError(f"verdict.{field}: missing required field")
    reject_unsafe_summary(value["reason_summary"])
    return value


def reject_unsafe_profile_string(path, value, *, max_length=240):
    if not isinstance(value, str) or not value:
        raise RoleVerdictError(f"{path}: expected non-empty string")
    if len(value) > max_length:
        raise RoleVerdictError(f"{path}: exceeds length limit")
    for pattern in RAW_PATTERNS:
        if pattern.search(value):
            raise RoleVerdictError(f"{path}: raw or private-looking detail is not allowed")
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise RoleVerdictError(f"{path}: control characters are not allowed")
    return value


def require_string_array(path, value, *, allowed=None, max_items=20, item_max_length=120):
    if value is None:
        return []
    if not isinstance(value, list):
        raise RoleVerdictError(f"{path}: expected array")
    if len(value) > max_items:
        raise RoleVerdictError(f"{path}: too many items")
    seen = set()
    result = []
    for index, item in enumerate(value):
        reject_unsafe_profile_string(f"{path}[{index}]", item, max_length=item_max_length)
        if allowed is not None and item not in allowed:
            raise RoleVerdictError(f"{path}[{index}]: invalid value")
        if item in seen:
            raise RoleVerdictError(f"{path}: duplicate item")
        seen.add(item)
        result.append(item)
    return result


def require_task_profile(value):
    require_object("task_profile", value)
    allowed_fields = {
        "schema_version",
        "explicit_query",
        "intent",
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
    }
    extra = sorted(set(value) - allowed_fields)
    if extra:
        raise RoleVerdictError("task_profile: unknown fields are not allowed")
    if value.get("schema_version") != "task_profile.v0":
        raise RoleVerdictError("task_profile.schema_version: invalid value")
    if value.get("intent") not in TASK_PROFILE_INTENTS:
        raise RoleVerdictError("task_profile.intent: invalid value")
    reject_unsafe_profile_string("task_profile.explicit_query", value.get("explicit_query", ""), max_length=240)
    reject_unsafe_profile_string("task_profile.repo_shape_category", value.get("repo_shape_category", ""), max_length=80)
    events = require_string_array("task_profile.recent_event_kinds", value.get("recent_event_kinds"), allowed=TASK_PROFILE_EVENTS, max_items=12)
    if not events:
        raise RoleVerdictError("task_profile.recent_event_kinds: expected non-empty array")
    require_string_array("task_profile.subsystems", value.get("subsystems"), max_items=12, item_max_length=80)
    require_string_array("task_profile.safe_file_refs", value.get("safe_file_refs"), max_items=24, item_max_length=160)
    require_string_array("task_profile.symbols", value.get("symbols"), max_items=40)
    require_string_array("task_profile.error_fingerprints", value.get("error_fingerprints"), max_items=12)
    require_string_array("task_profile.public_packages", value.get("public_packages"), max_items=20)
    require_string_array("task_profile.public_frameworks_tools", value.get("public_frameworks_tools"), max_items=20, item_max_length=80)
    if value.get("language_runtime") is not None:
        reject_unsafe_profile_string("task_profile.language_runtime", value["language_runtime"], max_length=80)
    if value.get("coarse_os") is not None and value["coarse_os"] not in {"windows", "macos", "linux", "ios", "android", "web", "unknown"}:
        raise RoleVerdictError("task_profile.coarse_os: invalid value")
    require_string_array("task_profile.dependency_major_versions", value.get("dependency_major_versions"), max_items=20, item_max_length=80)
    require_string_array("task_profile.risk_tags", value.get("risk_tags"), allowed=TASK_PROFILE_RISK_TAGS, max_items=12)
    return value


def task_profile_to_synthetic_request(task_profile, *, tenant_id, namespace_ids, request_id, latency_budget_ms):
    profile = require_task_profile(task_profile)
    if not namespace_ids:
        raise RoleVerdictError("namespace_ids: expected at least one namespace")
    for namespace_id in namespace_ids:
        reject_unsafe_profile_string("namespace_ids[]", namespace_id, max_length=120)
    reject_unsafe_profile_string("tenant_id", tenant_id, max_length=120)
    reject_unsafe_profile_string("request_id", request_id, max_length=120)
    if latency_budget_ms < 1:
        raise RoleVerdictError("latency_budget_ms: expected positive integer")

    public_tools = []
    for field in ("public_frameworks_tools", "subsystems", "symbols"):
        public_tools.extend(profile.get(field) or [])
    public_tools = sorted(set(public_tools))[:20]

    error_signature = " ".join(profile.get("error_fingerprints") or []) or profile["explicit_query"]

    return {
        "schema_version": "synthetic-retrieval-v0",
        "request_id": request_id,
        "auth_context": {
            "tenant_id": tenant_id,
            "namespace_ids": namespace_ids,
            "revocation_epoch": 0,
        },
        "search_profile": {
            "schema_version": "search-profile-v0",
            "request_id": f"{request_id}:profile",
            "tenant_scope": "private",
            "namespace_ids": namespace_ids,
            "delivery_mode_requested": "retrieval_panel",
            "goal_category": profile["explicit_query"],
            "sanitized_error_signature": error_signature,
            "public_packages_claimed": profile.get("public_packages") or [],
            "public_frameworks_tools_claimed": public_tools,
            "language_runtime": profile.get("language_runtime", "unknown"),
            "coarse_os": profile.get("coarse_os", "unknown"),
            "dependency_major_versions": profile.get("dependency_major_versions") or [],
            "repo_shape_category": profile["repo_shape_category"],
            "risk_flags_claimed": profile.get("risk_tags") or [],
            "latency_budget_ms": latency_budget_ms,
            "privacy_budget_class_claimed": "private_team",
        },
    }


def verdict(role, status, confidence, risk, reason_summary, recommended_action, *, refs=None, suppressed_detail="none"):
    reject_unsafe_summary(reason_summary)
    result = {
        "schema_version": "knudg_role_verdict.v0",
        "role": role,
        "status": status,
        "confidence": confidence,
        "risk": risk,
        "reason_summary": reason_summary,
        "recommended_action": recommended_action,
        "suppressed_detail": suppressed_detail,
    }
    if refs:
        result["refs"] = refs
    return result


def searcher_synthetic(request, corpus, min_score):
    response = search_synthetic(request, corpus, min_score)
    if response.get("decision") != "cards_found":
        return verdict(
            "searcher",
            "abstain",
            "none",
            "none",
            "No displayable authorized synthetic match.",
            "do_nothing",
            suppressed_detail="none",
        )
    card_refs = [f"{card['card_id']}:{card['card_version_id']}" for card in response["cards"]]
    risk = "high" if any(card.get("withheld") for card in response["cards"]) else "low"
    suppressed_detail = "high_risk" if risk == "high" else "none"
    return verdict(
        "searcher",
        "suggestion_available",
        "medium",
        risk,
        "Displayable retrieval-panel metadata is available.",
        "offer_retrieval_panel",
        refs={"card_refs": card_refs, "panel_ref": f"synthetic:{request['request_id']}"},
        suppressed_detail=suppressed_detail,
    )


def writer_local(draft):
    result = draft_card(draft)
    digest = result["digest"].split(":")[-1][:24]
    risk = "high" if result["payload"]["safety"]["safety_class"] == "high" else "low"
    suppressed_detail = "high_risk" if risk == "high" else "none"
    return verdict(
        "writer",
        "draft_candidate_possible",
        "medium",
        risk,
        "A local synthetic writer draft can be offered.",
        "offer_writer_draft",
        refs={"draft_ref": f"synthetic-draft:{digest}"},
        suppressed_detail=suppressed_detail,
    )


def nudger_from_verdict(input_verdict):
    source = require_verdict_input(input_verdict)
    if source["status"] in {"abstain", "degraded"}:
        return verdict("nudger", "abstain", "none", "none", "Nothing worth surfacing now.", "do_nothing")
    if source["confidence"] not in {"medium", "high"}:
        return verdict("nudger", "abstain", "none", "none", "Suggestion confidence is too low.", "do_nothing")
    if source["risk"] in {"high", "privacy", "security"} or source.get("suppressed_detail") in {"raw_or_private", "executable", "high_risk", "not_authorized"}:
        return verdict("nudger", "abstain", "none", "none", "Suggestion is not low-noise enough to surface.", "do_nothing")
    action = source["recommended_action"]
    if action not in {"offer_retrieval_panel", "offer_writer_draft", "offer_approval_handoff", "ask_user_before_continuing"}:
        return verdict("nudger", "abstain", "none", "none", "No safe user-facing offer is available.", "do_nothing")
    status = source["status"]
    refs = source.get("refs")
    return verdict(
        "nudger",
        status,
        source["confidence"],
        source["risk"],
        "A low-noise Knudg offer is available.",
        action,
        refs=refs,
        suppressed_detail="none",
    )


def searcher_nudge_synthetic(request, corpus, min_score):
    return nudger_from_verdict(searcher_synthetic(request, corpus, min_score))


def searcher_profile_synthetic(task_profile, corpus, min_score, *, tenant_id, namespace_ids, request_id, latency_budget_ms):
    request = task_profile_to_synthetic_request(
        task_profile,
        tenant_id=tenant_id,
        namespace_ids=namespace_ids,
        request_id=request_id,
        latency_budget_ms=latency_budget_ms,
    )
    return searcher_synthetic(request, corpus, min_score)


def searcher_profile_nudge_synthetic(task_profile, corpus, min_score, *, tenant_id, namespace_ids, request_id, latency_budget_ms):
    return nudger_from_verdict(
        searcher_profile_synthetic(
            task_profile,
            corpus,
            min_score,
            tenant_id=tenant_id,
            namespace_ids=namespace_ids,
            request_id=request_id,
            latency_budget_ms=latency_budget_ms,
        )
    )


def writer_nudge_local(draft):
    return nudger_from_verdict(writer_local(draft))


def local_dogfood(draft, task_profile, *, tenant_id, namespace_ids, request_id, min_score, latency_budget_ms):
    writer_result = draft_card(draft)
    draft_digest = writer_result["digest"]
    corpus = {
        "schema_version": "synthetic-corpus-v0",
        "cards": [
            {
                "tenant_id": tenant_id,
                "namespace_id": namespace_ids[0],
                "card_id": "card_001",
                "card_version_id": "version_001",
                "status": "approved_private",
                "source_class": "synthetic",
                "payload": writer_result["payload"],
            }
        ],
        "revocation_tombstones": [],
    }
    verdict_payload = searcher_profile_nudge_synthetic(
        task_profile,
        corpus,
        min_score,
        tenant_id=tenant_id,
        namespace_ids=namespace_ids,
        request_id=request_id,
        latency_budget_ms=latency_budget_ms,
    )
    fixture_ref_material = json.dumps(
        {
            "draft_digest": draft_digest,
            "tenant_id": tenant_id,
            "namespace_ids": namespace_ids,
            "request_id": request_id,
            "card_ref": "card_001:version_001",
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return {
        "schema_version": "local-dogfood-result-v0",
        "status": "ok",
        "stored": False,
        "protected_data_serving_enabled": False,
        "publication_enabled": False,
        "role_verdict": verdict_payload,
        "refs": {
            "draft_digest": draft_digest,
            "corpus_ref": "synthetic-corpus:" + hashlib.sha256(fixture_ref_material.encode("utf-8")).hexdigest()[:24],
            "card_ref": "card_001:version_001",
        },
    }


def build_parser():
    parser = argparse.ArgumentParser(description="Knudg summoned role wrappers.")
    sub = parser.add_subparsers(dest="command", required=True)
    searcher = sub.add_parser("searcher-synthetic")
    searcher.add_argument("--input", required=True)
    searcher.add_argument("--corpus", required=True)
    searcher.add_argument("--min-score", type=int, default=2)
    searcher_profile = sub.add_parser("searcher-profile-synthetic")
    searcher_profile.add_argument("--input", required=True)
    searcher_profile.add_argument("--corpus", required=True)
    searcher_profile.add_argument("--min-score", type=int, default=2)
    searcher_profile.add_argument("--tenant-id", default="tenant_local")
    searcher_profile.add_argument("--namespace-id", action="append")
    searcher_profile.add_argument("--request-id", default="task_profile_req_000001")
    searcher_profile.add_argument("--latency-budget-ms", type=int, default=250)
    searcher_nudge = sub.add_parser("searcher-nudge-synthetic")
    searcher_nudge.add_argument("--input", required=True)
    searcher_nudge.add_argument("--corpus", required=True)
    searcher_nudge.add_argument("--min-score", type=int, default=2)
    searcher_profile_nudge = sub.add_parser("searcher-profile-nudge-synthetic")
    searcher_profile_nudge.add_argument("--input", required=True)
    searcher_profile_nudge.add_argument("--corpus", required=True)
    searcher_profile_nudge.add_argument("--min-score", type=int, default=2)
    searcher_profile_nudge.add_argument("--tenant-id", default="tenant_local")
    searcher_profile_nudge.add_argument("--namespace-id", action="append")
    searcher_profile_nudge.add_argument("--request-id", default="task_profile_req_000001")
    searcher_profile_nudge.add_argument("--latency-budget-ms", type=int, default=250)
    writer = sub.add_parser("writer-local")
    writer.add_argument("--input", required=True)
    writer_nudge = sub.add_parser("writer-nudge-local")
    writer_nudge.add_argument("--input", required=True)
    dogfood = sub.add_parser("local-dogfood")
    dogfood.add_argument("--draft-input", required=True)
    dogfood.add_argument("--task-profile-input", required=True)
    dogfood.add_argument("--tenant-id", default="tenant_local")
    dogfood.add_argument("--namespace-id", action="append")
    dogfood.add_argument("--request-id", default="local_dogfood_req_000001")
    dogfood.add_argument("--min-score", type=int, default=2)
    dogfood.add_argument("--latency-budget-ms", type=int, default=250)
    nudger = sub.add_parser("nudger-from-verdict")
    nudger.add_argument("--input", required=True)
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "searcher-synthetic":
            if args.min_score < 1:
                raise RoleVerdictError("--min-score must be positive")
            emit(searcher_synthetic(load_json(args.input), load_json(args.corpus), args.min_score))
        elif args.command == "searcher-profile-synthetic":
            if args.min_score < 1:
                raise RoleVerdictError("--min-score must be positive")
            emit(
                searcher_profile_synthetic(
                    load_json(args.input),
                    load_json(args.corpus),
                    args.min_score,
                    tenant_id=args.tenant_id,
                    namespace_ids=args.namespace_id or ["ns_local"],
                    request_id=args.request_id,
                    latency_budget_ms=args.latency_budget_ms,
                )
            )
        elif args.command == "searcher-nudge-synthetic":
            if args.min_score < 1:
                raise RoleVerdictError("--min-score must be positive")
            emit(searcher_nudge_synthetic(load_json(args.input), load_json(args.corpus), args.min_score))
        elif args.command == "searcher-profile-nudge-synthetic":
            if args.min_score < 1:
                raise RoleVerdictError("--min-score must be positive")
            emit(
                searcher_profile_nudge_synthetic(
                    load_json(args.input),
                    load_json(args.corpus),
                    args.min_score,
                    tenant_id=args.tenant_id,
                    namespace_ids=args.namespace_id or ["ns_local"],
                    request_id=args.request_id,
                    latency_budget_ms=args.latency_budget_ms,
                )
            )
        elif args.command == "writer-local":
            emit(writer_local(load_json(args.input)))
        elif args.command == "writer-nudge-local":
            emit(writer_nudge_local(load_json(args.input)))
        elif args.command == "local-dogfood":
            if args.min_score < 1:
                raise RoleVerdictError("--min-score must be positive")
            emit(
                local_dogfood(
                    load_json(args.draft_input),
                    load_json(args.task_profile_input),
                    tenant_id=args.tenant_id,
                    namespace_ids=args.namespace_id or ["ns_local"],
                    request_id=args.request_id,
                    min_score=args.min_score,
                    latency_budget_ms=args.latency_budget_ms,
                )
            )
        elif args.command == "nudger-from-verdict":
            emit(nudger_from_verdict(load_json(args.input)))
        return 0
    except (RoleVerdictError, SyntheticRetrievalError, WriterDraftError, CardPayloadError, json.JSONDecodeError):
        role = {
            "searcher-synthetic": "searcher",
            "searcher-profile-synthetic": "searcher",
            "searcher-nudge-synthetic": "nudger",
            "searcher-profile-nudge-synthetic": "nudger",
            "writer-local": "writer",
            "writer-nudge-local": "nudger",
            "local-dogfood": "nudger",
            "nudger-from-verdict": "nudger",
        }.get(getattr(args, "command", ""), "nudger")
        emit(
            verdict(
                role,
                "degraded",
                "none",
                "none",
                "Role wrapper could not produce a safe verdict.",
                "do_nothing",
                suppressed_detail="raw_or_private",
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
