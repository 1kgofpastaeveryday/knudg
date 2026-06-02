#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "intake-safety-gate.schema.json"
REQUIRED_DECISIONS = {"accepted", "redact_then_retry", "human_review_required", "reject", "retry_later"}
REQUIRED_BLOCKERS = {
    "submit_candidate_schema_accepted",
    "scanner_output_schema_accepted",
    "classifier_schema_accepted",
    "audit_event_schema_accepted",
    "quarantine_schema_accepted",
    "no_log_ingress_tests_pass",
    "non_oracular_response_tests_pass",
    "no_body_storage_negative_tests_pass",
    "review_escrow_or_ambiguous_retry_policy_accepted",
    "hmac_fingerprint_key_profile_accepted",
    "route_level_search_hook_ingress_protection_accepted",
}
REQUIRED_DOMAIN_COVERAGE = {
    "technical_work": "closed_launch_structured_only",
    "personal_reasoning": "typed_only_no_ingest",
    "career_private": "typed_only_no_ingest",
    "place_service_experience": "typed_only_no_ingest",
    "public_experience_candidate": "blocked_no_conversion",
    "public_aggregate_signal": "blocked_no_dashboard",
}
REQUIRED_SURFACE_COVERAGE = {
    "actual_experience_storage": "blocked_no_storage",
    "public_candidate_conversion": "blocked_no_conversion",
    "b2b_respondent_portal": "blocked_no_surface",
    "abuse_identity_ban_operations": "blocked_no_identity_processing",
    "raw_detail_escrow": "blocked_no_raw_escrow",
    "company_store_dashboard": "blocked_no_dashboard",
}
NO_BODY_DECISIONS = {"accepted", "redact_then_retry", "human_review_required", "reject", "retry_later"}
RAW_ESCROW_PREFLIGHT_FALSE_FLAGS = {
    "stores_body",
    "escrow_handle_created",
    "model_input_includes_raw",
    "validator_errors_include_raw",
}


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def gate_failures(data):
    failures = []
    domain_coverage = data["domain_coverage"]
    missing_domains = sorted(set(REQUIRED_DOMAIN_COVERAGE) - set(domain_coverage))
    if missing_domains:
        failures.append(f"missing domain coverage: {', '.join(missing_domains)}")
    wrong_domains = sorted(
        domain
        for domain, expected in REQUIRED_DOMAIN_COVERAGE.items()
        if domain in domain_coverage and domain_coverage[domain] != expected
    )
    if wrong_domains:
        failures.append(f"unsafe domain coverage: {', '.join(wrong_domains)}")
    surface_coverage = data["surface_coverage"]
    missing_surfaces = sorted(set(REQUIRED_SURFACE_COVERAGE) - set(surface_coverage))
    if missing_surfaces:
        failures.append(f"missing surface coverage: {', '.join(missing_surfaces)}")
    wrong_surfaces = sorted(
        surface
        for surface, expected in REQUIRED_SURFACE_COVERAGE.items()
        if surface in surface_coverage and surface_coverage[surface] != expected
    )
    if wrong_surfaces:
        failures.append(f"unsafe surface coverage: {', '.join(wrong_surfaces)}")
    fallback_decisions = set(data["raw_escrow_fallback_policy"]["allowed_decisions"])
    if {"redact_then_retry", "retry_later"} - fallback_decisions:
        failures.append("raw escrow fallback must allow redact_then_retry and retry_later")
    decisions = {item["decision"]: item for item in data["decision_outcomes"]}
    missing = sorted(REQUIRED_DECISIONS - set(decisions))
    if missing:
        failures.append(f"missing decisions: {', '.join(missing)}")
    blockers = set(data["blocked_until"])
    missing_blockers = sorted(REQUIRED_BLOCKERS - blockers)
    if missing_blockers:
        failures.append(f"missing blockers: {', '.join(missing_blockers)}")
    for decision in NO_BODY_DECISIONS:
        item = decisions.get(decision)
        if not item:
            continue
        if item["stores_body"] or item["creates_card"] or item["indexes"]:
            failures.append(f"{decision} must not store body, create card, or index")
    raw_escrow_cases = data["synthetic_raw_escrow_preflight_cases"]
    if not any(item["decision"] == "human_review_required" for item in raw_escrow_cases):
        failures.append("raw escrow preflight must include human_review_required")
    for item in raw_escrow_cases:
        enabled_flags = sorted(flag for flag in RAW_ESCROW_PREFLIGHT_FALSE_FLAGS if item[flag])
        if enabled_flags:
            failures.append(f"{item['case_id']} must not enable raw escrow flags: {', '.join(enabled_flags)}")
    if data["status"] != "accepted":
        enabled = [name for name, value in data["enablement"].items() if name.endswith("_enabled") and value]
        if enabled:
            failures.append(f"draft intake gate cannot enable surfaces: {', '.join(sorted(enabled))}")
    if data["status"] == "accepted":
        nullable_schemas = [name for name, value in data["schemas"].items() if value is None]
        if nullable_schemas:
            failures.append(f"accepted intake gate has missing schemas: {', '.join(sorted(nullable_schemas))}")
        if blockers:
            failures.append("accepted intake gate must not have blocked_until entries")
    return failures


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate PR-006 intake safety gate fixture.")
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
    print(
        json.dumps(
            {
                "status": "ok",
                "non_synthetic_submit_enabled": data["enablement"]["non_synthetic_submit_enabled"],
                "body_persistence_enabled": data["enablement"]["body_persistence_enabled"],
                "review_escrow_enabled": data["enablement"]["review_escrow_enabled"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
