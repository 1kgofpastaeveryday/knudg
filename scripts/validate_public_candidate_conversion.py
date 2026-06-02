#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "public-candidate-conversion-request-v0.schema.json"
REQUIRED_GATES = {"PR-003", "PR-005", "PR-006", "REVIEWER_PUBLISH"}
REQUIRED_FORBIDDEN_OUTPUTS = {
    "submitter_identity",
    "raw_source_material",
    "private_selection_status",
    "staff_identity",
    "raw_review_body",
    "non_public_operational_detail",
}
FALSE_SURFACE_FLAGS = {
    "conversion_enabled",
    "public_serving_enabled",
    "b2b_delivery_enabled",
    "identity_processing_enabled",
    "raw_detail_escrow_enabled",
    "dashboard_enabled",
}
FALSE_RESULT_FLAGS = {
    "creates_public_card",
    "mutates_private_record",
    "opens_public_surface",
    "delivers_to_b2b",
    "serves_dashboard",
    "stores_raw_detail",
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
    if data["source_private_record"]["private_record_mutation"] != "forbidden":
        failures.append("public candidate conversion cannot mutate source private record")
    if data["source_private_record"]["record_digest"] == data["new_public_candidate_artifact"]["artifact_digest"]:
        failures.append("public candidate conversion requires a new artifact digest")
    if data["source_private_record"]["record_id"] == data["source_private_record"]["private_retention_consent_id"]:
        failures.append("public candidate conversion source record and consent ids must be distinct")
    if data["new_public_candidate_artifact"]["domain"] != "public_experience_candidate":
        failures.append("new artifact must use public_experience_candidate domain")
    if data["new_public_candidate_artifact"]["raw_source_retention"] != "none":
        failures.append("public candidate conversion cannot retain raw source")
    if data["new_public_candidate_artifact"]["stored_public_card"]:
        failures.append("public candidate conversion preflight cannot store public card")
    payload = data["public_candidate_payload"]
    if payload["publication_state"] != "candidate_only_not_served":
        failures.append("public candidate payload cannot be marked served")
    if payload["source_attribution"] != "redacted_private_experience_record":
        failures.append("public candidate payload must derive from a redacted private experience record")
    missing_payload_exclusions = sorted(REQUIRED_FORBIDDEN_OUTPUTS - set(payload["excluded_private_detail_classes"]))
    if missing_payload_exclusions:
        failures.append(f"public candidate payload missing excluded private detail classes: {', '.join(missing_payload_exclusions)}")

    approval = data["approval_path"]
    required_approval_true = [
        "exact_artifact_approval_required",
        "reviewer_publish_required",
        "consent_challenge_required",
    ]
    missing_approval = sorted(flag for flag in required_approval_true if not approval[flag])
    if missing_approval:
        failures.append(f"missing required approval controls: {', '.join(missing_approval)}")
    completed_approval = sorted(flag for flag in ["approval_completed", "reviewer_publish_completed"] if approval[flag])
    if completed_approval:
        failures.append(f"preflight cannot complete approval controls: {', '.join(completed_approval)}")
    if not approval["approval_completed"]:
        failures.append("exact artifact approval is not completed")
    if not approval["reviewer_publish_completed"]:
        failures.append("reviewer publish is not completed")

    forbidden_outputs = set(data["forbidden_outputs"])
    missing_outputs = sorted(REQUIRED_FORBIDDEN_OUTPUTS - forbidden_outputs)
    if missing_outputs:
        failures.append(f"missing forbidden outputs: {', '.join(missing_outputs)}")
    requested_forbidden_outputs = sorted(
        set(data["output_contract"]["requested_outputs"]) & REQUIRED_FORBIDDEN_OUTPUTS
    )
    if requested_forbidden_outputs:
        failures.append(f"requested forbidden outputs: {', '.join(requested_forbidden_outputs)}")
    withheld_outputs = set(data["output_contract"]["withheld_outputs"])
    missing_withheld = sorted(REQUIRED_FORBIDDEN_OUTPUTS - withheld_outputs)
    if missing_withheld:
        failures.append(f"missing withheld outputs: {', '.join(missing_withheld)}")

    enabled_surface_flags = sorted(flag for flag in FALSE_SURFACE_FLAGS if data["surface_enablement"][flag])
    if enabled_surface_flags:
        failures.append(f"public candidate conversion enables future surfaces: {', '.join(enabled_surface_flags)}")
    if not data["surface_enablement"]["conversion_enabled"]:
        failures.append("public candidate conversion surface is disabled")
    enabled_result_flags = sorted(flag for flag in FALSE_RESULT_FLAGS if data["result_contract"][flag])
    if enabled_result_flags:
        failures.append(f"public candidate conversion performs blocked effects: {', '.join(enabled_result_flags)}")
    if contains_raw_marker(data):
        failures.append("public candidate conversion request contains raw markers")
    return failures


def result_payload(data, blockers):
    return {
        "status": "ok" if not blockers else "blocked",
        "conversion_allowed": not blockers,
        "objective_item": data["objective_item"],
        "command_effect": "preflight_only",
        "creates_public_card": False,
        "mutates_private_record": False,
        "opens_public_surface": False,
        "delivers_to_b2b": False,
        "serves_dashboard": False,
        "stores_raw_detail": False,
        "required_gates": sorted(REQUIRED_GATES),
        "blocking_gates": blockers,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate public candidate conversion preflight contract.")
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
