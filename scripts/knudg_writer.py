#!/usr/bin/env python3
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.card_payload import CardPayloadError, canonical_digest, canonicalize, validate_card_payload_v1


ALLOWED_FIELDS = {
    "schema_version",
    "request_id",
    "source_class",
    "outcome_type",
    "goal",
    "symptom",
    "environment",
    "context_fingerprint",
    "successful_path",
    "failed_paths",
    "known_unknowns",
    "scope_limits",
    "evidence_strength",
    "quality_state",
    "twist",
    "risk_flags",
}
REQUIRED_FIELDS = {
    "schema_version",
    "request_id",
    "source_class",
    "outcome_type",
    "goal",
    "symptom",
    "environment",
    "context_fingerprint",
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
    "transcript",
    "raw_transcript",
}
OUTCOME_TYPES = {"solved", "failed_only", "inconclusive", "unknown_clarified"}
EVIDENCE_STRENGTHS = {"single_session", "multi_session", "reproduced", "external_reference", "operator_judgment"}
QUALITY_STATES = {"unreviewed", "solved_once", "solved_many", "verified", "disputed"}
RISK_FLAGS = {
    "executable_advice",
    "mentions_urls",
    "mentions_packages",
    "mentions_repositories",
    "credential_risk",
    "billing_risk",
    "deletion_risk",
    "network_call_risk",
}
HIGH_RISK_FLAGS = {"executable_advice", "credential_risk", "billing_risk", "deletion_risk", "network_call_risk"}

RAW_PATTERNS = [
    re.compile(r"https?://", re.IGNORECASE),
    re.compile(r"\b[A-Z]:\\", re.IGNORECASE),
    re.compile(r"\b/Users/|/home/|/var/|/etc/", re.IGNORECASE),
    re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b"),
    re.compile(r"\b(?:password|secret|token|api[_-]?key|credential)\b", re.IGNORECASE),
    re.compile(r"\b(?:github\.com|gitlab\.com|bitbucket\.org)\b", re.IGNORECASE),
]


class WriterDraftError(ValueError):
    pass


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def emit(value):
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))


def reject_raw_string(path, value):
    if len(value) > 240:
        raise WriterDraftError(f"{path}: value exceeds local draft length limit")
    for pattern in RAW_PATTERNS:
        if pattern.search(value):
            raise WriterDraftError(f"{path}: raw/private-looking value is not allowed")


def walk_sanitized(path, value):
    if isinstance(value, str):
        reject_raw_string(path, value)
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            walk_sanitized(f"{path}[{index}]", item)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if key in FORBIDDEN_RAW_FIELDS:
                raise WriterDraftError(f"{path}: forbidden raw field present")
            walk_sanitized(f"{path}.{key}", item)
        return
    if isinstance(value, bool) or value is None or isinstance(value, int):
        return
    raise WriterDraftError(f"{path}: unsupported value type")


def require_object(name, value):
    if not isinstance(value, dict):
        raise WriterDraftError(f"{name}: expected object")


def require_string(name, value):
    if not isinstance(value, str) or not value:
        raise WriterDraftError(f"{name}: expected non-empty string")


def require_string_list(name, value, *, required_for_outcome=False):
    if value is None:
        if required_for_outcome:
            raise WriterDraftError(f"{name}: expected non-empty array")
        return []
    if not isinstance(value, list):
        raise WriterDraftError(f"{name}: expected array")
    for item in value:
        require_string(f"{name}[]", item)
    if required_for_outcome and not value:
        raise WriterDraftError(f"{name}: expected non-empty array")
    return value


def require_draft_input(draft):
    require_object("draft", draft)
    forbidden = sorted(set(draft) & FORBIDDEN_RAW_FIELDS)
    if forbidden:
        raise WriterDraftError("draft: forbidden raw fields present")
    extra = sorted(set(draft) - ALLOWED_FIELDS)
    if extra:
        raise WriterDraftError(f"draft: unknown field: {extra[0]}")
    missing = sorted(REQUIRED_FIELDS - set(draft))
    if missing:
        raise WriterDraftError(f"draft: missing required field: {missing[0]}")
    if draft["schema_version"] != "writer-draft-v0":
        raise WriterDraftError("draft.schema_version: invalid value")
    if draft["source_class"] != "synthetic":
        raise WriterDraftError("draft.source_class: only synthetic local drafts are enabled")
    if draft["outcome_type"] not in OUTCOME_TYPES:
        raise WriterDraftError("draft.outcome_type: invalid value")
    evidence = draft.get("evidence_strength", "single_session")
    if evidence not in EVIDENCE_STRENGTHS:
        raise WriterDraftError("draft.evidence_strength: invalid value")
    quality = draft.get("quality_state", "unreviewed")
    if quality not in QUALITY_STATES:
        raise WriterDraftError("draft.quality_state: invalid value")
    for field in ("request_id", "goal", "symptom"):
        require_string(f"draft.{field}", draft[field])
    for field in ("environment", "context_fingerprint"):
        require_object(f"draft.{field}", draft[field])
    risk_flags = draft.get("risk_flags", [])
    if not isinstance(risk_flags, list):
        raise WriterDraftError("draft.risk_flags: expected array")
    unknown_risks = sorted(set(risk_flags) - RISK_FLAGS)
    if unknown_risks:
        raise WriterDraftError(f"draft.risk_flags: unknown flag: {unknown_risks[0]}")
    walk_sanitized("draft", draft)
    return draft


