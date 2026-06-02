#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "raw-detail-escrow-request-v0.schema.json"
REQUIRED_GATES = {
    "PR-003",
    "PR-006",
    "PROTECTED_DATA_DURABILITY",
    "PURGE_PATH",
    "ESCROW_TTL_POLICY",
    "REVIEWER_ACCESS_POLICY",
    "NO_RAW_ECHO_NEGATIVE_TESTS",
    "KEY_PROFILE_ACCEPTED",
    "RAW_DETAIL_PURPOSE_BINDING",
    "CRYPTOGRAPHIC_ENVELOPE_PROFILE",
    "ACCESS_LEASE_POLICY",
    "RESTORE_BACKUP_PURGE_POLICY",
    "AUDIT_DIGEST_ONLY_POLICY",
}
REQUIRED_REVIEW_REASONS = {"human_review_required", "legal_review_required", "safety_review_required"}
REQUIRED_DIGEST_FIELDS = {"source_record_digest", "redacted_artifact_digest", "raw_payload_digest"}
REQUIRED_FORBIDDEN_OUTPUTS = {
    "submitter_identity",
    "raw_source_material",
    "raw_review_body",
    "device_or_network_signal",
    "reidentification_hint",
    "protected_fingerprint",
    "private_selection_status",
    "staff_identity",
    "source_metadata",
    "raw_moderation_evidence",
    "escrow_ciphertext",
    "escrow_handle",
    "escrow_key_material",
    "reviewer_private_note",
    "non_public_operational_detail",
}
FALSE_SURFACE_FLAGS = {
    "raw_detail_escrow_enabled",
    "escrow_write_enabled",
    "encrypted_blob_storage_enabled",
    "reviewer_access_enabled",
    "decrypt_operation_enabled",
    "reviewer_lease_creation_enabled",
    "model_input_includes_raw",
    "validator_errors_include_raw",
    "audit_or_client_response_includes_raw",
    "real_data_ingest_enabled",
    "public_serving_enabled",
    "b2b_delivery_enabled",
    "identity_processing_enabled",
    "dashboard_enabled",
    "retrieval_enabled",
    "export_enabled",
    "ranking_enabled",
}
FALSE_RESULT_FLAGS = {
    "stores_raw_detail",
    "creates_escrow_handle",
    "creates_encrypted_blob",
    "stores_key_material",
    "opens_reviewer_access",
    "creates_reviewer_lease",
    "decrypts_escrow",
    "sends_raw_to_model_input",
    "echoes_raw_in_validator_errors",
    "echoes_raw_in_audit_or_client_response",
    "opens_public_surface",
    "delivers_to_b2b",
    "serves_dashboard",
    "performs_identity_processing",
    "makes_retrievable",
    "exports_raw_detail",
    "writes_audit_event",
}
FALSE_STORAGE_FLAGS = {
    "durable_storage_enabled",
    "backup_retention_enabled",
    "restore_quarantine_enabled",
    "access_audit_enabled",
}
RAW_MARKERS = (
    re.compile(r"@"),
    re.compile(r"\bhttps?://", re.IGNORECASE),
    re.compile(r"\b(?:localhost|127\.0\.0\.1|0\.0\.0\.0|::1)\b", re.IGNORECASE),
    re.compile(r"\b[A-Z]:\\", re.IGNORECASE),
    re.compile(r"\\\\[A-Za-z0-9_.-]+\\"),
    re.compile(r"/(?:Users|home|var|tmp)/", re.IGNORECASE),
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

    missing_outputs = sorted(REQUIRED_FORBIDDEN_OUTPUTS - set(data["forbidden_outputs"]))
    if missing_outputs:
        failures.append(f"missing forbidden outputs: {', '.join(missing_outputs)}")
    missing_withheld = sorted(REQUIRED_FORBIDDEN_OUTPUTS - set(data["output_contract"]["withheld_outputs"]))
    if missing_withheld:
        failures.append(f"missing withheld outputs: {', '.join(missing_withheld)}")
    requested_forbidden = sorted(set(data["output_contract"]["requested_outputs"]) & REQUIRED_FORBIDDEN_OUTPUTS)
    if requested_forbidden:
        failures.append(f"requested forbidden outputs: {', '.join(requested_forbidden)}")

    escrow_request = data["escrow_request"]
    if escrow_request["mode"] != "not_created":
        failures.append("raw detail escrow cannot be created in preflight")
    if escrow_request["raw_source_material"] != "forbidden_in_fixture":
        failures.append("raw source material is forbidden")
    if escrow_request["raw_review_body"] != "forbidden_in_fixture":
        failures.append("raw review body is forbidden")
    enabled_escrow_request_flags = sorted(
        flag
        for flag in [
            "escrow_handle_created",
            "encrypted_blob_created",
            "reviewer_access_enabled",
            "reviewer_lease_created",
            "decrypt_operation_enabled",
        ]
        if escrow_request[flag]
    )
    if enabled_escrow_request_flags:
        failures.append(f"raw detail escrow request performs blocked effects: {', '.join(enabled_escrow_request_flags)}")

    escrow_policy = data["escrow_policy_contract"]
    missing_review_reasons = sorted(REQUIRED_REVIEW_REASONS - set(escrow_policy["allowed_review_reasons"]))
    if missing_review_reasons:
        failures.append(f"missing escrow review reasons: {', '.join(missing_review_reasons)}")
    enabled_release_flags = sorted(
        flag
        for flag in [
            "public_release_allowed",
            "b2b_release_allowed",
            "respondent_release_allowed",
            "model_training_allowed",
        ]
        if escrow_policy[flag]
    )
    if enabled_release_flags:
        failures.append(f"raw detail escrow policy enables release: {', '.join(enabled_release_flags)}")

    consent = data["consent_revocation"]
    if consent["trusted_consent_completion_enabled"]:
        failures.append("trusted escrow consent completion cannot be enabled in preflight")
    if consent["escrow_consent_completed"]:
        failures.append("escrow consent cannot be completed in preflight")
    if not consent["revocation_supported_required"]:
        failures.append("revocation support is required")
    if consent["purge_path_accepted"]:
        failures.append("preflight cannot accept purge path")
    if consent["ttl_policy_accepted"]:
        failures.append("preflight cannot accept TTL policy")
    if not consent["escrow_consent_completed"]:
        failures.append("intake review escrow consent is not completed")
    if not consent["purge_path_accepted"]:
        failures.append("raw escrow purge path is not accepted")
    if not consent["ttl_policy_accepted"]:
        failures.append("raw escrow TTL policy is not accepted")

    storage = data["protected_storage"]
    if storage["key_material"] != "forbidden_in_fixture":
        failures.append("escrow key material is forbidden")
    enabled_storage_flags = sorted(flag for flag in FALSE_STORAGE_FLAGS if storage[flag])
    if enabled_storage_flags:
        failures.append(f"protected storage enables blocked capabilities: {', '.join(enabled_storage_flags)}")
    if not storage["durable_storage_enabled"]:
        failures.append("protected-data durability is disabled")

    envelope = data["cryptographic_envelope_contract"]
    if envelope["envelope_created"]:
        failures.append("cryptographic envelope cannot be created in preflight")
    if not envelope["key_rotation_policy_accepted"]:
        failures.append("key rotation policy is not accepted")

    access = data["reviewer_access_contract"]
    if access["lease_mode"] != "disabled_preflight_only":
        failures.append("reviewer access lease cannot be enabled in preflight")
    if access["lease_ttl_policy_accepted"]:
        failures.append("preflight cannot accept reviewer lease TTL policy")

    retention = data["retention_purge_contract"]
    if retention["retention_mode"] != "no_retention_preflight":
        failures.append("raw detail retention cannot be enabled in preflight")
    if retention["legal_hold_policy_accepted"]:
        failures.append("preflight cannot accept legal hold policy")

    audit_echo = data["audit_echo_contract"]
    missing_digest_fields = sorted(REQUIRED_DIGEST_FIELDS - set(audit_echo["digest_fields_required"]))
    if missing_digest_fields:
        failures.append(f"missing audit digest fields: {', '.join(missing_digest_fields)}")

    enabled_surface_flags = sorted(flag for flag in FALSE_SURFACE_FLAGS if data["surface_enablement"][flag])
    if enabled_surface_flags:
        failures.append(f"raw detail escrow enables future surfaces: {', '.join(enabled_surface_flags)}")
    enabled_result_flags = sorted(flag for flag in FALSE_RESULT_FLAGS if data["result_contract"][flag])
    if enabled_result_flags:
        failures.append(f"raw detail escrow performs blocked effects: {', '.join(enabled_result_flags)}")
    if not data["surface_enablement"]["raw_detail_escrow_enabled"]:
        failures.append("raw detail escrow surface is disabled")
    if contains_raw_marker(data):
        failures.append("raw detail escrow request contains raw markers")
    return failures


def result_payload(data, blockers):
    return {
        "status": "ok" if not blockers else "blocked",
        "escrow_allowed": not blockers,
        "objective_item": data["objective_item"],
        "surface": data["surface"],
        "command_effect": "preflight_only",
        "purpose_binding": data["escrow_policy_contract"]["purpose_binding"],
        "cryptographic_envelope_bound": True,
        "reviewer_access_contract_bound": True,
        "retention_purge_contract_bound": True,
        "audit_digest_only_contract_bound": True,
        "stores_raw_detail": False,
        "creates_escrow_handle": False,
        "creates_encrypted_blob": False,
        "stores_key_material": False,
        "opens_reviewer_access": False,
        "creates_reviewer_lease": False,
        "decrypts_escrow": False,
        "sends_raw_to_model_input": False,
        "echoes_raw_in_validator_errors": False,
        "echoes_raw_in_audit_or_client_response": False,
        "opens_public_surface": False,
        "delivers_to_b2b": False,
        "serves_dashboard": False,
        "performs_identity_processing": False,
        "makes_retrievable": False,
        "exports_raw_detail": False,
        "writes_audit_event": False,
        "required_gates": sorted(REQUIRED_GATES),
        "blocking_gates": blockers,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate raw detail escrow preflight contract.")
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
