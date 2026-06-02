#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "experience-surface-gates-v0.schema.json"
REQUIRED_SURFACES = {
    "actual_experience_storage": {
        "objective_item": 8,
        "domains": {"career_private", "place_service_experience"},
        "required_gates": {"PR-003", "PR-006", "ED-001", "ED-002"},
        "forbidden_outputs": {"submitter_identity", "raw_source_material", "private_selection_status", "staff_identity", "raw_review_body"},
    },
    "public_candidate_conversion": {
        "objective_item": 9,
        "domains": {"public_experience_candidate"},
        "required_gates": {"PR-003", "PR-005", "PR-006", "REVIEWER_PUBLISH"},
        "forbidden_outputs": {"submitter_identity", "raw_source_material", "private_selection_status", "staff_identity", "raw_review_body", "non_public_operational_detail"},
    },
    "b2b_respondent_portal": {
        "objective_item": 10,
        "domains": {"public_experience_candidate", "public_aggregate_signal"},
        "required_gates": {"ED-005", "NO_DISCLOSURE_NEGATIVE_TESTS", "RESPONDENT_POLICY", "MODERATION_WORKFLOW"},
        "forbidden_outputs": {"submitter_identity", "raw_source_material", "device_or_network_signal", "reidentification_hint", "protected_fingerprint", "raw_review_body", "source_metadata", "raw_moderation_evidence", "respondent_visible_user_attribution"},
    },
    "abuse_identity_ban_operations": {
        "objective_item": 11,
        "domains": {"career_private", "place_service_experience", "public_experience_candidate", "public_aggregate_signal"},
        "required_gates": {
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
        },
        "forbidden_outputs": {
            "submitter_identity",
            "raw_identity_values",
            "subject_row",
            "raw_source_material",
            "device_or_network_signal",
            "reidentification_hint",
            "protected_fingerprint",
            "source_metadata",
            "raw_moderation_evidence",
            "match_status",
            "account_identifier",
            "private_selection_status",
        },
    },
    "raw_detail_escrow": {
        "objective_item": 12,
        "domains": {"career_private", "place_service_experience", "public_experience_candidate"},
        "required_gates": {
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
        },
        "forbidden_outputs": {
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
        },
    },
    "company_store_dashboard": {
        "objective_item": 13,
        "domains": {"public_aggregate_signal"},
        "required_gates": {
            "AGGREGATE_SIGNAL_POLICY",
            "PUBLIC_B2B_DISCLOSURE_POLICY",
            "MODERATION_WORKFLOW",
            "NO_IDENTITY_LEAKAGE_TESTS",
            "MIN_SOURCE_COUNT_POLICY",
            "MANIPULATION_RESISTANCE_POLICY",
            "NO_SINGLE_OBSERVATION_DISPLAY_TESTS",
            "NO_SUPPRESSION_SURFACE_TESTS",
            "CORRECTION_TAKEDOWN_POLICY",
            "AGGREGATE_PRIVACY_THRESHOLD_POLICY",
            "FAIR_REVIEW_PRESENTATION_POLICY",
            "DASHBOARD_DISPLAY_POLICY",
            "NO_ESCROW_ARTIFACT_DISPLAY_TESTS",
            "DASHBOARD_EXPORT_DOWNLOAD_POLICY",
        },
        "forbidden_outputs": {
            "submitter_identity",
            "raw_source_material",
            "device_or_network_signal",
            "reidentification_hint",
            "protected_fingerprint",
            "raw_review_body",
            "private_selection_status",
            "staff_identity",
            "source_metadata",
            "raw_moderation_evidence",
            "escrow_ciphertext",
            "escrow_handle",
            "escrow_key_material",
            "account_identifier",
            "match_status",
            "individual_claim",
            "single_observation_detail",
            "reviewer_private_note",
            "non_public_operational_detail",
        },
    },
}
ENABLEMENT_FLAGS = {
    "real_data_ingest_enabled",
    "public_serving_enabled",
    "b2b_delivery_enabled",
    "identity_processing_enabled",
    "raw_detail_escrow_enabled",
    "dashboard_enabled",
}


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def gate_failures(data):
    failures = []
    seen = set()
    duplicates = []
    for item in data["surfaces"]:
        surface = item["surface"]
        if surface in seen:
            duplicates.append(surface)
        seen.add(surface)
    if duplicates:
        failures.append(f"duplicate surfaces: {', '.join(sorted(set(duplicates)))}")
    by_surface = {item["surface"]: item for item in data["surfaces"]}
    missing_surfaces = sorted(set(REQUIRED_SURFACES) - set(by_surface))
    if missing_surfaces:
        failures.append(f"missing surfaces: {', '.join(missing_surfaces)}")
    extra_surfaces = sorted(set(by_surface) - set(REQUIRED_SURFACES))
    if extra_surfaces:
        failures.append(f"unknown surfaces: {', '.join(extra_surfaces)}")

    for surface, requirements in sorted(REQUIRED_SURFACES.items()):
        item = by_surface.get(surface)
        if not item:
            continue
        if item["objective_item"] != requirements["objective_item"]:
            failures.append(f"{surface} maps to wrong objective item")
        domains = set(item["domains"])
        if domains != requirements["domains"]:
            failures.append(f"{surface} has wrong domains")
        if data["status"] != "accepted" and item["status"] != "blocked":
            failures.append(f"{surface} must remain blocked before accepted manifest")
        enabled_flags = sorted(flag for flag in ENABLEMENT_FLAGS if item["enablement"][flag])
        if enabled_flags:
            failures.append(f"{surface} has enabled flags: {', '.join(enabled_flags)}")
        gates = {gate["gate"] for gate in item["required_gates"]}
        missing_gates = sorted(requirements["required_gates"] - gates)
        if missing_gates:
            failures.append(f"{surface} missing gates: {', '.join(missing_gates)}")
        forbidden_outputs = set(item["forbidden_outputs"])
        missing_outputs = sorted(requirements["forbidden_outputs"] - forbidden_outputs)
        if missing_outputs:
            failures.append(f"{surface} missing forbidden outputs: {', '.join(missing_outputs)}")
    if data["status"] == "accepted":
        accepted_surfaces = [item["surface"] for item in data["surfaces"] if item["status"] == "accepted"]
        if len(accepted_surfaces) != len(data["surfaces"]):
            failures.append("accepted manifest requires every surface to be accepted")
    return failures


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate broader experience surface gate manifest.")
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
    print(json.dumps({"status": "ok", "surface_count": len(data["surfaces"])}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
