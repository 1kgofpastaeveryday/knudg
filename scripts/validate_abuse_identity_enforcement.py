#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "abuse-identity-enforcement-request-v0.schema.json"
REQUIRED_ACTIONS = {"warn", "rate_limit", "hold_for_review", "suspend", "ban", "appeal", "reinstate", "revoke", "purge"}
REQUIRED_GATES = {
    "ED-006",
    "TNS-001",
    "AUTHORIZATION_ROLE_MODEL",
    "HIGH_RISK_REVIEW_POLICY",
    "IDEMPOTENCY_WRITE_BEFORE_EFFECT",
    "ANTI_ENUMERATION_CONTRACT",
    "IDENTITY_MINIMIZATION_POLICY",
    "PROTECTED_FINGERPRINT_PROFILE",
    "AUDIT_DURABILITY",
    "NO_IDENTITY_DISCLOSURE_NEGATIVE_TESTS",
    "RAW_IDENTITY_RETENTION_PURGE_POLICY",
    "APPEAL_RECOVERY_PATH",
}
REQUIRED_HIGH_RISK_REVIEW_ACTIONS = {"suspend", "ban"}
REQUIRED_TWO_PERSON_REVIEW_ACTIONS = {"ban"}
REQUIRED_APPEAL_REF_ACTIONS = {"suspend", "ban"}
REQUIRED_AUDIT_EVENT_FIELDS = {
    "case_id",
    "actor_id",
    "purpose",
    "reason_class",
    "decision_digest",
    "subject_ref",
    "appeal_ref",
    "created_at",
}
REQUIRED_FORBIDDEN_OUTPUTS = {
    "submitter_identity",
    "raw_identity_values",
    "subject_row",
    "device_or_network_signal",
    "reidentification_hint",
    "protected_fingerprint",
    "raw_source_material",
    "source_metadata",
    "raw_moderation_evidence",
    "match_status",
    "account_identifier",
    "private_selection_status",
}
REQUIRED_PREFLIGHT_EVENTS = {"case_opened", "identity_signal_reviewed"}
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
FALSE_SURFACE_FLAGS = {
    "identity_processing_enabled",
    "real_enforcement_enabled",
    "real_ban_operations_enabled",
    "protected_fingerprint_creation_enabled",
    "subject_row_creation_enabled",
    "actual_experience_storage_enabled",
    "public_candidate_conversion_enabled",
    "public_serving_enabled",
    "b2b_delivery_enabled",
    "respondent_inquiry_enabled",
    "dashboard_enabled",
    "retrieval_enabled",
    "export_enabled",
    "ranking_enabled",
    "raw_detail_escrow_enabled",
}
FALSE_RESULT_FLAGS = {
    "performs_identity_processing",
    "stores_raw_identity",
    "creates_subject_row",
    "creates_protected_fingerprint",
    "discloses_match_status",
    "enforces_ban",
    "enforces_rate_limit",
    "creates_suspension",
    "opens_appeal_case",
    "opens_public_surface",
    "delivers_to_b2b",
    "serves_dashboard",
    "stores_raw_detail",
    "writes_audit_event",
}
RAW_MARKERS = (
    re.compile(r"@"),
    re.compile(r"\bhttps?://", re.IGNORECASE),
    re.compile(r"\b(?:localhost|127\.0\.0\.1|0\.0\.0\.0|::1)\b", re.IGNORECASE),
    re.compile(r"\b[A-Z]:\\", re.IGNORECASE),
    re.compile(r"\\\\[A-Za-z0-9_.-]+\\"),
    re.compile(r"\b20\d{2}-\d{2}-\d{2}\b"),
    re.compile(r"\b(?:password|secret|token|api[_-]?key|credential|private[_ -]?key)\b", re.IGNORECASE),
)


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sanitized_schema_errors(errors):
    return [{"path": "/".join(str(item) for item in error.path), "validator": error.validator} for error in errors]


def contains_raw_marker(data):
    text = json.dumps(data, sort_keys=True)
    return any(pattern.search(text) for pattern in RAW_MARKERS)


