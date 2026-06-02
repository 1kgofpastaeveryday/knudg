#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "company-store-dashboard-request-v0.schema.json"
REQUIRED_GATES = {
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
}
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
    "account_identifier",
    "match_status",
    "individual_claim",
    "single_observation_detail",
    "reviewer_private_note",
    "non_public_operational_detail",
}
FALSE_SURFACE_FLAGS = {
    "dashboard_enabled",
    "dashboard_serving_enabled",
    "aggregate_signal_query_enabled",
    "single_observation_display_enabled",
    "public_serving_enabled",
    "b2b_delivery_enabled",
    "respondent_portal_enabled",
    "identity_processing_enabled",
    "raw_detail_escrow_enabled",
    "retrieval_enabled",
    "export_enabled",
    "ranking_enabled",
}
FALSE_RESULT_FLAGS = {
    "serves_dashboard",
    "creates_dashboard_view",
    "queries_aggregate_signal",
    "shows_single_observation",
    "suppresses_negative_reviews",
    "suppresses_or_hides_reviews",
    "opens_public_surface",
    "delivers_to_b2b",
    "opens_respondent_portal",
    "performs_identity_processing",
    "stores_raw_detail",
    "makes_retrievable",
    "exports_dashboard_data",
    "writes_audit_event",
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
    blocked_gates = {item["gate"] for item in data["blocked_until"]}
    missing_blocked_gates = sorted(REQUIRED_GATES - blocked_gates)
    if missing_blocked_gates:
        failures.append(f"missing blocked_until gates: {', '.join(missing_blocked_gates)}")

    missing_outputs = sorted(REQUIRED_FORBIDDEN_OUTPUTS - set(data["forbidden_outputs"]))
    if missing_outputs:
        failures.append(f"missing forbidden outputs: {', '.join(missing_outputs)}")
    missing_withheld = sorted(REQUIRED_FORBIDDEN_OUTPUTS - set(data["output_contract"]["withheld_outputs"]))
    if missing_withheld:
        failures.append(f"missing withheld outputs: {', '.join(missing_withheld)}")
    requested_forbidden = sorted(set(data["output_contract"]["requested_outputs"]) & REQUIRED_FORBIDDEN_OUTPUTS)
    if requested_forbidden:
        failures.append(f"requested forbidden outputs: {', '.join(requested_forbidden)}")

    aggregate = data["aggregate_signal_request"]
    if aggregate["aggregate_signal_available"]:
        failures.append("aggregate signal cannot be available in preflight")
    if aggregate["minimum_group_size_met"]:
        failures.append("minimum group size cannot be accepted in preflight")
    if aggregate["single_observation_display_enabled"]:
        failures.append("single-observation display cannot be enabled")
    if aggregate["negative_review_suppression_enabled"]:
        failures.append("negative review suppression cannot be enabled")
    if aggregate["review_suppression_surface_enabled"]:
        failures.append("review suppression surface cannot be enabled")
    if aggregate["manipulation_response_controls_enabled"]:
        failures.append("manipulation response controls cannot be enabled")
    if aggregate["manipulation_review_enabled"]:
        failures.append("manipulation review cannot be completed in preflight")
    if aggregate["freshness_policy_accepted"]:
        failures.append("preflight cannot accept freshness policy")
    if aggregate["stale_signal_expiry_accepted"]:
        failures.append("preflight cannot accept stale-signal expiry policy")
    if not aggregate["aggregate_signal_available"]:
        failures.append("aggregate signal is not available")
    if not aggregate["minimum_group_size_met"]:
        failures.append("minimum group size is not met")
    if not aggregate["manipulation_review_enabled"]:
        failures.append("manipulation checks are not accepted")

    disclosure = data["disclosure_policy"]
    if disclosure["public_b2b_disclosure_policy_accepted"]:
        failures.append("preflight cannot accept public/B2B disclosure policy")
    if disclosure["respondent_inquiry_policy_accepted"]:
        failures.append("preflight cannot accept respondent inquiry policy")
    if disclosure["no_identity_leakage_tests_passed"]:
        failures.append("preflight cannot pass no-identity-leakage tests")
    if disclosure["correction_takedown_workflow_accepted"]:
        failures.append("preflight cannot accept correction/takedown workflow")
    if not disclosure["public_b2b_disclosure_policy_accepted"]:
        failures.append("public/B2B disclosure policy is not accepted")
    if not disclosure["no_identity_leakage_tests_passed"]:
        failures.append("no-identity-leakage tests are not accepted")
    if not disclosure["correction_takedown_workflow_accepted"]:
        failures.append("correction and takedown workflow is not accepted")

    aggregate_privacy = data["aggregate_privacy_contract"]
    if aggregate_privacy["minimum_source_count_policy_accepted"]:
        failures.append("preflight cannot accept aggregate privacy threshold policy")
    if aggregate_privacy["drilldown_to_source_allowed"]:
        failures.append("dashboard cannot allow source drilldown in preflight")
    if aggregate_privacy["segment_breakdown_allowed"]:
        failures.append("dashboard cannot allow segment breakdown in preflight")
    if not aggregate_privacy["minimum_source_count_policy_accepted"]:
        failures.append("aggregate privacy threshold policy is not accepted")

    review_integrity = data["review_integrity_contract"]
    if review_integrity["negative_review_suppression_allowed"]:
        failures.append("negative review suppression cannot be allowed")
    if review_integrity["respondent_self_service_suppression_allowed"]:
        failures.append("respondent self-service suppression cannot be allowed")
    if review_integrity["manipulation_response_controls_allowed"]:
        failures.append("manipulation response controls cannot be allowed")
    if review_integrity["correction_takedown_policy_accepted"]:
        failures.append("preflight cannot accept correction/takedown policy")

    display = data["dashboard_display_contract"]
    enabled_display_flags = sorted(
        flag
        for flag in [
            "single_observation_display_allowed",
            "raw_detail_display_allowed",
            "identity_state_display_allowed",
            "escrow_artifact_display_allowed",
            "ranking_or_sorting_enabled",
        ]
        if display[flag]
    )
    if enabled_display_flags:
        failures.append(f"dashboard display contract enables blocked displays: {', '.join(enabled_display_flags)}")

    delivery = data["dashboard_delivery_contract"]
    enabled_delivery_flags = sorted(
        flag
        for flag in [
            "access_token_issued",
            "api_serving_enabled",
            "export_download_enabled",
            "b2b_delivery_enabled",
            "public_serving_enabled",
            "dashboard_snapshot_enabled",
        ]
        if delivery[flag]
    )
    if enabled_delivery_flags:
        failures.append(f"dashboard delivery contract enables serving: {', '.join(enabled_delivery_flags)}")

    enabled_surface_flags = sorted(flag for flag in FALSE_SURFACE_FLAGS if data["surface_enablement"][flag])
    if enabled_surface_flags:
        failures.append(f"company/store dashboard enables future surfaces: {', '.join(enabled_surface_flags)}")
    enabled_result_flags = sorted(flag for flag in FALSE_RESULT_FLAGS if data["result_contract"][flag])
    if enabled_result_flags:
        failures.append(f"company/store dashboard performs blocked effects: {', '.join(enabled_result_flags)}")
    if not data["surface_enablement"]["dashboard_enabled"]:
        failures.append("company/store dashboard surface is disabled")
    if contains_raw_marker(data):
        failures.append("company/store dashboard request contains raw markers")
    return failures


def result_payload(data, blockers):
    return {
        "status": "ok" if not blockers else "blocked",
        "dashboard_allowed": not blockers,
        "objective_item": data["objective_item"],
        "surface": data["surface"],
        "command_effect": "preflight_only",
        "aggregate_privacy_contract_bound": True,
        "review_integrity_contract_bound": True,
        "dashboard_display_contract_bound": True,
        "dashboard_delivery_contract_bound": True,
        "serves_dashboard": False,
        "creates_dashboard_view": False,
        "queries_aggregate_signal": False,
        "shows_single_observation": False,
        "suppresses_negative_reviews": False,
        "suppresses_or_hides_reviews": False,
        "opens_public_surface": False,
        "delivers_to_b2b": False,
        "opens_respondent_portal": False,
        "performs_identity_processing": False,
        "stores_raw_detail": False,
        "makes_retrievable": False,
        "exports_dashboard_data": False,
        "writes_audit_event": False,
        "required_gates": sorted(REQUIRED_GATES),
        "blocking_gates": blockers,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate company/store dashboard preflight contract.")
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
