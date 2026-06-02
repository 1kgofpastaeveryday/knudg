#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "m3-retrieval-gates.schema.json"
DECISIONS_PATH = ROOT / "docs" / "decisions" / "README.md"


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validation_errors(schema, data):
    validator = Draft202012Validator(schema)
    return sorted(validator.iter_errors(data), key=lambda error: list(error.path))


def gate_failures(data):
    failures = []
    decisions = DECISIONS_PATH.read_text(encoding="utf-8")
    dec_014a_accepted = "| DEC-014A |" in decisions and "| DEC-014A | M3 internal protected-data sender-constrained proof profile | accepted |" in decisions
    if data["status"] == "accepted":
        if data["exact_fts"]["rank_formula"] == "unset":
            failures.append("accepted gate requires exact_fts.rank_formula")
        if data["exact_fts"]["score_normalization"] == "unset":
            failures.append("accepted gate requires exact_fts.score_normalization")
        if data["exact_fts"]["tokenizer_profile"] == "unset":
            failures.append("accepted gate requires exact_fts.tokenizer_profile")
        spec_artifact = data["exact_fts"]["accepted_spec_artifact"]
        if not spec_artifact or not (ROOT / spec_artifact).exists():
            failures.append("accepted gate requires existing exact/FTS accepted spec artifact")
        proof_artifact = data["proof_profile"]["accepted_profile_artifact"]
        if (
            data["proof_profile"]["status"] != "accepted"
            or not data["proof_profile"]["accepted_profile"]
            or not dec_014a_accepted
            or not proof_artifact
            or not (ROOT / proof_artifact).exists()
        ):
            failures.append("accepted gate requires authoritative DEC-014A accepted proof profile")
    if data["protected_data_enablement"]["enabled"] is not False:
        failures.append("protected data enablement must remain false in this scaffold")
    if not data["protected_data_enablement"]["blocked_until"]:
        failures.append("protected data scaffold must name blocking gates")
    return failures


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate M3 retrieval gate scaffold fixtures.")
    parser.add_argument("--input", required=True)
    args = parser.parse_args(argv)

    schema = load_json(SCHEMA_PATH)
    data = load_json(args.input)
    errors = validation_errors(schema, data)
    if errors:
        print(json.dumps({"status": "rejected", "errors": [error.message for error in errors]}, sort_keys=True))
        return 2
    failures = gate_failures(data)
    if failures:
        print(json.dumps({"status": "blocked", "blocking_gates": failures}, sort_keys=True))
        return 3
    print(json.dumps({"status": "ok", "protected_data_enabled": False}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
