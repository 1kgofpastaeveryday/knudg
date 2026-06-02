#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "review-ops-gates.schema.json"
DECISIONS_PATH = ROOT / "docs" / "decisions" / "README.md"


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def dec_018_accepted():
    decisions = DECISIONS_PATH.read_text(encoding="utf-8")
    return "| DEC-018 | Review and verification operations | accepted |" in decisions


def gate_failures(data):
    failures = []
    if data["status"] == "accepted" and not dec_018_accepted():
        failures.append("accepted gate requires authoritative DEC-018 accepted review-ops decision")
    if data["status"] == "accepted":
        artifact = data["accepted_review_ops_artifact"]
        if not artifact or not (ROOT / artifact).exists():
            failures.append("accepted gate requires existing review-ops evidence artifact")
    high_risk_lanes = [lane for lane in data["reviewer_lanes"] if lane["risk_band"] == "high"]
    if not high_risk_lanes:
        failures.append("at least one high-risk lane is required")
    if any(not lane["dual_review_required"] for lane in high_risk_lanes):
        failures.append("every high-risk lane requires dual review")
    if data["enablement"]["reviewer_publish_enabled"]:
        failures.append("reviewer publish must remain disabled in this scaffold")
    if data["enablement"]["public_display_enabled"]:
        failures.append("public display must remain disabled in this scaffold")
    if data["enablement"]["high_risk_body_expansion_enabled"]:
        failures.append("high-risk body expansion must remain disabled in this scaffold")
    return failures


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate DEC-018 review operations gate scaffold fixtures.")
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
    print(json.dumps({
        "status": "ok",
        "reviewer_publish_enabled": False,
        "public_display_enabled": False,
        "high_risk_body_expansion_enabled": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
