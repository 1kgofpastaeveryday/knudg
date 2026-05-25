#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "consent-revocation-gate.schema.json"
REQUIRED_SURFACES = {
    "private_candidate_collection_consent": "private_candidate_collection",
    "private_retention_consent": "private_retention",
    "team_namespace_grant_consent": "team_namespace_grant",
    "public_publication_consent": "public_publication",
    "intake_review_escrow_consent": "intake_review_escrow",
}
REQUIRED_BLOCKERS = {
    "trusted_ui_implemented",
    "accessibility_baseline_pass",
    "challenge_completion_schemas_accepted",
    "csrf_and_clickjacking_tests_pass",
    "exact_origin_redirect_tests_pass",
    "anti_enumeration_tests_pass",
    "serializable_consent_tombstone_audit_tests_pass",
    "malicious_client_handoff_tests_pass",
}


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def gate_failures(data):
    failures = []
    seen = set()
    duplicates = []
    surfaces = {}
    for surface in data["surfaces"]:
        surface_type = surface["surface_type"]
        if surface_type in seen:
            duplicates.append(surface_type)
        seen.add(surface_type)
        surfaces[surface_type] = surface
    if duplicates:
        failures.append(f"duplicate consent surfaces: {', '.join(sorted(set(duplicates)))}")
    missing = sorted(set(REQUIRED_SURFACES) - set(surfaces))
    if missing:
        failures.append(f"missing consent surfaces: {', '.join(missing)}")
    for surface_type, canonical_scope in REQUIRED_SURFACES.items():
        surface = surfaces.get(surface_type)
        if surface and surface["canonical_scope"] != canonical_scope:
            failures.append(f"{surface_type} maps to wrong canonical scope")
    missing_blockers = sorted(REQUIRED_BLOCKERS - set(data["blocked_until"]))
    if data["status"] != "accepted" and missing_blockers:
        failures.append(f"missing blockers: {', '.join(missing_blockers)}")
    if data["status"] == "accepted":
        if data["blocked_until"]:
            failures.append("accepted consent gate must not have blocked_until entries")
        for surface in data["surfaces"]:
            if surface["status"] != "trusted_completion_ready":
                failures.append(f"{surface['surface_type']} is not trusted-completion ready")
            if surface["completion_transport"] != "trusted_browser_or_os_surface":
                failures.append(f"{surface['surface_type']} lacks trusted completion transport")
    enabled = [name for name, value in data["enablement"].items() if value]
    if data["status"] != "accepted" and enabled:
        failures.append(f"draft consent gate cannot enable surfaces: {', '.join(sorted(enabled))}")
    return failures


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate PR-003 consent/revocation gate fixture.")
    parser.add_argument("--input", required=True)
    args = parser.parse_args(argv)

    schema = load_json(SCHEMA_PATH)
    data = load_json(args.input)
    errors = sorted(Draft202012Validator(schema).iter_errors(data), key=lambda error: list(error.path))
    if errors:
        print(json.dumps({"status": "rejected", "errors": [error.message for error in errors]}, sort_keys=True))
        return 2
    failures = gate_failures(data)
    if failures:
        print(json.dumps({"status": "blocked", "blocking_gates": failures}, sort_keys=True))
        return 3
    print(
        json.dumps(
            {
                "status": "ok",
                "trusted_completion_enabled": data["enablement"]["trusted_completion_enabled"],
                "public_publication_enabled": data["enablement"]["public_publication_enabled"],
                "surface_count": len(data["surfaces"]),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
