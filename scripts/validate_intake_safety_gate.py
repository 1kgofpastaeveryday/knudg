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
NO_BODY_DECISIONS = {"redact_then_retry", "human_review_required", "reject", "retry_later"}


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def gate_failures(data):
    failures = []
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