def build_safety(risk_flags, evidence_strength):
    risk_set = set(risk_flags)
    safety_class = "high" if risk_set & HIGH_RISK_FLAGS else "medium" if risk_set else "low"
    verification_state = {
        "single_session": "single_session",
        "multi_session": "single_session",
        "reproduced": "reproduced",
        "external_reference": "external_reference",
        "operator_judgment": "unverified",
    }[evidence_strength]
    return {
        "safety_class": safety_class,
        "review_state": "cleared" if safety_class == "low" else "unreviewed",
        "executable_advice": "executable_advice" in risk_set,
        "mentions_urls": "mentions_urls" in risk_set,
        "mentions_packages": "mentions_packages" in risk_set,
        "mentions_repositories": "mentions_repositories" in risk_set,
        "credential_risk": "credential_risk" in risk_set,
        "billing_risk": "billing_risk" in risk_set,
        "deletion_risk": "deletion_risk" in risk_set,
        "network_call_risk": "network_call_risk" in risk_set,
        "verification_state": verification_state,
        "withheld_reason": None,
    }


def build_card_payload(draft):
    require_draft_input(draft)
    outcome = draft["outcome_type"]
    successful_path = require_string_list(
        "draft.successful_path",
        draft.get("successful_path"),
        required_for_outcome=outcome == "solved",
    )
    failed_paths = require_string_list(
        "draft.failed_paths",
        draft.get("failed_paths"),
        required_for_outcome=outcome == "failed_only",
    )
    known_unknowns = require_string_list(
        "draft.known_unknowns",
        draft.get("known_unknowns"),
        required_for_outcome=outcome == "unknown_clarified",
    )
    scope_limits = require_string_list("draft.scope_limits", draft.get("scope_limits"))
    if outcome == "failed_only":
        successful_path = None
    evidence_strength = draft.get("evidence_strength", "single_session")
    payload = {
        "outcome_type": outcome,
        "goal": draft["goal"],
        "symptom": draft["symptom"],
        "environment": draft["environment"],
        "context_fingerprint": draft["context_fingerprint"],
        "successful_path": successful_path,
        "failed_paths": failed_paths,
        "known_unknowns": known_unknowns,
        "scope_limits": scope_limits,
        "evidence_strength": evidence_strength,
        "quality_state": draft.get("quality_state", "unreviewed"),
        "safety": build_safety(draft.get("risk_flags", []), evidence_strength),
        "privacy": {
            "contains_personal_data": False,
            "source_class": "synthetic",
            "local_draft_only": True,
        },
        "provenance": {
            "source": "local synthetic writer draft",
            "request_id": draft["request_id"],
            "source_class": "synthetic",
        },
    }
    if draft.get("twist") is not None:
        payload["twist"] = draft["twist"]
    validate_card_payload_v1(payload)
    return payload


def draft_card(draft):
    payload = build_card_payload(draft)
    return {
        "ok": True,
        "status": "local_draft_only",
        "stored": False,
        "publication_enabled": False,
        "card_schema_version": 1,
        "digest": canonical_digest(payload),
        "canonical": canonicalize(payload),
        "payload": payload,
    }


def build_parser():
    parser = argparse.ArgumentParser(description="Knudg local synthetic writer draft helper.")
    sub = parser.add_subparsers(dest="command", required=True)
    draft = sub.add_parser("draft-card")
    draft.add_argument("--input", required=True)
    draft.add_argument("--canonical", action="store_true", help="Print only canonical card payload JSON.")
    draft.add_argument("--digest", action="store_true", help="Print only the card payload digest.")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "draft-card":
            result = draft_card(load_json(args.input))
            if args.digest:
                print(result["digest"])
            elif args.canonical:
                print(result["canonical"])
            else:
                emit(result)
        return 0
    except (WriterDraftError, CardPayloadError, json.JSONDecodeError) as exc:
        emit({"ok": False, "status": "payload_rejected", "stored": False, "publication_enabled": False, "error": str(exc)})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
