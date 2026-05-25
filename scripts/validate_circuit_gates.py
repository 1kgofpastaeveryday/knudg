#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "circuit-gates.schema.json"
REQUIRED_FAMILIES = {
    "auth_revocation_data_integrity_backup",
    "public_wedge_publication",
    "landing_route_denylist",
    "vector_rerank_cost",
    "noncritical_writes_admission",
}
EXPECTED_BEHAVIOR = {
    "auth_revocation_data_integrity_backup": {
        "postgres_unavailable_behavior": "fail_closed",
        "stale_emergency_behavior": "remain_closed_page_operator",
    },
    "public_wedge_publication": {
        "postgres_unavailable_behavior": "publication_search_disabled",
        "stale_emergency_behavior": "remain_disabled_no_auto_clear",
    },
    "landing_route_denylist": {
        "postgres_unavailable_behavior": "serve_inert_static_or_404_410",
        "stale_emergency_behavior": "keep_deny_until_probe",
    },
    "vector_rerank_cost": {
        "postgres_unavailable_behavior": "disable_dependency_exact_fts_or_no_suggestion",
        "stale_emergency_behavior": "keep_disabled_until_owner_review",
    },
    "noncritical_writes_admission": {
        "postgres_unavailable_behavior": "pause_or_reject_idempotently",
        "stale_emergency_behavior": "keep_paused_no_background_retries",
    },
}


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def gate_failures(data):
    failures = []
    seen = set()
    duplicates = []
    for item in data["families"]:
        if item["family"] in seen:
            duplicates.append(item["family"])
        seen.add(item["family"])
    if duplicates:
        failures.append(f"duplicate circuit families: {', '.join(sorted(set(duplicates)))}")
    families = {item["family"]: item for item in data["families"]}
    missing = sorted(REQUIRED_FAMILIES - set(families))
    if missing:
        failures.append(f"missing circuit families: {', '.join(missing)}")
    for family_name, expected in EXPECTED_BEHAVIOR.items():
        if family_name not in families:
            continue
        family = families[family_name]
        if family["auto_clear_allowed"]:
            failures.append(f"{family_name} must not auto-clear")
        if family["postgres_unavailable_behavior"] != expected["postgres_unavailable_behavior"]:
            failures.append(f"{family_name} postgres-unavailable behavior mismatch")
        if family["stale_emergency_behavior"] != expected["stale_emergency_behavior"]:
            failures.append(f"{family_name} stale emergency behavior mismatch")
    if data["enablement"]["live_mutation_enabled"]:
        failures.append("live circuit mutation must remain disabled in this scaffold")
    if data["enablement"]["public_publication_enabled"]:
        failures.append("public publication must remain disabled in this scaffold")
    return failures


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate operational circuit gate scaffold fixtures.")
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
    print(json.dumps({"status": "ok", "live_mutation_enabled": False, "public_publication_enabled": False}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
