#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path

from jsonschema import Draft202012Validator

from validate_experience_surface_gates import REQUIRED_SURFACES, gate_failures


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "experience-surface-activation-request-v0.schema.json"
DEFAULT_GATES_PATH = ROOT / "fixtures" / "experience-surface-gates.draft.json"
GATES_SCHEMA_PATH = ROOT / "schemas" / "experience-surface-gates-v0.schema.json"
RAW_MARKERS = (
    re.compile(r"\b(password|secret|token|api[_-]?key|credential|private[_-]?key)\b", re.IGNORECASE),
    re.compile(r"\b[A-Z]:\\", re.IGNORECASE),
    re.compile(r"\\\\[A-Za-z0-9_.-]+\\"),
)
SURFACE_OPERATIONS = {
    "actual_experience_storage": "enable_actual_experience_storage",
    "public_candidate_conversion": "convert_public_candidate",
    "b2b_respondent_portal": "open_b2b_respondent_portal",
    "abuse_identity_ban_operations": "enable_abuse_identity_ban_operations",
    "raw_detail_escrow": "enable_raw_detail_escrow",
    "company_store_dashboard": "open_company_store_dashboard",
}
SURFACE_ENABLEMENT = {
    "actual_experience_storage": {"real_data_ingest_enabled"},
    "public_candidate_conversion": {"public_serving_enabled"},
    "b2b_respondent_portal": {"b2b_delivery_enabled"},
    "abuse_identity_ban_operations": {"identity_processing_enabled"},
    "raw_detail_escrow": {"raw_detail_escrow_enabled"},
    "company_store_dashboard": {"dashboard_enabled"},
}
GLOBAL_FORBIDDEN_OUTPUTS = {
    "submitter_identity",
    "raw_source_material",
    "device_or_network_signal",
    "reidentification_hint",
    "private_selection_status",
    "staff_identity",
    "protected_fingerprint",
    "raw_review_body",
    "non_public_operational_detail",
    "source_metadata",
    "raw_moderation_evidence",
    "escrow_ciphertext",
    "escrow_handle",
    "escrow_key_material",
    "reviewer_private_note",
}


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def schema_errors(schema_path, data):
    schema = load_json(schema_path)
    return sorted(Draft202012Validator(schema).iter_errors(data), key=lambda error: list(error.path))


def sanitized_schema_errors(errors):
    return [{"path": "/".join(str(item) for item in error.path), "validator": error.validator} for error in errors]


def contains_raw_marker(data):
    text = json.dumps(data, sort_keys=True)
    return any(pattern.search(text) for pattern in RAW_MARKERS)


def surface_by_key(gates):
    return {surface["surface"]: surface for surface in gates["surfaces"]}