def gate_failures(data):
    failures = []
    missing_gates = sorted(REQUIRED_GATES - set(data["required_gates"]))
    if missing_gates:
        failures.append(f"missing required gates: {', '.join(missing_gates)}")

    requested_operation = data["requested_operation"]
    distinct_digest_pairs = [
        ("case_digest", "decision_digest"),
        ("case_digest", "idempotency_digest"),
        ("decision_digest", "idempotency_digest"),
    ]
    repeated_digest_pairs = [
        f"{left}/{right}"
        for left, right in distinct_digest_pairs
        if requested_operation[left] == requested_operation[right]
    ]
    if repeated_digest_pairs:
        failures.append(f"operation digests must be distinct: {', '.join(repeated_digest_pairs)}")

    authorization_model = data["authorization_model"]
    missing_high_risk = sorted(
        REQUIRED_HIGH_RISK_REVIEW_ACTIONS - set(authorization_model["high_risk_review_required_for"])
    )
    if missing_high_risk:
        failures.append(f"missing high-risk review actions: {', '.join(missing_high_risk)}")
    missing_two_person = sorted(
        REQUIRED_TWO_PERSON_REVIEW_ACTIONS - set(authorization_model["two_person_review_required_for"])
    )
    if missing_two_person:
        failures.append(f"missing two-person review actions: {', '.join(missing_two_person)}")
    if not authorization_model["actor_role_model_accepted"]:
        failures.append("actor role model is not accepted")

    missing_outputs = sorted(REQUIRED_FORBIDDEN_OUTPUTS - set(data["forbidden_outputs"]))
    if missing_outputs:
        failures.append(f"missing forbidden outputs: {', '.join(missing_outputs)}")
    missing_withheld = sorted(REQUIRED_FORBIDDEN_OUTPUTS - set(data["output_contract"]["withheld_outputs"]))
    if missing_withheld:
        failures.append(f"missing withheld outputs: {', '.join(missing_withheld)}")
    requested_forbidden = sorted(set(data["output_contract"]["requested_outputs"]) & REQUIRED_FORBIDDEN_OUTPUTS)
    if requested_forbidden:
        failures.append(f"requested forbidden outputs: {', '.join(requested_forbidden)}")

    identity_resolution = data["identity_resolution"]
    if identity_resolution["mode"] != "not_performed":
        failures.append("identity resolution cannot run in preflight")
    if identity_resolution["raw_identity_values"] != "forbidden_in_fixture":
        failures.append("raw identity values are forbidden")
    if identity_resolution["protected_fingerprint_created"]:
        failures.append("protected fingerprint cannot be created in preflight")
    if identity_resolution["subject_rows"] != "none" or identity_resolution["real_subject_rows_created"]:
        failures.append("real subject rows cannot be created in preflight")
    if identity_resolution["match_status_disclosure"] != "none":
        failures.append("match status cannot be disclosed")

    transition_actions = [item["action"] for item in data["enforcement_model"]["transitions"]]
    missing_transitions = sorted(REQUIRED_ACTIONS - set(transition_actions))
    if missing_transitions:
        failures.append(f"missing enforcement transitions: {', '.join(missing_transitions)}")
    duplicate_transitions = sorted({action for action in transition_actions if transition_actions.count(action) > 1})
    if duplicate_transitions:
        failures.append(f"duplicate enforcement transitions: {', '.join(duplicate_transitions)}")
    real_transitions = sorted(item["action"] for item in data["enforcement_model"]["transitions"] if item["real_effect_enabled"])
    if real_transitions:
        failures.append(f"enforcement transitions have real effects: {', '.join(real_transitions)}")

    audit_event_mapping = data["audit_event_mapping"]
    if audit_event_mapping["audit_event_write_enabled"]:
        failures.append("audit event writes cannot occur in preflight")
    missing_preflight_events = sorted(REQUIRED_PREFLIGHT_EVENTS - set(audit_event_mapping["preflight_required_events"]))
    if missing_preflight_events:
        failures.append(f"missing preflight audit events: {', '.join(missing_preflight_events)}")
    mapped_actions = [item["action"] for item in audit_event_mapping["transition_events"]]
    duplicate_mapped_actions = sorted({action for action in mapped_actions if mapped_actions.count(action) > 1})
    if duplicate_mapped_actions:
        failures.append(f"duplicate audit event mappings: {', '.join(duplicate_mapped_actions)}")
    missing_mapped_actions = sorted(REQUIRED_ACTIONS - set(mapped_actions))
    if missing_mapped_actions:
        failures.append(f"missing audit event mappings: {', '.join(missing_mapped_actions)}")
    mapped_events = {item["action"]: item["audit_event_type"] for item in audit_event_mapping["transition_events"]}
    incorrect_mapped_actions = sorted(
        action
        for action, expected_event_type in REQUIRED_AUDIT_EVENT_MAPPING.items()
        if mapped_events.get(action) != expected_event_type
    )
    if incorrect_mapped_actions:
        failures.append(f"incorrect audit event mappings: {', '.join(incorrect_mapped_actions)}")

    audit_event_contract = data["audit_event_contract"]
    missing_audit_fields = sorted(REQUIRED_AUDIT_EVENT_FIELDS - set(audit_event_contract["required_event_fields"]))
    if missing_audit_fields:
        failures.append(f"missing audit event fields: {', '.join(missing_audit_fields)}")
    if audit_event_contract["audit_write_mode"] == "disabled_preflight_only":
        failures.append("audit event writes are disabled")

    appeal_recovery = data["appeal_recovery"]
    missing_appeal_required_for = sorted({"suspend", "ban"} - set(appeal_recovery["required_for"]))
    if missing_appeal_required_for:
        failures.append(f"missing appeal recovery coverage: {', '.join(missing_appeal_required_for)}")
    if not appeal_recovery["appeal_path_required"] or not appeal_recovery["reinstatement_path_required"]:
        failures.append("appeal and reinstatement paths are required")
    accepted_paths = sorted(
        flag for flag in ["appeal_path_accepted", "reinstatement_path_accepted"] if appeal_recovery[flag]
    )
    if accepted_paths:
        failures.append(f"preflight cannot accept appeal recovery paths: {', '.join(accepted_paths)}")
    if not appeal_recovery["appeal_path_accepted"]:
        failures.append("appeal path is not accepted")
    if not appeal_recovery["reinstatement_path_accepted"]:
        failures.append("reinstatement path is not accepted")

    appeal_recovery_contract = data["appeal_recovery_contract"]
    missing_appeal_refs = sorted(
        REQUIRED_APPEAL_REF_ACTIONS - set(appeal_recovery_contract["appeal_ref_required_for"])
    )
    if missing_appeal_refs:
        failures.append(f"missing appeal refs for actions: {', '.join(missing_appeal_refs)}")

    enabled_surface_flags = sorted(flag for flag in FALSE_SURFACE_FLAGS if data["surface_enablement"][flag])
    if enabled_surface_flags:
        failures.append(f"abuse identity enforcement enables future surfaces: {', '.join(enabled_surface_flags)}")
    enabled_result_flags = sorted(flag for flag in FALSE_RESULT_FLAGS if data["result_contract"][flag])
    if enabled_result_flags:
        failures.append(f"abuse identity enforcement performs blocked effects: {', '.join(enabled_result_flags)}")
    if not data["surface_enablement"]["identity_processing_enabled"]:
        failures.append("identity processing is disabled")
    if not data["surface_enablement"]["real_enforcement_enabled"]:
        failures.append("ban enforcement is disabled")
    if contains_raw_marker(data):
        failures.append("abuse identity enforcement request contains raw markers")
    return failures


