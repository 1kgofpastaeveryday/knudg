#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "b2b-respondent-portal-request-v0.schema.json"
REQUIRED_GATES = {"ED-005", "NO_DISCLOSURE_NEGATIVE_TESTS", "RESPONDENT_POLICY", "MODERATION_WORKFLOW"}
REQUIRED_FORBIDDEN_OUTPUTS = {
    "submitter_identity",
    "raw_source_material",
    "device_or_network_signal",
    "reidentification_hint",
    "protected_fingerprint",
    "raw_review_body",
    "source_metadata",
    "raw_moderation_evidence",
    "escrow_ciphertext",
    "escrow_handle",
    "escrow_key_material",
    "reviewer_private_note",
    "non_public_operational_detail",
    "respondent_visible_user_attribution",
}
FALSE_SURFACE_FLAGS = {
    "portal_enabled",
    "b2b_delivery_enabled",
    "response_submission_enabled",
    "public_serving_enabled",
    "identity_processing_enabled",
    "raw_detail_escrow_enabled",
    "dashboard_enabled",
}
FALSE_RESULT_FLAGS = {
    "opens_portal",
    "delivers_to_b2b",
    "makes_response_available",
    "opens_public_surface",
    "serves_dashboard",
    "performs_identity_processing",
    "stores_raw_detail",
}
FALSE_RESPONSE_FLAGS = {
    "contains_raw_source",
    "contains_submitter_identity",
    "contains_device_or_network_signal",
    "contains_protected_fingerprint",
    "contains_reidentification_hint",
    "response_available",
}
FALSE_PORTAL_VIEW_FLAGS = {
    "access_token_issued",
    "server_render_enabled",
    "contains_submit_control",
    "contains_contact_channel",
}
REQUIRED_DISABLED_ACTIONS = {
    "submit_response",
    "upload_raw_detail",
    "request_submitter_identity",
    "message_submitter",
    "claim_business_profile",
    "open_dashboard",
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
    missing_blockers = sorted(REQUIRED_GATES - set(data["blocked_until"]))
    if missing_blockers:
        failures.append(f"missing blocked_until gates: {', '.join(missing_blockers)}")
    missing_outputs = sorted(REQUIRED_FORBIDDEN_OUTPUTS - set(data["forbidden_outputs"]))
    if missing_outputs:
        failures.append(f"missing forbidden outputs: {', '.join(missing_outputs)}")
    missing_withheld = sorted(REQUIRED_FORBIDDEN_OUTPUTS - set(data["output_contract"]["withheld_outputs"]))
    if missing_withheld:
        failures.append(f"missing withheld outputs: {', '.join(missing_withheld)}")
    requested_forbidden = sorted(set(data["output_contract"]["requested_outputs"]) & REQUIRED_FORBIDDEN_OUTPUTS)
    if requested_forbidden:
        failures.append(f"requested forbidden outputs: {', '.join(requested_forbidden)}")
    visibility = data["respondent_visibility_contract"]
    visibility_withheld = set(visibility["withheld_fields"])
    missing_visibility_withheld = sorted(REQUIRED_FORBIDDEN_OUTPUTS - visibility_withheld)
    if missing_visibility_withheld:
        failures.append(f"respondent visibility contract missing withheld fields: {', '.join(missing_visibility_withheld)}")
    if visibility["identity_disclosure"] != "none":
        failures.append("respondent visibility contract cannot disclose identity")
    if visibility["raw_detail_disclosure"] != "none":
        failures.append("respondent visibility contract cannot disclose raw detail")
    if visibility["response_submission_policy"] != "disabled_until_gates_pass":
        failures.append("respondent response submission must remain disabled before gates pass")
    if set(visibility["visible_fields"]) != set(data["output_contract"]["requested_outputs"]):
        failures.append("respondent visible fields must match requested outputs")
    portal_flags = sorted(flag for flag in FALSE_PORTAL_VIEW_FLAGS if data["portal_view_contract"][flag])
    if portal_flags:
        failures.append(f"respondent portal view enables serving surface: {', '.join(portal_flags)}")
    action = data["respondent_action_contract"]
    if action["allowed_actions"]:
        failures.append("respondent actions must remain empty before gates pass")
    missing_disabled_actions = sorted(REQUIRED_DISABLED_ACTIONS - set(action["disabled_actions"]))
    if missing_disabled_actions:
        failures.append(f"respondent action contract missing disabled actions: {', '.join(missing_disabled_actions)}")
    if action["action_token_issued"]:
        failures.append("respondent action token cannot be issued before gates pass")

    response_flags = sorted(flag for flag in FALSE_RESPONSE_FLAGS if data["response_draft"][flag])
    if response_flags:
        failures.append(f"response draft exposes forbidden data: {', '.join(response_flags)}")
    enabled_surface_flags = sorted(flag for flag in FALSE_SURFACE_FLAGS if data["surface_enablement"][flag])
    if enabled_surface_flags:
        failures.append(f"b2b respondent portal enables future surfaces: {', '.join(enabled_surface_flags)}")
    enabled_result_flags = sorted(flag for flag in FALSE_RESULT_FLAGS if data["result_contract"][flag])
    if enabled_result_flags:
        failures.append(f"b2b respondent portal performs blocked effects: {', '.join(enabled_result_flags)}")
    if data["respondent_scope"]["identity_verification_status"] != "not_verified_preflight":
        failures.append("respondent identity verification cannot complete in preflight")
    if data["respondent_scope"]["contact_channel_available"]:
        failures.append("respondent contact channel cannot be available in preflight")
    if data["source_public_candidate"]["public_serving_enabled"]:
        failures.append("b2b respondent portal cannot depend on public serving")
    if not data["surface_enablement"]["portal_enabled"]:
        failures.append("b2b respondent portal surface is disabled")
    if not data["surface_enablement"]["b2b_delivery_enabled"]:
        failures.append("b2b delivery is disabled")
    if not data["response_draft"]["response_available"]:
        failures.append("respondent response is not available")
    if contains_raw_marker(data):
        failures.append("b2b respondent portal request contains raw markers")
    return failures


def result_payload(data, blockers):
    return {
        "status": "ok" if not blockers else "blocked",
        "portal_allowed": not blockers,
        "objective_item": data["objective_item"],
        "command_effect": "preflight_only",
        "opens_portal": False,
        "delivers_to_b2b": False,
        "makes_response_available": False,
        "opens_public_surface": False,
        "serves_dashboard": False,
        "performs_identity_processing": False,
        "stores_raw_detail": False,
        "required_gates": sorted(REQUIRED_GATES),
        "blocking_gates": blockers,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate B2B respondent portal preflight contract.")
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
