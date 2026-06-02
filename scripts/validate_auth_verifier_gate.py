#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "auth-verifier-gate.schema.json"
REQUIRED_NEGATIVE_TESTS = {
    "hs256_rejected_non_local",
    "alg_none_rejected",
    "wrong_audience_rejected",
    "wrong_issuer_rejected",
    "stale_key_rejected",
    "stale_nonce_rejected",
    "proof_key_mismatch_rejected",
    "cross_resource_replay_rejected",
    "rls_call_sites_unchanged",
}
REQUIRED_BLOCKERS = {
    "asymmetric_or_kms_profile_accepted",
    "sender_constrained_profile_accepted",
    "nonce_replay_store_implemented",
    "key_rotation_tests_pass",
    "negative_auth_tests_pass",
    "environment_assertions_pass",
    "request_context_backend_swap_tested",
}


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def gate_failures(data):
    failures = []
    missing_tests = sorted(REQUIRED_NEGATIVE_TESTS - set(data["negative_tests"]))
    if missing_tests:
        failures.append(f"missing negative tests: {', '.join(missing_tests)}")
    if data["local_hs256"]["production_enabled"]:
        failures.append("local HS256 must stay disabled in production")
    if data["local_hs256"]["team_or_staging_enabled"]:
        failures.append("local HS256 must stay disabled in team or staging environments")
    if data["status"] != "accepted":
        missing_blockers = sorted(REQUIRED_BLOCKERS - set(data["blocked_until"]))
        if missing_blockers:
            failures.append(f"missing blockers: {', '.join(missing_blockers)}")
        profile = data["non_local_profile"]
        if profile["profile_type"] != "unset":
            failures.append("draft auth verifier gate cannot self-select a non-local profile")
    if data["status"] == "accepted":
        profile = data["non_local_profile"]
        if profile["profile_type"] == "unset":
            failures.append("accepted auth verifier gate must select a non-local profile")
        if profile["sender_constrained_proof"] == "unset":
            failures.append("accepted auth verifier gate must select sender-constrained proof")
        for field in ["issuer_binding", "audience_binding", "resource_indicator_binding", "nonce_replay_store", "key_rotation"]:
            if not profile[field]:
                failures.append(f"accepted auth verifier gate missing {field}")
        if profile["outage_behavior"] == "unset":
            failures.append("accepted auth verifier gate must define outage behavior")
        if data["blocked_until"]:
            failures.append("accepted auth verifier gate must not have blocked_until entries")
    return failures


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate PR-004 auth verifier gate fixture.")
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
                "profile_type": data["non_local_profile"]["profile_type"],
                "production_hs256_enabled": data["local_hs256"]["production_enabled"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