def result_payload(data, blockers):
    return {
        "status": "ok" if not blockers else "blocked",
        "enforcement_allowed": not blockers,
        "objective_item": data["objective_item"],
        "requested_action": data["requested_operation"]["action"],
        "reason_class": data["requested_operation"]["reason_class"],
        "command_effect": "preflight_only",
        "authorization_allowed": False,
        "anti_enumeration_contract_bound": True,
        "identity_minimization_contract_bound": True,
        "appeal_recovery_contract_bound": True,
        "performs_identity_processing": False,
        "stores_raw_identity": False,
        "creates_subject_row": False,
        "creates_protected_fingerprint": False,
        "discloses_match_status": False,
        "enforces_ban": False,
        "opens_public_surface": False,
        "delivers_to_b2b": False,
        "serves_dashboard": False,
        "stores_raw_detail": False,
        "writes_audit_event": False,
        "required_gates": sorted(REQUIRED_GATES),
        "blocking_gates": blockers,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate abuse identity enforcement preflight contract.")
    parser.add_argument("--input", required=True)
    args = parser.parse_args(argv)

    schema = load_json(SCHEMA_PATH)
    data = load_json(args.input)
    errors = sorted(Draft202012Validator(schema).iter_errors(data), key=lambda error: list(error.path))
    if errors:
        print(json.dumps({"status": "rejected", "errors": sanitized_schema_errors(errors)}, sort_keys=True))
        return 2
    blockers = gate_failures(data)
    print(json.dumps(result_payload(data, blockers), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
