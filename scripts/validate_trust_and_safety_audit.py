#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "trust-and-safety-audit-v0.schema.json"
REQUIRED_EVENT_TYPES = {
    "case_opened",
    "identity_signal_reviewed",
    "submission_held",
    "account_warned",
    "account_rate_limited",
    "account_suspended",
    "account_banned",
    "appeal_opened",
    "reinstated",
    "artifact_revoked",
    "artifact_purged",
}
REQUIRED_FIELDS = {
    "case_id",
    "actor_id",
    "purpose",
    "reason_class",
    "decision_digest",
    "subject_ref",
    "appeal_ref",
    "created_at",
}
REQUIRED_COVERED_DOMAINS = {
    "technical_work",
    "personal_reasoning",
    "career_private",
    "place_service_experience",
    "public_experience_candidate",
    "public_aggregate_signal",
}
REQUIRED_FORBIDDEN_DISCLOSURES = {
    "business_dashboard",
    "actual_experience_storage",
    "raw_detail_escrow",
    "respondent_inquiry",
    "b2b_respondent_portal",
    "company_store_dashboard",
    "public_candidate_conversion",
    "public_card",
    "retrieval_panel",
    "export",
    "ranking_feature",
}
REQUIRED_BLOCKERS = {
    "PR-006",
    "TNS_ROLE_MODEL",
    "PROTECTED_FINGERPRINT_PROFILE",
    "APPEAL_RECOVERY_PATH",
    "NO_DISCLOSURE_NEGATIVE_TESTS",
}
RAW_AUDIT_EVENT_MARKERS = ("@", "http://", "https://", "127.0.0.1", "localhost", "\\", "/Users/", "/home/")


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def gate_failures(data):
    failures = []
    missing_domains = sorted(REQUIRED_COVERED_DOMAINS - set(data["covered_domains"]))
    if missing_domains:
        failures.append(f"missing covered domains: {', '.join(missing_domains)}")
    missing_events = sorted(REQUIRED_EVENT_TYPES - set(data["event_types"]))
    if missing_events:
        failures.append(f"missing event types: {', '.join(missing_events)}")
    missing_fields = sorted(REQUIRED_FIELDS - set(data["required_event_fields"]))
    if missing_fields:
        failures.append(f"missing required fields: {', '.join(missing_fields)}")
    missing_disclosures = sorted(REQUIRED_FORBIDDEN_DISCLOSURES - set(data["forbidden_disclosures"]))
    if missing_disclosures:
        failures.append(f"missing forbidden disclosures: {', '.join(missing_disclosures)}")
    missing_blockers = sorted(REQUIRED_BLOCKERS - set(data["blocked_until"]))
    if missing_blockers:
        failures.append(f"missing blockers: {', '.join(missing_blockers)}")
    audit_event = data["synthetic_audit_event_contract"]
    serialized_audit_event = json.dumps(audit_event, sort_keys=True)
    raw_markers = sorted(marker for marker in RAW_AUDIT_EVENT_MARKERS if marker in serialized_audit_event)
    if raw_markers:
        failures.append(f"synthetic audit event contains raw markers: {', '.join(raw_markers)}")
    if not audit_event["decision_digest"].startswith("sha256:"):
        failures.append("synthetic audit event decision digest must be sha256")
    synthetic_events = {item["event_type"]: item for item in data["synthetic_events"]}
    missing_synthetic_events = sorted(set(data["event_types"]) - set(synthetic_events))
    extra_synthetic_events = sorted(set(synthetic_events) - set(data["event_types"]))
    if missing_synthetic_events:
        failures.append(f"missing synthetic events: {', '.join(missing_synthetic_events)}")
    if extra_synthetic_events:
        failures.append(f"unknown synthetic events: {', '.join(extra_synthetic_events)}")
    for event_type, event in sorted(synthetic_events.items()):
        missing_event_fields = sorted(field for field in data["required_event_fields"] if field not in event)
        if missing_event_fields:
            failures.append(f"{event_type} missing synthetic event fields: {', '.join(missing_event_fields)}")
        serialized_event = json.dumps(event, sort_keys=True)
        event_raw_markers = sorted(marker for marker in RAW_AUDIT_EVENT_MARKERS if marker in serialized_event)
        if event_raw_markers:
            failures.append(f"{event_type} synthetic event contains raw markers: {', '.join(event_raw_markers)}")
    if data["real_identity_processing_enabled"]:
        failures.append("draft trust-and-safety audit cannot enable real identity processing")
    enabled_operations = sorted(name for name, value in data["operational_enablement"].items() if value)
    if enabled_operations:
        failures.append(f"draft trust-and-safety audit cannot enable operations: {', '.join(enabled_operations)}")
    if data["status"] == "accepted" and data["blocked_until"]:
        failures.append("accepted trust-and-safety audit gate must not have blockers")
    return failures


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate TNS-001 trust-and-safety audit fixture.")
    parser.add_argument("--input", required=True)
    args = parser.parse_args(argv)

    schema = load_json(SCHEMA_PATH)
    data = load_json(args.input)
    errors = sorted(Draft202012Validator(schema).iter_errors(data), key=lambda error: list(error.path))
    if errors:
        sanitized_errors = [
            {"path": "/".join(str(item) for item in error.path), "validator": error.validator}
            for error in errors
        ]
        print(json.dumps({"status": "rejected", "errors": sanitized_errors}, sort_keys=True))
        return 2
    failures = gate_failures(data)
    if failures:
        print(json.dumps({"status": "blocked", "blocking_gates": failures}, sort_keys=True))
        return 3
    print(json.dumps({"status": "ok", "real_identity_processing_enabled": data["real_identity_processing_enabled"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