def preflight_blockers(request, gates):
    blockers = []
    gate_errors = schema_errors(GATES_SCHEMA_PATH, gates)
    if gate_errors:
        blockers.append("experience surface gate manifest schema is invalid")
        return blockers
    gate_blockers = gate_failures(gates)
    blockers.extend(f"gate manifest blocked: {item}" for item in gate_blockers)

    surface_key = request["requested_surface"]
    expected = REQUIRED_SURFACES[surface_key]
    surface = surface_by_key(gates).get(surface_key)
    if surface is None:
        blockers.append(f"{surface_key} is missing from gate manifest")
        return blockers
    if request["requested_operation"] != SURFACE_OPERATIONS[surface_key]:
        blockers.append(f"{surface_key} requested wrong operation")
    if request["objective_item"] != expected["objective_item"]:
        blockers.append(f"{surface_key} requested wrong objective item")
    if set(request["requested_domains"]) != expected["domains"]:
        blockers.append(f"{surface_key} requested wrong domains")

    requested_true_flags = {key for key, value in request["requested_enablement"].items() if value}
    if requested_true_flags != SURFACE_ENABLEMENT[surface_key]:
        blockers.append(f"{surface_key} requested wrong enablement flags")

    evidence = {item["gate"]: item["status"] for item in request["gate_evidence"]}
    missing_evidence = sorted(expected["required_gates"] - set(evidence))
    if missing_evidence:
        blockers.append(f"{surface_key} missing gate evidence: {', '.join(missing_evidence)}")
    unaccepted = sorted(gate for gate in expected["required_gates"] if evidence.get(gate) != "accepted")
    if unaccepted:
        blockers.append(f"{surface_key} has unaccepted gate evidence: {', '.join(unaccepted)}")

    forbidden_requested_outputs = sorted(set(request["output_contract"]["requested_outputs"]) & expected["forbidden_outputs"])
    if forbidden_requested_outputs:
        blockers.append(f"{surface_key} requests forbidden outputs: {', '.join(forbidden_requested_outputs)}")
    forbidden_allowed_outputs = sorted(set(request["output_contract"]["allowed_outputs"]) & expected["forbidden_outputs"])
    if forbidden_allowed_outputs:
        blockers.append(f"{surface_key} allows forbidden outputs: {', '.join(forbidden_allowed_outputs)}")
    globally_forbidden_requested = sorted(
        set(request["output_contract"]["requested_outputs"]) & GLOBAL_FORBIDDEN_OUTPUTS
    )
    if globally_forbidden_requested:
        blockers.append(f"{surface_key} requests globally forbidden outputs: {', '.join(globally_forbidden_requested)}")
    globally_forbidden_allowed = sorted(set(request["output_contract"]["allowed_outputs"]) & GLOBAL_FORBIDDEN_OUTPUTS)
    if globally_forbidden_allowed:
        blockers.append(f"{surface_key} allows globally forbidden outputs: {', '.join(globally_forbidden_allowed)}")
    requested_not_allowed = sorted(
        set(request["output_contract"]["requested_outputs"]) - set(request["output_contract"]["allowed_outputs"])
    )
    if requested_not_allowed:
        blockers.append(f"{surface_key} requested outputs are not allowed: {', '.join(requested_not_allowed)}")

    if gates["status"] != "accepted":
        blockers.append("experience surface gate manifest is not accepted")
    if surface["status"] != "accepted":
        blockers.append(f"{surface_key} surface is not accepted")
    if any(surface["enablement"].values()):
        blockers.append(f"{surface_key} manifest enablement flags must remain false before activation")
    return blockers


def result_payload(request, gates, blockers):
    surface_key = request["requested_surface"]
    surface = surface_by_key(gates).get(surface_key, {})
    expected = REQUIRED_SURFACES.get(surface_key, {})
    return {
        "status": "ok" if not blockers else "blocked",
        "activation_allowed": not blockers,
        "requested_surface": surface_key,
        "objective_item": request["objective_item"],
        "command_effect": "preflight_only",
        "writes_real_data": False,
        "creates_card": False,
        "indexes": False,
        "opens_public_surface": False,
        "performs_identity_processing": False,
        "stores_raw_detail": False,
        "serves_dashboard": False,
        "requested_enablement": request["requested_enablement"],
        "applied_enablement": {
            "real_data_ingest_enabled": False,
            "public_serving_enabled": False,
            "b2b_delivery_enabled": False,
            "identity_processing_enabled": False,
            "raw_detail_escrow_enabled": False,
            "dashboard_enabled": False,
        },
        "required_gates": sorted(expected.get("required_gates", [])),
        "surface_manifest_status": surface.get("status"),
        "blocking_gates": blockers,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Preflight broader experience surface activation without enabling it.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--gates", default=str(DEFAULT_GATES_PATH))
    args = parser.parse_args(argv)

    request = load_json(args.input)
    errors = schema_errors(SCHEMA_PATH, request)
    if errors:
        print(json.dumps({"status": "rejected", "errors": sanitized_schema_errors(errors)}, sort_keys=True))
        return 2
    if contains_raw_marker(request):
        print(json.dumps({"status": "rejected", "errors": [{"path": "", "validator": "raw_marker"}]}, sort_keys=True))
        return 2

    gates = load_json(args.gates)
    blockers = preflight_blockers(request, gates)
    payload = result_payload(request, gates, blockers)
    print(json.dumps(payload, sort_keys=True))
    return 0 if not blockers else 3


if __name__ == "__main__":
    raise SystemExit(main())
