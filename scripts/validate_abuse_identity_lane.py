#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "abuse-identity-lane-v0.schema.json"
REQUIRED_ACTIONS = {"warn", "rate_limit", "hold_for_review", "suspend", "ban", "appeal", "reinstate", "revoke", "purge"}
KNOWN_AUDIT_EVENT_TYPES = {
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
REQUIRED_PREFLIGHT_AUDIT_EVENTS = {"case_opened", "identity_signal_reviewed"}
REQUIRED_AUDIT_EVENT_MAPPING = {
    "warn": "account_warned",
    "rate_limit": "account_rate_limited",
    "hold_for_review": "submission_held",
    "suspend": "account_suspended",
    "ban": "account_banned",
    "appeal": "appeal_opened",
    "reinstate": "reinstated",
    "revoke": "artifact_revoked",
    "purge": "artifact_purged",
}
REQUIRED_FORBIDDEN_SURFACES = {
    "retrieval",
    "actual_experience_storage",
    "raw_detail_escrow",
    "public_card",
    "aggregate_report",
    "b2b_dashboard",
    "b2b_respondent_portal",
    "company_store_dashboard",
    "public_candidate_conversion",
    "respondent_inquiry",
    "export",
    "ranking_feature",
}
RAW_MARKERS = ("@", "http://", "https://", "127.0.0.1", "localhost", "\\", "/Users/", "/home/")
REQUIRED_AUDIT_REQUIREMENTS = {
    "case_reason",
    "purpose_binding",
    "actor_identity",
    "decision_digest",
    "appeal_path",
    "reinstatement_path",
    "no_b2b_identity_disclosure",
}


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def gate_failures(data):
    failures = []
    serialized = json.dumps(data, sort_keys=True)
    raw_markers = sorted(marker for marker in RAW_MARKERS if marker in serialized)
    if raw_markers:
        failures.append(f"abuse identity lane contains raw markers: {', '.join(raw_markers)}")
    missing_actions = sorted(REQUIRED_ACTIONS - set(data["allowed_actions"]))
    if missing_actions:
        failures.append(f"missing actions: {', '.join(missing_actions)}")
    transition_actions = {item["action"] for item in data["operation_model"]["transitions"]}
    missing_transitions = sorted(REQUIRED_ACTIONS - transition_actions)
    if missing_transitions:
        failures.append(f"missing operation transitions: {', '.join(missing_transitions)}")
    real_transitions = sorted(item["action"] for item in data["operation_model"]["transitions"] if item["real_effect_enabled"])
    if real_transitions:
        failures.append(f"operation transitions have real effects: {', '.join(real_transitions)}")
    audit_event_mapping = data["audit_event_mapping"]
    missing_preflight_events = sorted(
        REQUIRED_PREFLIGHT_AUDIT_EVENTS - set(audit_event_mapping["preflight_required_events"])
    )
    if missing_preflight_events:
        failures.append(f"missing preflight audit events: {', '.join(missing_preflight_events)}")
    unknown_preflight_events = sorted(set(audit_event_mapping["preflight_required_events"]) - KNOWN_AUDIT_EVENT_TYPES)
    if unknown_preflight_events:
        failures.append(f"unknown preflight audit events: {', '.join(unknown_preflight_events)}")
    transition_event_items = audit_event_mapping["transition_events"]
    mapped_actions = [item["action"] for item in transition_event_items]
    duplicate_mapped_actions = sorted({action for action in mapped_actions if mapped_actions.count(action) > 1})
    if duplicate_mapped_actions:
        failures.append(f"duplicate audit event mappings: {', '.join(duplicate_mapped_actions)}")
    mapped_action_set = set(mapped_actions)
    missing_mapped_actions = sorted(REQUIRED_ACTIONS - mapped_action_set)
    if missing_mapped_actions:
        failures.append(f"missing audit event mappings: {', '.join(missing_mapped_actions)}")
    extra_mapped_actions = sorted(mapped_action_set - REQUIRED_ACTIONS)
    if extra_mapped_actions:
        failures.append(f"unknown audit event mapping actions: {', '.join(extra_mapped_actions)}")
    mapped_events = {item["action"]: item["audit_event_type"] for item in transition_event_items}
    unknown_mapped_events = sorted(
        event_type for event_type in mapped_events.values() if event_type not in KNOWN_AUDIT_EVENT_TYPES
    )
    if unknown_mapped_events:
        failures.append(f"unknown audit event types: {', '.join(unknown_mapped_events)}")
    incorrect_mapped_actions = sorted(
        action
        for action, expected_event_type in REQUIRED_AUDIT_EVENT_MAPPING.items()
        if mapped_events.get(action) != expected_event_type
    )
    if incorrect_mapped_actions:
        failures.append(f"incorrect audit event mappings: {', '.join(incorrect_mapped_actions)}")
    real_mapped_actions = sorted(set(real_transitions) & mapped_action_set)
    if real_mapped_actions:
        failures.append(f"mapped transitions have real effects: {', '.join(real_mapped_actions)}")
    missing_surfaces = sorted(REQUIRED_FORBIDDEN_SURFACES - set(data["forbidden_surfaces"]))
    if missing_surfaces:
        failures.append(f"missing forbidden surfaces: {', '.join(missing_surfaces)}")
    missing_audit = sorted(REQUIRED_AUDIT_REQUIREMENTS - set(data["audit_requirements"]))
    if missing_audit:
        failures.append(f"missing audit requirements: {', '.join(missing_audit)}")
    if data["status"] != "active" and data["identity_storage"]["real_subject_rows"] != "none":
        failures.append("draft abuse identity lane cannot create real subject rows")
    if data["status"] == "active" and data["blocked_until"]:
        failures.append("active abuse identity lane must not have blockers")
    return failures


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate abuse identity lane fixture.")
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
    print(json.dumps({"status": "ok", "mode": data["operation_model"]["mode"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
